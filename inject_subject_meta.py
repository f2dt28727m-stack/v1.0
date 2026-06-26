#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inject subject_meta into real-person quiz JSON files.
Hedge wording uses "or" between alternate typings.

Rule: writes only if the field doesn't already exist (idempotent).
"""
import json
import os

QUIZZES_DIR = 'quizzes'

# typing_primary  = most-cited MBTI in fan communities (with sources)
# typing_alternate = other commonly-cited typings, joined with "or" in render
# Source notes: see web search results / personality-database votes
SUBJECT_META = {
    'quiz_27.json':  {'pronoun': 'she', 'typing_primary': 'ENFP',  'typing_alternate': 'INFP or INFJ'},   # SZA
    'quiz_37.json':  {'pronoun': 'she', 'typing_primary': 'ESFJ',  'typing_alternate': 'INFP or ISFP'},   # Olivia Rodrigo
    'quiz_53.json':  {'pronoun': 'she', 'typing_primary': 'ENFJ',  'typing_alternate': 'ESFP or INFP'},   # Sabrina Carpenter
    'quiz_100.json': {'pronoun': 'she', 'typing_primary': 'ENFP',  'typing_alternate': 'INFJ or ESFJ'},   # Taylor Swift
    'quiz_152.json': {'pronoun': 'she', 'typing_primary': 'ISFP',  'typing_alternate': 'ESTP'},          # Ice Spice
    'quiz_153.json': {'pronoun': 'she', 'typing_primary': 'ENFJ',  'typing_alternate': 'ESFP or ESTP'},   # Dua Lipa
    'quiz_155.json': {'pronoun': 'she', 'typing_primary': 'ISFP',  'typing_alternate': 'INFP'},          # Billie Eilish
    'quiz_157.json': {'pronoun': 'she', 'typing_primary': 'INFP',  'typing_alternate': 'ISFP or INFJ'},   # Lana Del Rey
    # Groups: list all self-disclosed members
    'quiz_60.json':  {
        'pronoun': 'they',
        'is_group': True,
        'group_name': 'NewJeans',
        'members': {
            'Minji':    'ESTJ',
            'Hanni':    'INFP',
            'Danielle': 'ENFP',
            'Haerin':   'ISTP',
            'Hyein':    'INFP',
        },
    },
    'quiz_164.json': {
        'pronoun': 'they',
        'is_group': True,
        'group_name': 'BLACKPINK',
        'members': {
            'Jisoo': 'ISTP',
            'Jennie': 'INFJ',  # INFP also cited
            'Rosé':  'ENFP',
            'Lisa':  'ISFP',
        },
    },
}


def main():
    for filename, meta in SUBJECT_META.items():
        path = os.path.join(QUIZZES_DIR, filename)
        if not os.path.exists(path):
            print(f'  SKIP (not found): {filename}')
            continue
        with open(path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        if 'subject_meta' in data:
            print(f'  SKIP (already has subject_meta): {filename}')
            continue
        data['subject_meta'] = meta
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        print(f'  OK: {filename}  -> subject_meta injected')


if __name__ == '__main__':
    main()
