"""Fix the quizId=1001 corruption across quiz files.

For each file quizzes/quiz_NNN.json whose internal `quizId` does not match
its filename's NNN, set `quizId` to NNN.

Safe-by-default: skips files whose quizId is already correct, skips files
without a parseable numeric id, and reports a summary at the end.
"""

import json
import os
import re
import sys

QUIZ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quizzes")
NAME_RE = re.compile(r"^quiz_(\d+)\.json$")

changed = []
skipped = []
errors = []

for name in sorted(os.listdir(QUIZ_DIR)):
    m = NAME_RE.match(name)
    if not m:
        continue
    expected_id = int(m.group(1))
    full = os.path.join(QUIZ_DIR, name)
    try:
        with open(full, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        errors.append((name, str(e)))
        continue
    actual_id = data.get("quizId")
    if actual_id == expected_id:
        skipped.append((name, "already correct"))
        continue
    if actual_id is None:
        skipped.append((name, "no quizId field"))
        continue
    data["quizId"] = expected_id
    with open(full, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    changed.append((name, actual_id, expected_id))

print(f"Total changed: {len(changed)}")
for name, old, new in changed:
    print(f"  {name}: quizId {old} -> {new}")
print(f"\nSkipped: {len(skipped)}")
if errors:
    print(f"\nErrors: {len(errors)}")
    for n, e in errors:
        print(f"  {n}: {e}")
