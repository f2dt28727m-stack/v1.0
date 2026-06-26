"""
Scan quizzes/ for two classes of bugs:
  1. Chinese characters leaked into English content  -> chinese_leak_report.csv
  2. results[].mbti  vs. results[].description  text mismatch  -> mbti_mismatch_report.csv

Also reports any result with a missing/empty mbti field.

Production files only:
  - quizzes/quiz_*.json  (top-level)
Skips: staging/, some tests/, _archive_bp_*/
"""

import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
QUIZ_DIR = os.path.join(ROOT, "quizzes")
SKIP_DIR_NAMES = {"staging", "some tests", "_archive_bp_v1", "_archive_bp_v2"}

CN_RE = re.compile(r"[\u4e00-\u9fff]")

# Common MBTI-4-letter patterns in result descriptions.
# Handles curly + straight apostrophe, "an" / "a", and various trailing punctuation.
# Capture the FIRST 4-letter token that could be an MBTI, in order of preference.
# Each pattern is tried left-to-right; the first one that yields a valid MBTI wins.
MBTI_PATTERNS = [
    # "You're an ESTJ" / "You're a ESFP" / "You're an ESTJ—"
    re.compile(r"You(?:'|’)re\s+(?:an?\s+)([EISNTFJP]{4})\b", re.IGNORECASE),
    # "As an ISTP," / "As an ESFP—" / "An ENTJ type"
    re.compile(r"\b(?:[Aa]s\s+an?|[Aa]n)\s+([EISNTFJP]{4})\b", re.IGNORECASE),
    # "ISTJ: ..." / "ESFP—the ..." (MBTI followed by colon, em-dash, comma)
    re.compile(r"\b([EISNTFJP]{4})(?:\s*[—\-:,]|\s+who\s+|\s+with\s+)", re.IGNORECASE),
]

VALID_MBTIS = {
    "ESTJ", "ESFJ", "ENTJ", "ENFJ",
    "ISTJ", "ISFJ", "INTJ", "INFJ",
    "ESTP", "ESFP", "ENTP", "ENFP",
    "ISTP", "ISFP", "INTP", "INFP",
}


def list_production_quizzes():
    out = []
    for name in sorted(os.listdir(QUIZ_DIR)):
        full = os.path.join(QUIZ_DIR, name)
        if name in SKIP_DIR_NAMES:
            continue
        if os.path.isfile(full) and name.startswith("quiz_") and name.endswith(".json"):
            out.append(full)
    return out


def iter_strings(obj, path=""):
    """Yield (path, value) for every string leaf in a JSON-ish object."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from iter_strings(item, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}" if path else k
            yield from iter_strings(v, child)


def extract_mbti_from_text(text):
    """Return the MBTI-4-letter code mentioned in the description, or None.

    Tries each pattern in priority order; returns the first hit that is a
    recognized MBTI code. Filters out 4-letter words that happen to be made
    of MBTI letters but are not actual codes (e.g. "Jett" in "You're Jett...").
    """
    if not text:
        return None
    for pat in MBTI_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).upper()
            if candidate in VALID_MBTIS:
                return candidate
    return None


def main():
    files = list_production_quizzes()
    print(f"Scanning {len(files)} production quiz files in {QUIZ_DIR}")

    # --- Bug 1: Chinese leak ---
    cn_rows = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as e:
            print(f"  ! skip {fp}: {e}", file=sys.stderr)
            continue
        quiz_id = data.get("quizId")
        for path, value in iter_strings(data):
            if CN_RE.search(value):
                # Truncate the snippet to keep CSV readable
                snippet = value if len(value) <= 200 else value[:200] + "..."
                cn_rows.append({
                    "quiz_id": quiz_id,
                    "file": os.path.relpath(fp, ROOT),
                    "field": path,
                    "snippet": snippet,
                })

    cn_csv = os.path.join(ROOT, "chinese_leak_report.csv")
    with open(cn_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["quiz_id", "file", "field", "snippet"])
        w.writeheader()
        w.writerows(cn_rows)
    print(f"[Bug 1] {len(cn_rows)} Chinese occurrences -> {cn_csv}")

    # --- Bug 2: mbti field vs description text ---
    mismatch_rows = []
    missing_mbti_rows = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        quiz_id = data.get("quizId")
        for idx, r in enumerate(data.get("results", []) or []):
            declared = r.get("mbti") or r.get("mbtiType")
            desc = r.get("description", "")
            text_mbti = extract_mbti_from_text(desc)
            title = r.get("title", "")

            if not declared:
                # Field missing entirely — matching will silently fall back to results[0]
                missing_mbti_rows.append({
                    "quiz_id": quiz_id,
                    "result_index": idx,
                    "title": title,
                    "issue": "missing_mbti_field",
                    "declared_mbti": "",
                    "text_mbti": text_mbti or "",
                    "description_snippet": (desc or "")[:160],
                })
                continue

            if text_mbti and declared.upper() != text_mbti:
                mismatch_rows.append({
                    "quiz_id": quiz_id,
                    "result_index": idx,
                    "title": title,
                    "issue": "mbti_field_vs_text_mismatch",
                    "declared_mbti": declared,
                    "text_mbti": text_mbti,
                    "description_snippet": (desc or "")[:160],
                })

    mm_csv = os.path.join(ROOT, "mbti_mismatch_report.csv")
    with open(mm_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "quiz_id", "result_index", "title", "issue",
            "declared_mbti", "text_mbti", "description_snippet",
        ])
        w.writeheader()
        w.writerows(mismatch_rows)
    print(f"[Bug 2] {len(mismatch_rows)} mbti/description mismatches -> {mm_csv}")

    miss_csv = os.path.join(ROOT, "mbti_missing_report.csv")
    with open(miss_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "quiz_id", "result_index", "title", "issue",
            "declared_mbti", "text_mbti", "description_snippet",
        ])
        w.writeheader()
        w.writerows(missing_mbti_rows)
    print(f"[Bug 2] {len(missing_mbti_rows)} results missing mbti field -> {miss_csv}")


if __name__ == "__main__":
    main()
