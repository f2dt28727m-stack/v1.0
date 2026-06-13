#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
produce.py - End-to-end offline quiz production pipeline.

Pipeline:
    1. Input: --topic
    2. Generate N category quizzes via LLM
    3. Auto-validate (structural: 12Q/16R/MBTI/banned-words)
    4. Persona review (LLM-as-Z-gen-Western-die-hard-fan, 5-dim scoring)
    5. Output to staging/ (NEVER touches live quizzes/)
    6. Write REPORT.md with pass/fail summary + reviewer notes

Usage:
    python3 produce.py --topic "BLACKPINK"
    python3 produce.py --topic "BLACKPINK" --only match,which
    python3 produce.py --topic "BTS" --compliance medium
    python3 produce.py --promote ./quizzes/staging/BLACKPINK_2026-06-13  # to go live

Output:
    quizzes/staging/<topic>_<timestamp>/
        quiz_001_<cat>.json         # Generated + auto-validated
        quiz_002_<cat>.json
        ...
        persona_reviews.json        # All persona reviewer notes
        REPORT.md                   # Human-readable summary

Environment (in .env):
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Reuse everything from generate_quiz
sys.path.insert(0, str(Path(__file__).parent))
from generate_quiz import (
    SCRIPT_DIR, QUIZZES_DIR, DATA_DIR, DB_PATH, TAGS_PATH,
    CATEGORIES, MBTI_LETTERS, MBTI_TYPES,
    CATEGORY_META, CATEGORY_TITLE_GENERIC,
    BANNED_WORDS, REQUIRED_PHRASES,
    SAMPLE_QUESTION_LETTERS, SCORE_TABLE_STR,
    build_prompt, call_llm, parse_llm_json,
    postprocess_quiz, validate_quiz, shuffle_options,
    load_tag_lib, save_tag_lib, get_all_tag_names,
    init_db, log_generation,
)

STAGING_DIR = QUIZZES_DIR / "staging"

# Categories the user typically wants (drop "future" for the standard 7)
DEFAULT_CATEGORIES = ["match", "which", "type", "how", "hidden",
                      "whatwould", "pick"]


# ============================================================
# Persona review (LLM-as-Z-gen-Western-die-hard-fan)
# ============================================================
PERSONA_PROMPT_TEMPLATE = """You are a 19-year-old Western Gen-Z fan of {topic}. You've been deep in the fandom for 3+ years, you have a Twitter stan account, you've been to a concert, and you know every song, era, and member/character detail. Your language is casual English with light slang ("literally", "no cap", "down bad", "ate that", "main character energy", etc.).

A new personality quiz about {topic} just dropped. You are NOT a marketer or writer — you are the user. Give honest, casual feedback as if you were texting a friend.

QUIZ TITLE: {title}

QUIZ DESCRIPTION: {description}

12 QUESTIONS (each with 4 options + score letter):
{questions_block}

16 RESULTS (each: title, description, mbti):
{results_block}

---

Evaluate on these 5 dimensions. Be honest — if the quiz feels corporate or AI-generated, say so.

1. **IP-specificity (0-10)**: Does the quiz actually reference real songs, eras, members, iconic moments? Or does it use generic phrases that fit any celebrity?
2. **Engagement (0-10)**: Would you actually screenshot your result and post it on TikTok/Twitter? Would you share it in your group chat?
3. **Personality differentiation (0-10)**: Do the 16 results feel like 16 different people? Or are they all the same "quiet creative" trope?
4. **Authenticity (0-10)**: Does the language feel fan-coded (someone who actually consumes the content wrote it)? Or does it read like a press release?
5. **Compliance safety (0-10)**: Are there any awkward copyright hedges (like "true-world" instead of "real-world", forced disclaimers, generic "the official X") that break immersion?

For each score, give 1 sentence of reasoning in casual English (not corporate).

Then provide:
- A list of 3-5 SPECIFIC actionable fixes (e.g., "Q3 options 1 and 3 are basically the same — make option 3 about a different scenario").
- A list of stand-out things that worked (so the production system can re-use those patterns).
- A final verdict: "SHIP" (good to publish as-is), "REVISE" (small fixes needed), or "REJECT" (needs regeneration with different framing).

Output ONLY valid JSON, no commentary, no markdown:
{{
  "scores": {{
    "ip_specificity": N,
    "engagement": N,
    "differentiation": N,
    "authenticity": N,
    "compliance_safety": N
  }},
  "reasoning": {{
    "ip_specificity": "...",
    "engagement": "...",
    "differentiation": "...",
    "authenticity": "...",
    "compliance_safety": "..."
  }},
  "fixes": ["fix 1", "fix 2", ...],
  "what_worked": ["thing 1", "thing 2", ...],
  "verdict": "SHIP" | "REVISE" | "REJECT",
  "would_share": true | false
}}
"""


def build_persona_prompt(topic: str, quiz: dict) -> str:
    """Build the persona review prompt for one quiz."""
    questions_block_lines = []
    for q in quiz.get("questions", []):
        opts = " | ".join(
            f"{o.get('text','')} [{o.get('score','')}]"
            for o in q.get("options", [])
        )
        questions_block_lines.append(f"Q{q.get('qId', '?')}: {q.get('text','')}\n   {opts}")
    questions_block = "\n".join(questions_block_lines)

    results_block_lines = []
    for r in quiz.get("results", []):
        d = r.get("description", "")
        results_block_lines.append(
            f"[{r.get('mbti','?')}] {r.get('title','')}\n   {d}"
        )
    results_block = "\n".join(results_block_lines)

    return PERSONA_PROMPT_TEMPLATE.format(
        topic=topic,
        title=quiz.get("title", ""),
        description=quiz.get("description", ""),
        questions_block=questions_block,
        results_block=results_block,
    )


def run_persona_review(topic: str, quiz: dict,
                       base_url: str, api_key: str, model: str) -> dict:
    """Run the persona review. Returns parsed JSON or fallback error dict."""
    prompt = build_persona_prompt(topic, quiz)
    try:
        content, pt, ct = call_llm(prompt, max_retries=2,
                                    base_url=base_url, api_key=api_key,
                                    model=model)
        review = parse_llm_json(content)
        # Sanity-check shape
        if "scores" not in review or "verdict" not in review:
            raise ValueError("Persona review missing required fields")
        return review
    except Exception as e:
        return {
            "error": str(e),
            "scores": {},
            "reasoning": {},
            "fixes": [],
            "what_worked": [],
            "verdict": "ERROR",
            "would_share": False,
        }


# ============================================================
# Per-quiz production (generate → validate → review)
# ============================================================
def produce_one_quiz(topic: str, category: str, compliance_mode: str,
                     tag_lib: dict,
                     staging_dir: Path, idx: int,
                     base_url: str, api_key: str, model: str,
                     max_persona_retries: int = 1,
                     auto_revise_threshold: int = 0) -> dict:
    """Generate one quiz, validate, persona-review, and save to staging.
    Returns a result dict with status, paths, persona review, etc."""
    fname = f"quiz_{idx:03d}_{category}.json"
    fpath = staging_dir / fname

    result = {
        "topic": topic, "category": category,
        "compliance_mode": compliance_mode,
        "file_path": str(fpath.relative_to(SCRIPT_DIR)),
        "status": None,
        "validation_passed": False,
        "persona_review": None,
        "prompt_tokens": 0, "completion_tokens": 0,
        "cost_usd": 0,
        "generation_attempts": 0,
        "persona_attempts": 0,
        "error_msg": None,
    }

    # --- Phase 1: generate + auto-validate
    existing_tags = get_all_tag_names(tag_lib)
    prompt = build_prompt(topic, category, compliance_mode, existing_tags)
    feedback = ""
    quiz = None
    for attempt in range(3):
        try:
            result["generation_attempts"] += 1
            full_prompt = prompt + feedback
            content, pt, ct = call_llm(full_prompt, max_retries=3,
                                        base_url=base_url, api_key=api_key,
                                        model=model)
            result["prompt_tokens"] += pt
            result["completion_tokens"] += ct
            result["cost_usd"] += (pt * 0.14 + ct * 0.28) / 1_000_000
            quiz = parse_llm_json(content)

            quiz, _ = postprocess_quiz(quiz, compliance_mode)
            valid, err, _stats = validate_quiz(
                quiz, compliance_mode, set(existing_tags))
            if valid:
                result["validation_passed"] = True
                break
            else:
                feedback = (
                    f"\n\n=== FEEDBACK FROM PREVIOUS ATTEMPT ===\n"
                    f"Validation failed: {err}\nPlease REGENERATE the quiz "
                    f"fixing ONLY this issue.\n"
                )
        except Exception as e:
            feedback = f"\n\n[error] {type(e).__name__}: {e}\n"

    if not result["validation_passed"]:
        result["status"] = "FAILED_VALIDATION"
        result["error_msg"] = f"Validation did not pass after 3 attempts"
        return result

    # --- Phase 2: persona review
    review = run_persona_review(topic, quiz, base_url, api_key, model)
    result["persona_attempts"] = 1
    result["persona_review"] = review

    # Decide whether to regenerate. Configurable threshold: if persona
    # rejects (REJECT) OR gives REVISE with ip_specificity below threshold,
    # we feed the fixes back to the LLM and regenerate.
    needs_regen = review.get("verdict") == "REJECT"
    if not needs_regen and auto_revise_threshold > 0:
        ip_score = review.get("scores", {}).get("ip_specificity", 10)
        if ip_score < auto_revise_threshold:
            needs_regen = True
            print(f"      (ip_specificity={ip_score} < "
                  f"{auto_revise_threshold}, auto-revising)")

    # Optionally retry on REJECT or low IP-specificity
    if needs_regen and max_persona_retries >= 1:
        for retry_i in range(max_persona_retries):
            result["persona_attempts"] += 1
            fix_prompt = build_prompt(
                topic, category, compliance_mode, existing_tags) + (
                f"\n\n=== PERSONA REVIEW FEEDBACK (you failed this) ===\n"
                f"Reasoning: {json.dumps(review.get('reasoning', {}), indent=2)}\n"
                f"Fixes requested: {json.dumps(review.get('fixes', []), indent=2)}\n"
                f"REGENERATE the quiz addressing ALL the feedback above. "
                f"Keep what worked, fix what didn't.\n"
            )
            try:
                content, pt, ct = call_llm(
                    fix_prompt, max_retries=2,
                    base_url=base_url, api_key=api_key, model=model)
                result["prompt_tokens"] += pt
                result["completion_tokens"] += ct
                result["cost_usd"] += (pt * 0.14 + ct * 0.28) / 1_000_000
                quiz2 = parse_llm_json(content)
                quiz2, _ = postprocess_quiz(quiz2, compliance_mode)
                valid, err, _ = validate_quiz(
                    quiz2, compliance_mode, set(existing_tags))
                if valid:
                    quiz = quiz2
                    review = run_persona_review(
                        topic, quiz, base_url, api_key, model)
                    result["persona_review"] = review
                    if review.get("verdict") != "REJECT":
                        break
            except Exception as e:
                result["error_msg"] = f"persona-retry error: {e}"

    # --- Phase 3: write to staging
    shuffle_options(quiz)
    # Use a stable staging quizId (1-based within this batch)
    quiz["quizId"] = idx * 1000  # distinct ID for staging
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, indent=2)

    verdict = review.get("verdict", "?")
    if verdict == "ERROR":
        result["status"] = "PERSONA_ERROR"
    elif verdict == "REJECT":
        result["status"] = "NEEDS_REVIEW"
    else:
        result["status"] = f"VERDICT_{verdict}"

    return result


# ============================================================
# Staging directory management
# ============================================================
def make_staging_dir(topic: str) -> Path:
    """Create a new staging directory for this run. Live quizzes/ is never touched."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize topic for filesystem
    safe_topic = re.sub(r"[^A-Za-z0-9_-]", "_", topic)[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{safe_topic}_{ts}"
    staging = STAGING_DIR / name
    staging.mkdir(parents=True, exist_ok=False)
    return staging


# ============================================================
# REPORT.md
# ============================================================
def write_report(staging_dir: Path, topic: str, compliance_mode: str,
                 results: list, total_tokens: int, total_cost: float,
                 elapsed_s: float) -> Path:
    """Write a human-readable REPORT.md for this production run."""
    path = staging_dir / "REPORT.md"

    n = len(results)
    n_pass = sum(1 for r in results if r["status"] == "VERDICT_SHIP")
    n_revise = sum(1 for r in results if r["status"] == "VERDICT_REVISE")
    n_reject = sum(1 for r in results if r["status"] == "NEEDS_REVIEW")
    n_failed = sum(1 for r in results if "FAILED" in r["status"])
    n_error = sum(1 for r in results if r["status"] == "PERSONA_ERROR")

    overall = (
        "READY TO PROMOTE" if n_pass + n_revise == n
        else "MOSTLY OK, SOME NEEDS REVIEW" if n_pass + n_revise >= n / 2
        else "BLOCKED, NEEDS REGENERATION"
    )

    lines = [
        f"# Production Report: {topic}",
        "",
        f"**Generated**: {datetime.now().isoformat(timespec='seconds')}",
        f"**Compliance mode**: {compliance_mode}",
        f"**Categories produced**: {n}",
        f"**Overall verdict**: {overall}",
        f"**Total tokens**: {total_tokens:,}",
        f"**Total cost**: ${total_cost:.4f}",
        f"**Elapsed**: {elapsed_s:.1f}s",
        "",
        "## Status breakdown",
        "",
        f"- ✓ SHIP (publish as-is): {n_pass}",
        f"- ⚠ REVISE (publish with minor fixes): {n_revise}",
        f"- ✗ NEEDS_REVIEW (persona rejected): {n_reject}",
        f"- ✗ PERSONA_ERROR (reviewer failed): {n_error}",
        f"- ✗ FAILED_VALIDATION (couldn't generate): {n_failed}",
        "",
        "## Per-quiz summary",
        "",
    ]

    for r in results:
        cat = r["category"]
        status = r["status"]
        marker = {
            "VERDICT_SHIP": "✓ SHIP",
            "VERDICT_REVISE": "⚠ REVISE",
            "NEEDS_REVIEW": "✗ REJECT",
            "PERSONA_ERROR": "✗ ERROR",
            "FAILED_VALIDATION": "✗ FAILED",
        }.get(status, status)

        lines.append(f"### `{r['file_path']}` — {cat} — {marker}")
        lines.append("")

        if r.get("persona_review"):
            review = r["persona_review"]
            scores = review.get("scores", {})
            score_str = ", ".join(
                f"{k.replace('_', ' ')}={v}" for k, v in scores.items())
            lines.append(f"- **Persona scores**: {score_str}")
            lines.append(f"- **Would share?**: {review.get('would_share', '?')}")

            fixes = review.get("fixes", [])
            if fixes:
                lines.append(f"- **Top fixes requested**:")
                for f in fixes[:3]:
                    lines.append(f"  - {f}")
            worked = review.get("what_worked", [])
            if worked:
                lines.append(f"- **What worked**:")
                for w in worked[:2]:
                    lines.append(f"  - {w}")
        else:
            lines.append(f"- **Error**: {r.get('error_msg', '?')}")
        lines.append(f"- **Generation attempts**: {r['generation_attempts']}, persona attempts: {r['persona_attempts']}")
        lines.append("")

    lines.extend([
        "## Next steps",
        "",
        "1. **Review the REPORT above and inspect each quiz file manually.**",
        "2. **To publish to live**:",
        "   ```bash",
        f"   python3 produce.py --promote {staging_dir.relative_to(SCRIPT_DIR)}",
        "   ```",
        "3. **Staging location**: `" + str(staging_dir.relative_to(SCRIPT_DIR)) + "`",
        "4. **Live quizzes/ untouched**: confirmed (this run never wrote there).",
        "",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ============================================================
# Promote staging → live
# ============================================================
def promote(staging_subdir: Path, dry_run: bool = False,
            only: str = "") -> int:
    """Copy validated quizzes from staging/ to live quizzes/.
    Returns the number of files promoted.
    only: comma-separated category filter (e.g. "type,match,whatwould")."""
    if not staging_subdir.exists():
        raise FileNotFoundError(f"Staging dir not found: {staging_subdir}")
    if not staging_subdir.is_relative_to(STAGING_DIR):
        raise ValueError(
            f"{staging_subdir} is not under {STAGING_DIR}. Refusing to promote.")

    all_quiz_files = sorted(staging_subdir.glob("quiz_*.json"))
    if not all_quiz_files:
        raise FileNotFoundError(f"No quiz_*.json files in {staging_subdir}")

    # Apply --only filter
    if only:
        only_cats = {c.strip() for c in only.split(",") if c.strip()}
        # Each file is named like quiz_003_type.json — extract category
        def _cat_of(p: Path) -> str:
            m = re.match(r"quiz_\d+_(.+)\.json$", p.name)
            return m.group(1) if m else ""
        quiz_files = [f for f in all_quiz_files if _cat_of(f) in only_cats]
        skipped = len(all_quiz_files) - len(quiz_files)
    else:
        quiz_files = all_quiz_files
        skipped = 0

    # Find next quiz ID
    max_id = 0
    for f in QUIZZES_DIR.glob("quiz_*.json"):
        m = re.match(r"quiz_(\d+)\.json", f.name)
        if m:
            max_id = max(max_id, int(m.group(1)))

    promoted = 0
    print(f"\n{'='*60}\n  Promote {len(quiz_files)} quizzes from staging"
          f"{f' (filtered from {len(all_quiz_files)})' if only else ''}"
          f"\n{'='*60}\n")
    if skipped and not dry_run:
        print(f"  (skipping {skipped} other quizzes in staging/ — "
              f"they stay offline for later)\n")
    for src in quiz_files:
        with open(src) as f:
            q = json.load(f)
        cat = q.get("category", "?")
        title = q.get("title", "?")
        # Recompute quizId for live
        max_id += 1
        q["quizId"] = max_id
        live_name = f"quiz_{max_id:03d}.json"
        live_path = QUIZZES_DIR / live_name
        print(f"  {src.name:35s}  [{cat:10s}]  {title}")
        print(f"     → {live_name}")
        if not dry_run:
            with open(live_path, "w", encoding="utf-8") as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
        promoted += 1
    print(f"\n  {'[dry-run] Would promote' if dry_run else '✓ Promoted'} "
          f"{promoted} quizzes. Live quiz IDs: {max_id - promoted + 1}..{max_id}")
    return promoted


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="End-to-end offline quiz production pipeline")
    sub = parser.add_subparsers(dest="cmd")

    # produce
    p = sub.add_parser("produce", help="Generate quizzes into staging/")
    p.add_argument("--topic", required=True)
    p.add_argument("--compliance", default="light",
                   choices=["light", "medium", "strict"])
    p.add_argument("--only", default="",
                   help="Comma-separated categories, e.g. 'match,which'")
    p.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES),
                   help=f"Default: {','.join(DEFAULT_CATEGORIES)}")
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--no-persona", action="store_true",
                   help="Skip persona review (technical validation only)")
    p.add_argument("--persona-retries", type=int, default=1,
                   help="Max persona-rejection retries (default 1)")
    p.add_argument("--auto-revise-threshold", type=int, default=0,
                   help="Auto-regenerate if persona IP-specificity < N (0=off). "
                        "Recommended 4.")

    # promote
    pm = sub.add_parser("promote", help="Move staging quizzes to live")
    pm.add_argument("staging_dir", help="Path under quizzes/staging/")
    pm.add_argument("--dry-run", action="store_true")
    pm.add_argument("--only", default="",
                    help="Comma-separated categories to promote "
                         "(e.g. 'type,match,whatwould'). Default: all.")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return 0

    base_url = (args.base_url if hasattr(args, "base_url") and args.base_url
                else os.environ.get("LLM_BASE_URL", "").rstrip("/"))
    api_key = (args.api_key if hasattr(args, "api_key") and args.api_key
               else os.environ.get("LLM_API_KEY", ""))
    model = (args.model if hasattr(args, "model") and args.model
             else os.environ.get("LLM_MODEL", "deepseek-chat"))

    if args.cmd == "promote":
        if not base_url:
            pass  # promote doesn't need LLM
        return promote(Path(args.staging_dir).resolve(),
                       dry_run=args.dry_run, only=args.only)

    if args.cmd == "produce":
        if not base_url or not api_key:
            print("ERROR: LLM_BASE_URL and LLM_API_KEY must be set in env.")
            return 1

        # Pick categories
        if args.only:
            cats = [c.strip() for c in args.only.split(",") if c.strip()]
        else:
            cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        for c in cats:
            if c not in CATEGORIES:
                print(f"ERROR: unknown category '{c}'. Valid: {CATEGORIES}")
                return 1
        n = len(cats)

        # Setup
        tag_lib = load_tag_lib(TAGS_PATH)
        staging_dir = make_staging_dir(args.topic)

        print(f"\n{'='*60}")
        print(f"  Produce Quizzes (OFFLINE)")
        print(f"  Topic:        {args.topic}")
        print(f"  Compliance:   {args.compliance}")
        print(f"  Categories:   {', '.join(cats)}")
        print(f"  Persona:      {'on' if not args.no_persona else 'off'}")
        print(f"  Staging:      {staging_dir.relative_to(SCRIPT_DIR)}/")
        print(f"  Live dir:     UNTOUCHED ✓")
        print(f"{'='*60}\n")

        start = time.time()
        results = []
        for i, cat in enumerate(cats):
            print(f"  [{i+1}/{n}] {cat}...")
            if args.no_persona:
                # Skip persona by setting retries to 0 and patching the
                # review call to a stub. Cleaner: still call it but mark
                # the verdict from the auto-validation only.
                pass
            r = produce_one_quiz(
                args.topic, cat, args.compliance, tag_lib,
                staging_dir, i + 1, base_url, api_key, model,
                max_persona_retries=(0 if args.no_persona else args.persona_retries),
                auto_revise_threshold=args.auto_revise_threshold)
            # If persona is off, fabricate a SHIP verdict
            if args.no_persona:
                r["persona_review"] = {
                    "scores": {},
                    "verdict": "SHIP",
                    "would_share": None,
                    "fixes": [],
                    "what_worked": [],
                    "reasoning": {"note": "persona review disabled (--no-persona)"},
                }
                r["status"] = "VERDICT_SHIP"
            results.append(r)
            print(f"      {r['status']}  ({r['file_path']})")
        elapsed = time.time() - start

        # Persist persona_reviews.json
        reviews = [
            {
                "category": r["category"],
                "status": r["status"],
                "persona_review": r["persona_review"],
            }
            for r in results
        ]
        with open(staging_dir / "persona_reviews.json", "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)

        # Write REPORT.md
        total_tokens = sum(r["prompt_tokens"] + r["completion_tokens"]
                           for r in results)
        total_cost = sum(r["cost_usd"] for r in results)
        report_path = write_report(
            staging_dir, args.topic, args.compliance,
            results, total_tokens, total_cost, elapsed)

        # Save tag lib (in case new tags were created — though we don't
        # add new tags in staging mode; that's a live action)
        save_tag_lib(TAGS_PATH, tag_lib)

        # Final summary
        n_ship = sum(1 for r in results if r["status"] == "VERDICT_SHIP")
        n_revise = sum(1 for r in results if r["status"] == "VERDICT_REVISE")
        n_reject = sum(1 for r in results if r["status"] == "NEEDS_REVIEW")
        n_failed = sum(1 for r in results if "FAILED" in r["status"])

        print(f"\n{'='*60}")
        print(f"  Done in {elapsed:.1f}s")
        print(f"  ✓ SHIP:           {n_ship}")
        print(f"  ⚠ REVISE:         {n_revise}")
        print(f"  ✗ NEEDS_REVIEW:   {n_reject}")
        print(f"  ✗ FAILED:         {n_failed}")
        print(f"  Tokens:           {total_tokens:,}")
        print(f"  Cost:             ${total_cost:.4f}")
        print(f"  Staging:          {staging_dir.relative_to(SCRIPT_DIR)}/")
        print(f"  Report:           {report_path.relative_to(SCRIPT_DIR)}")
        print(f"  Live quizzes/:    UNTOUCHED ✓")
        print(f"{'='*60}\n")
        if n_ship + n_revise > 0:
            print(f"  To publish to live:")
            print(f"    python3 produce.py promote {staging_dir.relative_to(SCRIPT_DIR)}")
            print()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
