#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan all quiz JSON files and categorize by tags[0] into people / non-people."""
import json
import os
from collections import defaultdict

quizzes_dir = 'quizzes'
people = []
non_people = []
seen = set()

for f in sorted(os.listdir(quizzes_dir)):
    if not f.startswith('quiz_') or not f.endswith('.json'):
        continue
    path = os.path.join(quizzes_dir, f)
    try:
        with open(path) as fp:
            data = json.load(fp)
    except Exception:
        continue
    tags = data.get('tags', [])
    if not tags:
        continue
    subject = tags[0]
    title = data.get('title', '')[:80]
    quiz_id = data.get('quizId', f.replace('quiz_', '').replace('.json', ''))
    if subject in seen:
        continue
    seen.add(subject)

    is_person = subject in title
    line = (quiz_id, subject, title, is_person)
    if is_person:
        people.append(line)
    else:
        non_people.append((quiz_id, subject, title))

print('=== REAL PEOPLE (subject appears in title) ===')
unique_people = []
for qid, s, t, _ in sorted(people, key=lambda x: int(str(x[0]))):
    if s not in [u[1] for u in unique_people]:
        unique_people.append((qid, s, t))
        print(f'  quiz_{qid:>4}  {s:<35}  {t}')
print(f'\n  Total real-person quizzes: {len(people)}')
print(f'  Unique real people:        {len(unique_people)}')

print('\n=== NON-PERSON (franchise / generic topic) ===')
seen2 = set()
for qid, s, t in sorted(non_people, key=lambda x: int(str(x[0]))):
    if s in seen2:
        continue
    seen2.add(s)
    print(f'  quiz_{qid:>4}  {s:<35}  {t}')
print(f'\n  Total non-person quizzes: {len(non_people)}')
print(f'  Unique topics:           {len(seen2)}')
