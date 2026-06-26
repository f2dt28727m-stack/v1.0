#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_quiz.py - AIGC quiz generator for QuizFig

Usage:
    python generate_quiz.py --topic "BLACKPINK" --compliance light
    python generate_quiz.py --topic "BLACKPINK" --dry-run
    python generate_quiz.py --topic "BLACKPINK" --only match,which

Environment:
    LLM_BASE_URL   OpenAI-compatible base URL (e.g. https://api.MiniMax.chat/v1)
    LLM_API_KEY    API key
    LLM_MODEL      model name (default: MiniMax-M3)
"""

import argparse
import json
import os
import random
import re
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
# Constants
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
QUIZZES_DIR = SCRIPT_DIR / "quizzes"
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "_generation_log.db"
TAGS_PATH = DATA_DIR / "tags.json"

CATEGORIES = ["match", "which", "type", "how", "hidden",
              "whatwould", "pick", "future"]

MBTI_LETTERS = ["E", "I", "S", "N", "T", "F", "J", "P"]
MBTI_TYPES = ["ENTJ", "ENTP", "ENFJ", "ENFP",
              "ESTJ", "ESTP", "ESFJ", "ESFP",
              "INTJ", "INTP", "INFJ", "INFP",
              "ISTJ", "ISTP", "ISFJ", "ISFP"]

# 8 category meta: (id, type_zh, type_en, description)
CATEGORY_META = {
    "match":     "Match / Soulmate",
    "which":     "Which X Are You",
    "type":      "What's Your Type",
    "how":       "How Adjective Are You",
    "hidden":    "Hidden / Secret",
    "whatwould": "What Would You Do",
    "pick":      "Pick One / Choose",
    "future":    "Future / Destiny",
}

# Banned words by compliance mode.
# Note: We use a list of word fragments that, when found (case-insensitive
# substring) in any text field, are flagged. The postprocess step then
# applies BANNED_WORD_REPLACEMENTS regex patterns to scrub them.
BANNED_WORDS = {
    "light":  ["Official", "Official Test", "Canon", "Endorsed",
               "Lore Accurate", "Authorized", "Real ", "Authentic",
               "Original Licensed", "From the creators of"],
    "medium": ["Official", "Official Test", "Canon", "Endorsed",
               "Lore Accurate", "Authorized", "Authentic",
               "Original Licensed"],
    "strict": ["Official", "Official Test", "Canon", "Endorsed",
               "Lore Accurate", "Authorized", "Authentic",
               "Original Licensed", "Inspired by"],
}

REQUIRED_PHRASES = {
    "light":  ["fan quiz", "for entertainment"],
    "medium": ["fan quiz", "for entertainment", "inspired by"],
    "strict": ["fan quiz", "for entertainment", "inspired by",
               "not affiliated"],
}

# Tag color palette for new tags
TAG_COLORS = ["#FF6B9D", "#A259FF", "#00C2A8", "#FFA94D", "#4DABF7",
              "#FFD43B", "#9775FA", "#63E6BE", "#FF8787", "#69DB7C"]

# Deterministic 12-question layout: each letter appears exactly 6 times,
# each question has 4 unique letters. LLM is told to USE THIS EXACT TABLE
# for score assignment (only change question/option text).
SAMPLE_QUESTION_LETTERS = [
    ["E", "I", "S", "N"],   # Q1
    ["T", "F", "J", "P"],   # Q2
    ["E", "I", "T", "F"],   # Q3
    ["S", "N", "J", "P"],   # Q4
    ["E", "I", "S", "J"],   # Q5
    ["N", "T", "F", "P"],   # Q6
    ["E", "N", "T", "J"],   # Q7
    ["I", "S", "F", "P"],   # Q8
    ["E", "I", "T", "P"],   # Q9
    ["S", "N", "F", "J"],   # Q10
    ["E", "S", "F", "J"],   # Q11
    ["I", "N", "T", "P"],   # Q12
]
SCORE_TABLE_STR = "\n".join(
    f"  Q{i+1:>2}: " + "  ".join(letters)
    for i, letters in enumerate(SAMPLE_QUESTION_LETTERS)
)


# ============================================================
# SQLite logging
# ============================================================
def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS generation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        category TEXT NOT NULL,
        compliance_mode TEXT NOT NULL,
        quiz_id TEXT,
        file_path TEXT,
        status TEXT NOT NULL,
        score_distribution TEXT,
        mbti_coverage TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0,
        retry_count INTEGER DEFAULT 0,
        error_msg TEXT,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        validated_at TIMESTAMP,
        promoted_at TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tag_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generation_id INTEGER,
        new_tag TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn


def log_generation(conn, **kwargs) -> int:
    cols = ["topic", "category", "compliance_mode", "quiz_id",
            "file_path", "status", "score_distribution", "mbti_coverage",
            "prompt_tokens", "completion_tokens", "cost_usd",
            "retry_count", "error_msg"]
    vals = [kwargs.get(c) for c in cols]
    placeholders = ",".join(["?"] * len(cols))
    c = conn.cursor()
    c.execute(f"INSERT INTO generation_log ({','.join(cols)}) VALUES ({placeholders})", vals)
    conn.commit()
    return c.lastrowid


def log_new_tag(conn, generation_id: int, tag: str):
    c = conn.cursor()
    c.execute("INSERT INTO tag_log (generation_id, new_tag) VALUES (?, ?)",
              (generation_id, tag))
    conn.commit()


# ============================================================
# Tag library
# ============================================================
def load_tag_lib(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tag_lib(path: Path, lib: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)


def get_all_tag_names(lib: dict) -> list:
    """Flatten all tag names from the nested structure."""
    names = []
    for _cat, tags in lib.items():
        if isinstance(tags, dict):
            names.extend(tags.keys())
    return names


def add_tag_if_missing(lib: dict, tag: str) -> bool:
    """Add a new tag to a sensible category. Returns True if added."""
    tag = tag.strip()
    if not tag:
        return False
    existing = get_all_tag_names(lib)
    if tag in existing:
        return False

    # Decide which category to put it in
    cat = "Other"
    tag_l = tag.lower()
    if any(k in tag_l for k in ["swift", "drake", "bieber", "music", "kpop",
                                 "k-pop", "song", "singer", "band"]):
        cat = "Music"
    elif any(k in tag_l for k in ["marvel", "harry", "disney", "show",
                                   "movie", "series", "anime", "film"]):
        cat = "Movies & TV"
    elif any(k in tag_l for k in ["genshin", "game", "minecraft", "pokemon",
                                   "roblox", "zelda", "fortnite"]):
        cat = "Games"
    elif any(k in tag_l for k in ["mbti", "trait", "personality", "soulmate",
                                   "future", "aesthetic", "love language"]):
        cat = "Personality"
    elif any(k in tag_l for k in ["travel", "food", "fashion", "lifestyle"]):
        cat = "Lifestyle"
    elif any(k in tag_l for k in ["star wars", "lotr", "doctor who", "stranger"]):
        cat = "Movies & TV"

    if cat not in lib:
        lib[cat] = {}
    lib[cat][tag] = [tag]
    return True


# ============================================================
# Quiz ID allocation
# ============================================================
def get_next_quiz_ids(quizzes_dir: Path, count: int) -> list:
    """Get next N contiguous quiz IDs based on existing files."""
    max_id = 0
    if quizzes_dir.exists():
        for f in quizzes_dir.glob("quiz_*.json"):
            m = re.match(r"quiz_(\d+)\.json", f.name)
            if m:
                n = int(m.group(1))
                if n > max_id:
                    max_id = n
    return [max_id + i + 1 for i in range(count)]


def get_max_quiz_id(quizzes_dir: Path) -> int:
    """Get current max quiz ID, or 0 if none."""
    max_id = 0
    if quizzes_dir.exists():
        for f in quizzes_dir.glob("quiz_*.json"):
            m = re.match(r"quiz_(\d+)\.json", f.name)
            if m:
                n = int(m.group(1))
                if n > max_id:
                    max_id = n
    return max_id


# ============================================================
# Prompt building
# ============================================================
CATEGORY_TITLE_TEMPLATE = {
    "match":     "Which {topic} member/character is your perfect {relation}?",
    "which":     "Which {topic} vibe matches your personality?",
    "type":      "What's your {topic} personality type?",
    "how":       "How {topic} are you?",
    "hidden":    "What's your hidden {topic} trait?",
    "whatwould": "What would you do in the {topic} universe?",
    "pick":      "Which {topic} would you pick?",
    "future":    "What does your {topic} future look like?",
}

CATEGORY_RESULT_GUIDANCE = {
    "match": (
        "16 results. Each is a relationship archetype tied to an IP character/member. "
        "MIX 3 patterns for variety: "
        "(a) 'Pure {Member} - Your {Relation} Match' (b) '{Member} + {Member}: {Relation} Duo' "
        "(c) 'The {Adjective} {Relation} Soul' (archetype). "
        "If IP has 4 members, you MUST use all 4 as 'pure' results at least once, "
        "then add 2-member blends. For the remaining slots, use archetype names. "
        "Relations: Best Friend, Work Partner, Soulmate, Rival, Mentor, Creative Partner, "
        "Adventure Buddy, Confidant, etc."
    ),
    "which": (
        "16 results. MIX 3 patterns for variety: "
        "(a) 'Pure {Member} {Trait} Energy' (e.g., 'Pure Jennie Boss Energy') "
        "(b) '{Member} + {Member}: {Vibe}' (e.g., 'Lisa + Jennie: Stage Fire') "
        "(c) 'The {Adjective} {Noun}' archetype (e.g., 'The Midnight Listener'). "
        "If IP has 4 members, use each member at least twice across pure and blend patterns. "
        "Aim for 4-6 IP names appearing, rest as archetypes. "
        "Example outputs: 'Pure Jennie Boss Energy', 'Lisa + Jennie: Stage Fire', "
        "'The Midnight Listener', 'The Golden Hour Dreamer'."
    ),
    "type": (
        "16 personality type results themed around the IP. "
        "Pattern: 'The {Adjective} {Noun}' (e.g., 'The Bold Rebel', 'The Silent Observer'). "
        "You may also use: '{Member} {Type} Energy' or 'A {Member}-like {Archetype}'. "
        "Each must be distinct and IP-flavored."
    ),
    "how": (
        "16 results = 16 degrees of the trait. "
        "Pattern: '{Degree} {Topic} ({Subtype})' (e.g., 'The Legendary Dancer', "
        "'The Strong Dancer', 'The Hidden Dancer', 'The Aspiring Dancer'). "
        "Cover 4 degrees (legendary/strong/hidden/aspiring) x 4 subtypes. "
        "Subtypes can reference IP members: 'Lisa-level', 'Jennie-level', etc."
    ),
    "hidden": (
        "16 hidden trait results. "
        "Pattern: '{Trait Name} Soul', 'The {Trait} Heart', or '{Member}-like {Trait}'. "
        "Examples: 'The Quiet Storm', 'The Hidden Healer', 'The Secret Dreamer', "
        "'Lisa-like Free Spirit', 'Jennie-like Quiet Power'."
    ),
    "whatwould": (
        "16 action archetypes. Pattern: 'The One Who {Action}'. "
        "You may also use: '{Member} Would {Action}' or '{Member}-style {Action}'. "
        "Examples: 'The One Who Speaks Last', 'The One Who Dances Alone', "
        "'Lisa Would Light Up the Room', 'Jennie Would Command the Stage'."
    ),
    "pick": (
        "16 preference buckets. Pattern: 'The {Preference} Picker'. "
        "Can also be: '{Member}-style {Choice}' or 'You'd Pick Like {Member}'. "
        "Each captures a distinct taste/choice pattern."
    ),
    "future": (
        "16 future life archetypes. "
        "Pattern: 'The {Future Role} of Tomorrow' or '{Future Descriptor} Future'. "
        "Can also be: '{Member}-like Future {Role}'. "
        "Examples: 'The Quiet Performer of Tomorrow', 'Jennie-like Boss Era', "
        "'The World Changer Path'."
    ),
}

CATEGORY_QUESTION_GUIDANCE = {
    "match":     "Frame questions as: 'In a [situation], who do you turn to?' or 'Your ideal [relation] is...' 4 options test compatibility.",
    "which":     "Frame questions as: 'When [situation], you would...' 4 options are 4 different IP members/archetypes.",
    "type":      "Frame questions as: 'In your daily [context], you tend to...' 4 options are 4 personality types.",
    "how":       "Frame questions as: 'How often do you [behavior]?' 4 options measure intensity.",
    "hidden":    "Frame questions as: 'When no one is watching, you...' 4 options reveal hidden traits.",
    "whatwould": "Frame questions as: 'If you faced [scenario], what would you do?' 4 options are 4 action choices.",
    "pick":      "Frame questions as: 'You must pick one: [option] or [option]?' 4 options are 4 choices.",
    "future":    "Frame questions as: 'In 10 years, you see yourself...' 4 options are 4 future paths.",
}

CATEGORY_TITLE_REALNAME = {
    "match":     False,  # "your perfect best friend" - keep generic
    "which":     True,
    "type":      False,
    "how":       False,
    "hidden":    False,
    "whatwould": False,
    "pick":      False,
    "future":    False,
}

CATEGORY_TITLE_GENERIC = {
    "match":     "Which {topic} soul matches yours?",
    "which":     "Which {topic} vibe matches your personality?",
    "type":      "What's your {topic} personality type?",
    "how":       "How {topic} are you, really?",
    "hidden":    "What's your hidden {topic} trait?",
    "whatwould": "What would you do in the {topic} world?",
    "pick":      "Which {topic} would you pick?",
    "future":    "What does your {topic} future hold?",
}


def build_prompt(topic: str, category: str, compliance_mode: str,
                 existing_tags: list) -> str:
    """Build the full LLM prompt for one quiz."""
    title_template = CATEGORY_TITLE_GENERIC[category]
    question_guidance = CATEGORY_QUESTION_GUIDANCE[category]
    result_guidance = CATEGORY_RESULT_GUIDANCE[category]
    type_en = CATEGORY_META[category]
    required_phrases = REQUIRED_PHRASES[compliance_mode]
    banned_words = BANNED_WORDS[compliance_mode]

    # Compliance-specific title pattern
    if compliance_mode == "light":
        title_pattern = (
            f'Title pattern: "{title_template.format(topic=topic)}" '
            '(uses topic name, no "Official" or "Canon" framing)'
        )
    elif compliance_mode == "medium":
        title_pattern = (
            f'Title pattern: avoid direct topic name in title. '
            f'Use: "What Your {topic} Energy Says About You" or '
            f'"{topic} Vibe Personality Quiz"'
        )
    else:  # strict
        title_pattern = (
            f'Title pattern: NO topic name in title. '
            f'Use: "Fan Personality Quiz Inspired by {topic}\'s Public Persona" '
            f'or "What\'s Your Vibe? (Inspired by {topic})"'
        )

    result_naming = (
        f"Result naming: real names allowed (e.g., '{topic} member name') "
        f"but MUST use 'Inspired by' framing or just the name without "
        f"'Official'/'Canon' prefix. Format: '{{Name}} - {{Archetype}}'"
        if compliance_mode == "light"
        else f"Result naming: prefer archetype names (e.g., 'The Bold Leader') "
             f"over direct member/character names. Only use real names if "
             f"framed as 'Inspired by'."
        if compliance_mode == "medium"
        else f"Result naming: NEVER use real member/character names. "
             f"Use generic archetype names only (e.g., 'The Explorer', "
             f"'The Charmer', 'The Rebel')."
    )

    tag_section = (
        f"Use these existing tags if applicable: {', '.join(existing_tags[:30])}.\n"
        f"Add 3-5 tags total. New tags must be objective (no year, no 'viral', "
        f"no 'trending'). If you need a new tag, propose it in the JSON's 'tags' "
        f"array; the script will auto-append it to the library."
    )

    compliance_section = f"""
VII. COMPLIANCE RULES (mode = {compliance_mode})
1. BANNED WORDS in title/results/description: {', '.join(banned_words)}
2. REQUIRED phrases in description: must include ALL of: {', '.join(required_phrases)}
3. {title_pattern}
4. {result_naming}
5. The phrases "fan quiz", "for entertainment", "for entertainment purposes",
   "this is a fan quiz", and "not affiliated" must appear ONLY in
   quiz.description (the top-level field). They are FORBIDDEN inside
   any result.title or result.description.
6. NEVER claim affiliation, endorsement, or canon status.
7. All 4 option texts per question must NOT directly name MBTI dimensions
   (no 'practical/creative/social/private/emotional/logical/structured/flexible').
   Use scenario/behavior/feeling descriptions instead.
8. "real" / "Real" word usage — be careful but do not over-correct:
   * AVOID in claims of authenticity: "the real you", "real connection",
     "real spark", "real self", "real fan", "feels real", "truly real".
     Use "true", "genuine", "honest", "sincere", or rephrase.
   * ALLOWED in common English phrases: "real-world", "real-life",
     "real-fan", "real experience", "real life", "real world". These
     are everyday phrases, not authenticity claims. Do NOT replace
     them with awkward substitutes like "True-world" or "true-life" —
     just use them naturally.
""".strip()

    prompt = f"""You are a professional MBTI personality quiz author.
Generate a "{type_en}" type quiz for topic "{topic}".

I. CATEGORY (固定)
- Type: {type_en}
- Topic: {topic}
- Format: 12 questions, 4 options per question, 16 MBTI results.

II. QUESTIONS (核心)
- 12 questions, each with 4 options.
- {question_guidance}
- Every question MUST be set in an IP-specific scenario. Generic scenarios
  like "group project", "party", "work meeting" are FORBIDDEN.
- Use IP-specific settings: concerts, backstage, dance practice, fan signs,
  music video shoots, song lyrics, fan theories, era aesthetics, etc.
- Each option's "score" must be one of: E, I, S, N, T, F, J, P
- Across 12 questions × 4 options = 48 score slots:
  * Each of E, I, S, N, T, F, J, P must appear EXACTLY 6 times.
  * Within each question, the 4 options MUST have 4 DIFFERENT letters.
- USE THIS EXACT SCORE TABLE (do not modify which letter goes in which question):
{SCORE_TABLE_STR}
  Example: For Q1, your 4 options must use scores [E, I, S, N] in some order.
  For Q5, your scores must be [E, I, S, J]. You can shuffle WITHIN the question,
  but do not change the SET of letters for that question.
- Option ORDER will be force-shuffled by the script later. Do not try to control it.
- DO NOT directly expose dimensions. Use scenario/behavior/feeling language.
  BAD: "practical" / "creative" / "social" / "logical"
  GOOD: "Stick to proven methods" / "Try a brand new approach" / etc.

III. RESULTS (16 个 MBTI 1:1)
{result_guidance}
- 16 results, each tied to a unique MBTI type.
- MBTI types (use all 16, each once): {', '.join(MBTI_TYPES)}
- Each result has: title (concise, distinct), description (40-100 words, IP-flavored, vivid), mbti (one of the 16).
- Title should be 2-6 words. Use the pattern "{{Name}} - {{Archetype}}" or pure archetype.

- CRITICAL — IP-FLAVOR REQUIREMENT:
  * Each description MUST reference at least 2-3 specific IP elements: song
    titles, album names, era names, iconic moments, signature looks, well-
    known catchphrases, member-specific traits.
  * Generic descriptions like "natural performer", "commanding presence",
    "thrives in the spotlight" are FORBIDDEN — they fit any celebrity.
  * Example for BLACKPINK: "Your quiet side mirrors Jennie's cat-eye composure
    from her SOLO era" beats "You have a quiet, mysterious side".
  * Example for Harry Potter: "Your ambition echoes young Tom Riddle's diary
    phase" beats "You are ambitious and goal-oriented".

- CRITICAL — SENTENCE-OPENING VARIETY (no template fatigue):
  * Across 16 results, use AT LEAST 5 DIFFERENT opening patterns. NOT
    all results should start with "You have..." or "Your ... is...".
  * The pattern "Like [Member]'s [era], you [trait]" / "much like [Member]
    in [era]" must NOT appear in more than 3 of 16 results.
  * Here are 8+ distinct opening patterns to mix and match:
    (a) Direct "You" statement: "You light up a room with quiet confidence."
    (b) Song/era metaphor: "BORN PINK is your default state — bold,
        unapologetic, instantly recognizable."
    (c) Verb-led action: "Walking on stage, you channel an energy that
        demands attention."
    (d) Member reference: "Lisa's LALISA confidence runs through you, from
        how you dress to how you carry a conversation."
    (e) "When..." scenario: "When the music drops, you become someone else
        entirely."
    (f) Lyric echo: "Like the chorus of 'Shut Down' says — you don't
        play by anyone else's rules."
    (g) Contrast opener: "Quiet on the outside, but inside you're running
        a full production."
    (h) Fan-coded frame: "Hardcore fans would point at you and say 'that's
        a [era/role] kind of energy.'"
  * DISTRIBUTE these patterns across the 16 results. Count them as you go.

- CRITICAL — I-DOMINANT TYPES MUST BE DISTINCT:
  * The 8 I-dominant MBTI types (INTJ, INTP, INFJ, INFP, ISTJ, ISTP,
    ISFJ, ISFP) are NOT all "quiet observers". Each has a specific
    signature:
    - INTJ = strategic mastermind, long-game thinker, big-picture planner
    - INTP = abstract theorist, curious about how things work, ideas-first
    - INFJ = quietly empathetic, reads people deeply, idealistic but reserved
    - INFP = deeply feeling, poetic, value-driven, internal romantic
    - ISTJ = reliable executor, discipline, tradition, duty-focused
    - ISTP = hands-on problem-solver, action over words, mechanical thinker
    - ISFJ = nurturing caretaker, remembers the details, loyal to the core
    - ISFP = artist in the moment, aesthetic-driven, gentle but fierce
  * Do NOT make every I-type "quiet", "deep", "introspective", or
    "observes from the sidelines". The 8 I-types must read as 8
    different people.

- CRITICAL — NO DISCLAIMER IN RESULT DESCRIPTIONS:
  * Result descriptions must NEVER contain any of: "fan quiz",
    "for entertainment", "for entertainment purposes", "this is a fan",
    "not affiliated", "inspired by" (as a disclaimer), or the phrase
    "This is a fan quiz for entertainment purposes only" in any form.
  * These phrases live EXCLUSIVELY in the top-level quiz.description
    field. They are FORBIDDEN inside any result.title or
    result.description.
  * If a result reads like it needs a "this is just a fan thing"
    disclaimer, rephrase the IP reference instead of adding a
    disclaimer.

IV. TAGS
{tag_section}

V. TITLE
- {title_pattern}
- Language: English, Western quiz tone.
- Length: 6-12 words.

VI. DESCRIPTION (quiz.description, NOT result descriptions)
- 1-2 sentences. English. Include "fan quiz" and "for entertainment".
- Pattern: "Answer 12 questions to discover your [topic]-inspired [category]!"
- End with: "This is a fan quiz for entertainment purposes only."
- This is the ONLY place the disclaimer appears. The phrases "fan quiz"
  and "for entertainment" must NOT appear in any result.title or
  result.description. Re-read result descriptions before submitting
  and remove any disclaimer text.

VII. COMPLIANCE
{compliance_section}

VIII. OUTPUT FORMAT
Output ONLY a single valid JSON object. No commentary, no markdown, no code fences.
The JSON must have this exact structure (numbers may vary):
{{
  "quizId": 999,
  "title": "...",
  "category": "{category}",
  "tags": ["tag1", "tag2", "tag3"],
  "description": "...",
  "questions": [
    {{"qId": 1, "text": "...", "options": [
      {{"text": "...", "score": "E"}},
      {{"text": "...", "score": "I"}},
      {{"text": "...", "score": "S"}},
      {{"text": "...", "score": "N"}}
    ]}},
    ... 11 more questions
  ],
  "results": [
    {{"title": "...", "description": "..." (70-112 words), "mbti": "ENTJ"}},
    ... 15 more results
  ]
}}

REMINDER:
- 12 questions × 4 options = 48 scores, each letter 6 times.
- 16 results, each MBTI used exactly once.
- DO NOT include any text outside the JSON. No markdown fences. No commentary.
- BEFORE SUBMITTING, re-check: NO result.title or result.description
  contains "fan quiz", "for entertainment", "for entertainment purposes",
  "this is a fan", "not affiliated", or "True-world". The disclaimer
  lives ONLY in quiz.description.
- 16 result descriptions should use AT LEAST 5 different sentence-opening
  patterns (not all "You have..." or "Like [Member]...").
- The 8 I-dominant results must each be distinct (not all "quiet observer").
"""
    return prompt


# ============================================================
# LLM call
# ============================================================
def call_llm(prompt: str, max_retries: int = 3,
             base_url: str = None, api_key: str = None,
             model: str = None) -> tuple[str, int, int]:
    """Call LLM via OpenAI-compatible chat completions API.
    Returns (content, prompt_tokens, completion_tokens)."""
    base_url = base_url or os.environ.get("LLM_BASE_URL", "").rstrip("/")
    api_key = api_key or os.environ.get("LLM_API_KEY", "")
    model = model or os.environ.get("LLM_MODEL", "MiniMax-M3")

    if not base_url or not api_key:
        raise RuntimeError(
            "LLM_BASE_URL and LLM_API_KEY must be set. "
            "See .env.example for setup.")

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a quiz author. Output ONLY valid JSON. No commentary, no markdown."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 8000,
        # DeepSeek supports this; OpenAI also does; others will ignore it.
        "response_format": {"type": "json_object"},
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return (content, usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0))
        except (urllib.error.URLError, urllib.error.HTTPError,
                KeyError, json.JSONDecodeError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{max_retries}] {type(e).__name__}: {e}. "
                  f"Sleep {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")


# ============================================================
# JSON parsing (strip code fences, find JSON object)
# ============================================================
def parse_llm_json(content: str) -> dict:
    """Parse JSON from LLM output, stripping code fences and chatter."""
    text = content.strip()

    # Strip code fences ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)

    # Find first { and last } for safety
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM output")
    text = text[start:end + 1]

    return json.loads(text)


# ============================================================
# Post-processing (soft fixes that don't re-call LLM)
# ============================================================
BANNED_WORD_REPLACEMENTS = [
    # (pattern, replacement) — case-insensitive (re.IGNORECASE flag is set)
    # Use \w* suffix to also catch -ity, -ly, -al, -ation, etc.
    (r"\bauthentic\w*", "true-to-you"),
    (r"\bofficial\w*", ""),
    (r"\bcanon\w*", "iconic"),
    (r"\bendors\w*", "inspir"),
    (r"\blore[\s-]accurate", "vibe-accurate"),
    (r"\bauthoriz\w*", "them"),
    # Compound-word handling FIRST so they don't get partially replaced
    # by the standalone "Real" rule below.
    (r"\bReal[\s-]time\b", "Live-time"),
    (r"\breal[\s-]time\b", "live-time"),
    (r"\bReal[\s-]life\b", "Real-life"),
    (r"\breal[\s-]life\b", "real-life"),
    # Standalone "Real" as adjective (e.g., "Real connection", "Real fans",
    # "a real spark"). Use negative look-around for letters/hyphens so
    # we DON'T touch compound words like "Real-time" (already handled)
    # or suffixes like "Realistic", "Realize", "surreal".
    (r"(?<![A-Za-z\-])Real(?![A-Za-z\-])", "True"),
    (r"\boriginal[\s-]licensed", "themed"),
    (r"\bfrom the creators of\b", "inspired by"),
    # LLM over-correction guard: revert "True-world", "true-life", etc.
    # to natural English. These are LLM's self-substitutes for allowed
    # "real-world" / "real-life" phrases and sound robotic.
    (r"\b[Tt]rue[\s-]world\b", "real-world"),
    (r"\b[Tt]rue[\s-]life\b", "real-life"),
    (r"\b[Tt]rue[\s-]fan(s)?\b", r"longtime fan\1"),
    (r"\b[Tt]rue[\s-]self\b", "true self"),
    (r"\b[Tt]rue[\s-]feel(s|ing)?\b", r"true feel\1"),
]

# Disclaimer phrases that must NEVER appear inside result.title or
# result.description. If found, the post-processor strips them.
RESULT_DISCLAIMER_PATTERNS = [
    r"\.?\s*This is a fan quiz for entertainment purposes only\.?\s*$",
    r"\.?\s*This is a fan quiz\s*\.?\s*$",
    r"\.?\s*This is for entertainment purposes only\.?\s*$",
    r"\.?\s*Fan quiz for entertainment purposes only\.?\s*$",
    r"\.?\s*\(Fan quiz[^)]*\)\.?\s*$",
    r"\.?\s*This fan quiz is for entertainment\.?\s*$",
    r"\.?\s*This is a fan[- ]made quiz\.?\s*$",
]

# Whitespace / typography cleanup
WHITESPACE_FIX = [
    (r"[ \t]{2,}", " "),         # collapse multi-space
    (r"\n[ \t]+", "\n"),         # strip indent on newlines
    (r"[ \t]+\n", "\n"),         # strip trailing ws on lines
]


def postprocess_quiz(quiz: dict, _compliance_mode: str = "light") -> tuple[dict, list]:
    """Apply soft fixes. Returns (fixed_quiz, list_of_fixes_applied).
    _compliance_mode is reserved for future per-mode adjustments."""
    fixes = []

    def fix_whitespace(s: str) -> str:
        new = s
        for pattern, repl in WHITESPACE_FIX:
            new = re.sub(pattern, repl, new)
        return new.strip()

    def strip_disclaimer(s: str) -> str:
        """Strip disclaimer sentences that should only live in quiz.description.
        If stripping leaves a string without trailing punctuation, add a period."""
        new = s.rstrip()
        for pattern in RESULT_DISCLAIMER_PATTERNS:
            new2 = re.sub(pattern, "", new, flags=re.IGNORECASE | re.DOTALL)
            if new2 != new:
                new = new2.strip()
        # Restore trailing punctuation if lost
        if new and new[-1] not in '.!?':
            new = new + "."
        return new

    # 0) Whitespace / typography fix FIRST (so the rest of the regexes
    #    see clean text, e.g. no double-space "Real  fan" pattern).
    def clean_text(s: str) -> str:
        new = fix_whitespace(s)
        # Banned-word replacements
        for pattern, repl in BANNED_WORD_REPLACEMENTS:
            new2 = re.sub(pattern, repl, new, flags=re.IGNORECASE)
            if new2 != new:
                new = new2
        return new

    if "title" in quiz and isinstance(quiz["title"], str):
        old = quiz["title"]
        quiz["title"] = clean_text(old)
        if quiz["title"] != old:
            fixes.append("cleaned/normalized quiz.title")

    if "description" in quiz and isinstance(quiz["description"], str):
        old = quiz["description"]
        quiz["description"] = clean_text(old)
        if quiz["description"] != old:
            fixes.append("cleaned/normalized quiz.description")

    # Results: clean text AND strip disclaimer (the disclaimer fix is
    # separate so we can label it clearly in the fix log).
    for i, r in enumerate(quiz.get("results", [])):
        for tk in ["title", "description"]:
            if tk in r and isinstance(r[tk], str):
                old = r[tk]
                cleaned = clean_text(old)
                cleaned = strip_disclaimer(cleaned)
                r[tk] = cleaned
                if r[tk] != old:
                    fixes.append(f"cleaned/normalized result {i+1}.{tk}")

    # Questions / options: just clean (no disclaimer stripping — questions
    # can use "fan quiz" / "for entertainment" contextually).
    for qi, q in enumerate(quiz.get("questions", [])):
        if "text" in q and isinstance(q["text"], str):
            old = q["text"]
            q["text"] = clean_text(old)
            if q["text"] != old:
                fixes.append(f"cleaned/normalized question {qi+1}")
        for oi, o in enumerate(q.get("options", [])):
            if "text" in o and isinstance(o["text"], str):
                old = o["text"]
                o["text"] = clean_text(old)
                if o["text"] != old:
                    fixes.append(f"cleaned/normalized Q{qi+1} option {oi+1}")

    # 2) Trim result descriptions if too long (> 112 words).
    # Do NOT pad short ones — let validation retry handle that with feedback,
    # so LLM writes naturally instead of getting frankensteined with filler.
    for i, r in enumerate(quiz.get("results", [])):
        desc = r.get("description", "")
        words = desc.split()
        wc = len(words)
        if wc > 112:
            r["description"] = " ".join(words[:112])
            fixes.append(f"trimmed result {i+1} description from {wc} to 112 words")

    # 2b) Pad descriptions that are slightly short (35-39 words) with an
    # IP-flavored closing phrase. This is a soft fix for the 1-2 word
    # underrun problem where the LLM writes 39 words instead of 40.
    for i, r in enumerate(quiz.get("results", [])):
        desc = r.get("description", "")
        wc = len(desc.split())
        if 30 <= wc < 40:
            # Append a natural closing sentence that fits the result's
            # tone. Keep it generic enough to apply to any IP result.
            padding_choices = [
                "You bring your own color to the story, every single time.",
                "It's a presence that stays long after the lights go down.",
                "That energy is unmistakably, refreshingly yours.",
                "No one else carries quite the same signature you do.",
                "It's the kind of presence that quietly turns heads.",
            ]
            import random as _r
            r["description"] = desc.rstrip(".") + ". " + _r.choice(padding_choices)
            fixes.append(f"padded result {i+1} description from {wc} to {len(r['description'].split())} words")

    return quiz, fixes


# ============================================================
# Validation
# ============================================================
def validate_quiz(quiz: dict, compliance_mode: str,
                  existing_tags: set) -> tuple[bool, str, dict]:
    """Validate a generated quiz. Returns (valid, error_msg, stats)."""
    # Required top-level keys
    for key in ("quizId", "title", "category", "tags", "description",
                "questions", "results"):
        if key not in quiz:
            return False, f"Missing key: {key}", {}

    # 12 questions
    qs = quiz["questions"]
    if len(qs) != 12:
        return False, f"Need 12 questions, got {len(qs)}", {}

    # 4 options per question
    all_scores = []
    for i, q in enumerate(qs):
        opts = q.get("options", [])
        if len(opts) != 4:
            return False, f"Q{i+1}: need 4 options, got {len(opts)}", {}
        scores = []
        for o in opts:
            s = o.get("score", "")
            if s not in MBTI_LETTERS:
                return False, f"Q{i+1}: invalid score '{s}'", {}
            scores.append(s)
        if len(set(scores)) != 4:
            return False, f"Q{i+1}: scores must be 4 different letters, got {scores}", {}
        all_scores.extend(scores)

    # Score distribution: each letter exactly 6 times
    from collections import Counter
    dist = Counter(all_scores)
    for letter in MBTI_LETTERS:
        if dist[letter] != 6:
            return False, (f"Score distribution: {letter} appears "
                           f"{dist[letter]} times, need 6"), {}

    # 16 results
    rs = quiz["results"]
    if len(rs) != 16:
        return False, f"Need 16 results, got {len(rs)}", {}

    mbtis = []
    for i, r in enumerate(rs):
        m = r.get("mbti", "")
        if m not in MBTI_TYPES:
            return False, f"Result {i+1}: invalid MBTI '{m}'", {}
        mbtis.append(m)
    if len(set(mbtis)) != 16:
        return False, (f"MBTI not 1:1 with results. "
                       f"Got: {sorted(mbtis)}"), {}

    # Description word count — relaxed to 35-100 so LLM writes naturally
    # (its natural sweet spot is 40-70 words). Padding to 70+ forced
    # generic filler. The 30-39 range is auto-padded by postprocess.
    for i, r in enumerate(rs):
        desc = r.get("description", "")
        wc = len(desc.split())
        if wc < 35 or wc > 100:
            return False, (f"Result {i+1} description has {wc} words, "
                           f"need 35-100"), {}

    # Compliance: banned words. Use word-boundary regex to avoid false
    # positives on words like "surreal", "realistic", "realize" that
    # happen to contain the banned substring (e.g. "Real " would match
    # "surreal " if we used a plain substring check).
    import re as _re
    title = quiz.get("title", "")
    description = quiz.get("description", "")
    all_text = (title + "\n" + description + "\n" +
                "\n".join(r.get("title", "") for r in rs) + "\n" +
                "\n".join(r.get("description", "") for r in rs))
    for banned in BANNED_WORDS[compliance_mode]:
        # Build a word-boundary pattern. Strip trailing whitespace from the
        # banned phrase first, then escape, then add boundaries.
        b = banned.strip()
        if not b:
            continue
        # Use negative look-around for letters/hyphens to mimic word
        # boundary that includes hyphens (so "Real-time" matches "real"
        # but "surreal" does not).
        pattern = r"(?<![A-Za-z\-])" + _re.escape(b) + r"(?![A-Za-z\-])"
        if _re.search(pattern, all_text, flags=_re.IGNORECASE):
            return False, f"Banned word '{banned}' found", {}

    # Compliance: required phrases — check ONLY in quiz.description, not in
    # result descriptions. Result descriptions should stay clean and IP-flavored.
    quiz_desc_lower = description.lower()
    for req in REQUIRED_PHRASES[compliance_mode]:
        if req.lower() not in quiz_desc_lower:
            return False, f"Required phrase '{req}' missing in quiz.description", {}

    # Disclaimer must NOT appear in result.title or result.description.
    # (Post-processor strips it, but if it slips through, we want to fail
    # loud and have the LLM retry so it learns to stop adding it.)
    for i, r in enumerate(rs):
        for tk in ["title", "description"]:
            val = r.get(tk, "")
            if not isinstance(val, str):
                continue
            for pat in RESULT_DISCLAIMER_PATTERNS:
                if re.search(pat, val, flags=re.IGNORECASE | re.DOTALL):
                    return False, (
                        f"Result {i+1}.{tk} contains disclaimer text that "
                        f"should only be in quiz.description. Remove it."
                    ), {}

    # Validate tags (warn if new, don't fail)
    new_tags = [t for t in quiz.get("tags", []) if t not in existing_tags]
    bad_tags = [t for t in quiz.get("tags", [])
                if any(b in t.lower() for b in ["viral", "trending", "top ",
                                                  "1226", "2024", "2025"])]
    if bad_tags:
        return False, f"Tags contain trend/year words: {bad_tags}", {}

    stats = {
        "score_distribution": dict(dist),
        "mbti_coverage": sorted(mbtis),
        "new_tags": new_tags,
    }
    return True, "", stats


# ============================================================
# Force-shuffle options
# ============================================================
def shuffle_options(quiz: dict) -> None:
    """Randomize option order for each question to break any LLM pattern."""
    for q in quiz["questions"]:
        opts = q["options"]
        random.shuffle(opts)


# ============================================================
# File writing
# ============================================================
def write_quiz_file(quizzes_dir: Path, quiz_id: int,
                    quiz: dict) -> str:
    """Write quiz JSON. Returns file path."""
    quizzes_dir.mkdir(parents=True, exist_ok=True)
    fname = f"quiz_{quiz_id}.json"
    fpath = quizzes_dir / fname
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, indent=2)
    return str(fpath.relative_to(SCRIPT_DIR))


# ============================================================
# Main flow
# ============================================================
def process_one_category(topic: str, category: str,
                         compliance_mode: str,
                         tag_lib: dict, conn,
                         next_ids: list, idx: int,
                         base_url: str, api_key: str,
                         model: str, dry_run: bool) -> dict:
    """Process one (topic, category) combination. Returns result dict."""
    quiz_id_int = next_ids[idx]
    quiz_id_str = f"quiz_{quiz_id_int}"
    existing_tags = get_all_tag_names(tag_lib)

    result = {
        "topic": topic, "category": category,
        "compliance_mode": compliance_mode,
        "quiz_id": quiz_id_str, "file_path": None,
        "status": None, "stats": {},
        "prompt_tokens": 0, "completion_tokens": 0,
        "cost_usd": 0, "retry_count": 0, "error_msg": None,
    }

    if dry_run:
        quiz = make_sample_quiz(topic, category, quiz_id_int)
        result["retry_count"] = 0
    else:
        prompt = build_prompt(topic, category, compliance_mode, existing_tags)
        print(f"  [{idx+1}/{len(next_ids)}] {category:10s} → generating...")

        # Try up to 3 times: each retry includes feedback about what failed
        feedback = ""
        quiz = None
        for attempt in range(3):
            try:
                full_prompt = prompt + feedback
                content, pt, ct = call_llm(full_prompt, max_retries=3,
                                            base_url=base_url,
                                            api_key=api_key, model=model)
                # Accumulate token usage across retries
                result["prompt_tokens"] += pt
                result["completion_tokens"] += ct
                result["cost_usd"] += (pt * 0.14 + ct * 0.28) / 1_000_000
                quiz = parse_llm_json(content)
                result["retry_count"] = attempt

                # Apply post-process (soft fixes)
                quiz, fixes = postprocess_quiz(quiz, compliance_mode)
                if fixes:
                    print(f"    [postprocess attempt {attempt+1}] {len(fixes)} fixes applied")

                # Validate
                existing_tag_set = set(get_all_tag_names(tag_lib))
                valid, err, stats = validate_quiz(quiz, compliance_mode,
                                                   existing_tag_set)
                if valid:
                    result["stats"] = stats
                    result["score_distribution"] = json.dumps(stats["score_distribution"])
                    result["mbti_coverage"] = json.dumps(stats["mbti_coverage"])
                    break  # success
                else:
                    # Build feedback for next retry
                    if attempt < 2:
                        feedback = (
                            f"\n\n=== FEEDBACK FROM PREVIOUS ATTEMPT ===\n"
                            f"Validation failed: {err}\n"
                            f"Please REGENERATE the quiz fixing ONLY this issue. "
                            f"Keep everything else the same.\n"
                        )
                        if "Score distribution" in err:
                            feedback += (
                                "For score distribution: 12 questions x 4 options = 48 "
                                "score slots. Each of E,I,S,N,T,F,J,P must appear EXACTLY 6 "
                                "times. Each question's 4 options must use 4 DIFFERENT letters. "
                                "Count carefully before submitting.\n"
                            )
                        elif "description" in err:
                            feedback += (
                                "For description word count: each of the 16 result "
                                "descriptions must be 70-112 words. Count words and "
                                "adjust length.\n"
                            )
                        elif "disclaimer text" in err:
                            feedback += (
                                "The disclaimer phrase 'This is a fan quiz for "
                                "entertainment purposes only' (and any variant like "
                                "'for entertainment', 'fan quiz', 'this is a fan') "
                                "MUST NOT appear in any result.title or "
                                "result.description. It lives ONLY in the top-level "
                                "quiz.description. Re-read all 16 result "
                                "descriptions and remove any disclaimer-style "
                                "ending. End the description with a vivid IP "
                                "detail instead.\n"
                            )
                        elif "Banned word" in err:
                            # Pull the specific banned word to give targeted feedback
                            banned_word_match = re.search(r"'([^']+)'", err)
                            banned_word = banned_word_match.group(1) if banned_word_match else "the flagged word"
                            feedback += (
                                f"Remove the word '{banned_word}' (and any variant like "
                                f"{banned_word.lower()}/{banned_word.upper()}) and use a "
                                f"compliant alternative. For 'Real'/'real': replace with "
                                f"'true'/'genuine'/'honest' or rephrase. For 'Official'/"
                                f"'Canon'/'Authorized': rephrase to avoid claiming official "
                                f"status. For 'Authentic': rephrase to avoid authenticity claims. "
                                f"NEVER use these words anywhere in title, description, or "
                                f"results.\n"
                            )
                        elif "MBTI" in err:
                            feedback += (
                                "Each of the 16 MBTI types (ENTJ, ENTP, ..., ISFP) must "
                                "appear EXACTLY once across the 16 results.\n"
                            )
                        wait = 2 ** attempt
                        print(f"    [retry {attempt+1}] validation: {err[:60]}... "
                              f"sleep {wait}s")
                        time.sleep(wait)
                    else:
                        # Last attempt failed
                        result["status"] = "FAILED"
                        result["error_msg"] = f"Validation: {err} (after 3 attempts)"
                        result["retry_count"] = 3
                        log_generation(conn, **result)
                        print(f"    ✗ FAILED: {err[:80]}")
                        return result
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    print(f"    [retry {attempt+1}] {type(e).__name__}: {str(e)[:60]}. "
                          f"Sleep {wait}s...")
                    time.sleep(wait)
                else:
                    result["status"] = "FAILED"
                    result["error_msg"] = f"{type(e).__name__}: {e}"
                    result["retry_count"] = 3
                    log_generation(conn, **result)
                    print(f"    ✗ FAILED after 3 retries: {e}")
                    return result

    # 2) Force-shuffle
    shuffle_options(quiz)
    quiz["quizId"] = quiz_id_int  # ensure consistent ID

    # 3) Add new tags
    for new_tag in result["stats"].get("new_tags", []):
        if add_tag_if_missing(tag_lib, new_tag):
            log_new_tag(conn, -1, new_tag)
            print(f"    + new tag: {new_tag}")

    # 4) Write file
    file_path = write_quiz_file(QUIZZES_DIR, quiz_id_int, quiz)
    result["file_path"] = file_path
    result["status"] = "VALIDATED"

    log_generation(conn, **result)
    print(f"    ✓ {file_path}  scores={result['stats']['score_distribution']}")
    return result


def make_sample_quiz(topic: str, category: str, quiz_id: int) -> dict:
    """Build a sample quiz for dry-run / testing.
    Uses deterministic SAMPLE_QUESTION_LETTERS to ensure even distribution."""
    questions = []
    for i, letters in enumerate(SAMPLE_QUESTION_LETTERS):
        order = letters.copy()
        random.shuffle(order)  # randomize option order
        options = [
            {"text": f"Sample option {chr(65+j)} for question {i+1}",
             "score": order[j]}
            for j in range(4)
        ]
        questions.append({
            "qId": i + 1,
            "text": f"Sample question {i+1} about {topic}?",
            "options": options,
        })

    results = []
    for mbti in MBTI_TYPES:
        results.append({
            "title": f"Sample Result {mbti}",
            "description": (f"This is a sample result description for {mbti} "
                            f"in the {category} category about {topic}. "
                            f"It needs to be between 70 and 112 words long to "
                            f"pass validation. " * 3),  # padded to ~85 words
            "mbti": mbti,
        })

    title = CATEGORY_TITLE_GENERIC[category].format(topic=topic)

    return {
        "quizId": quiz_id,
        "title": title,
        "category": category,
        "tags": [topic, "Personality", "MBTI"],
        "description": (f"Answer 12 questions to discover your {topic}-inspired "
                        f"{category}! This is a fan quiz for entertainment "
                        f"purposes only."),
        "questions": questions,
        "results": results,
    }


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="AIGC quiz generator for QuizFig")
    parser.add_argument("--topic", required=True,
                        help="Topic/IP, e.g. 'BLACKPINK'")
    parser.add_argument("--compliance", default="light",
                        choices=["light", "medium", "strict"],
                        help="Compliance mode (default: light)")
    parser.add_argument("--only", default="",
                        help="Comma-separated categories, e.g. 'match,which'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test pipeline without LLM calls")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    # Categories
    if args.only:
        cats = [c.strip() for c in args.only.split(",") if c.strip()]
        for c in cats:
            if c not in CATEGORIES:
                parser.error(f"Unknown category: {c}. "
                             f"Valid: {', '.join(CATEGORIES)}")
    else:
        cats = CATEGORIES.copy()
    n = len(cats)

    # Setup
    random.seed(int(time.time()))
    conn = init_db(DB_PATH)
    tag_lib = load_tag_lib(TAGS_PATH)
    next_ids = get_next_quiz_ids(QUIZZES_DIR, n)

    print(f"\n{'='*60}")
    print(f"  Generate Quiz")
    print(f"  Topic:        {args.topic}")
    print(f"  Compliance:   {args.compliance}")
    print(f"  Categories:   {', '.join(cats)}")
    print(f"  Quiz IDs:     {next_ids[0]} .. {next_ids[-1]}")
    print(f"  Dry run:      {args.dry_run}")
    print(f"  Tags loaded:  {len(get_all_tag_names(tag_lib))}")
    print(f"{'='*60}\n")

    start = time.time()
    results = []
    for i, cat in enumerate(cats):
        r = process_one_category(
            args.topic, cat, args.compliance, tag_lib, conn,
            next_ids, i, args.base_url, args.api_key, args.model,
            args.dry_run)
        results.append(r)

    # Save updated tag lib
    save_tag_lib(TAGS_PATH, tag_lib)

    elapsed = time.time() - start
    ok = sum(1 for r in results if r["status"] == "VALIDATED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    total_tokens = sum(r["prompt_tokens"] + r["completion_tokens"] for r in results)
    total_cost = sum(r["cost_usd"] for r in results)

    print(f"\n{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    print(f"  Total:        {len(results)}")
    print(f"  Validated:    {ok}")
    print(f"  Failed:       {failed}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total cost:   ${total_cost:.4f}")
    print(f"  Elapsed:      {elapsed:.1f}s")
    print(f"  Tag lib size: {len(get_all_tag_names(tag_lib))}")
    print()
    print(f"  Per-category:")
    for r in results:
        marker = "✓" if r["status"] == "VALIDATED" else "✗"
        qid = r["quiz_id"] or "------"
        path = r["file_path"] or r["error_msg"] or ""
        print(f"    {marker} {r['category']:10s} {qid:10s}  {path}")
    print()
    print(f"  DB:   {DB_PATH}")
    print(f"  Tags: {TAGS_PATH}")
    print(f"{'='*60}\n")

    conn.close()


if __name__ == "__main__":
    main()
