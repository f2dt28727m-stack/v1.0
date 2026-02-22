#!/usr/bin/env python3
"""
Tag Management System
Three-level structure: KEY (category) -> Value (normalized tag) -> SubValues (original tags)

Usage: 
  python update_tags.py --scan      # Scan for unknown tags
  python update_tags.py --apply    # Apply normalization to quizzes
  python update_tags.py --list     # List all categories and tags
  python update_tags.py --add "category" "value" "subvalue"  # Add new mapping
"""
import json
import os
import sys
from collections import Counter

TAGS_FILE = 'data/tags.json'
QUIZZES_FILE = 'quizzes.json'

def load_tags():
    with open(TAGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_tags(tags):
    with open(TAGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)

def load_quizzes():
    with open(QUIZZES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_quizzes(quizzes):
    with open(QUIZZES_FILE, 'w', encoding='utf-8') as f:
        json.dump(quizzes, f, ensure_ascii=False, indent=2)

def build_normalization_map():
    """Build reverse mapping: original tag -> (category, normalized value)"""
    tags = load_tags()
    normal_map = {}
    
    for category, values in tags.items():
        for value, subvalues in values.items():
            for sv in subvalues:
                normal_map[sv.lower()] = (category, value)
    
    return normal_map

def scan_unknown_tags():
    """Scan quizzes and find tags not in the library"""
    normal_map = build_normalization_map()
    quizzes = load_quizzes()
    
    all_tags = []
    for q in quizzes.get('quizzes', []):
        all_tags.extend(q.get('tags', []))
    
    # Find unknown tags
    unknown = []
    for tag in set(all_tags):
        if tag.lower() not in normal_map:
            unknown.append(tag)
    
    unknown_counts = Counter()
    for tag in all_tags:
        if tag in unknown:
            unknown_counts[tag] += 1
    
    print(f"\n=== Unknown Tags ===")
    print(f"Found {len(unknown)} unknown tags:\n")
    for tag, count in unknown_counts.most_common(30):
        print(f"  [{count:3d}] {tag}")
    
    return unknown

def apply_normalization():
    """Apply normalized tags to all quizzes"""
    normal_map = build_normalization_map()
    quizzes = load_quizzes()
    
    updated = 0
    for quiz in quizzes.get('quizzes', []):
        old_tags = quiz.get('tags', [])
        new_tags = []
        
        for tag in old_tags:
            result = normal_map.get(tag.lower())
            if result:
                _, value = result
                if value not in new_tags:
                    new_tags.append(value)
            else:
                # Keep original if not found
                if tag not in new_tags:
                    new_tags.append(tag)
        
        quiz['tags'] = new_tags
        if old_tags != new_tags:
            updated += 1
    
    save_quizzes(quizzes)
    print(f"\n=== Normalization Applied ===")
    print(f"Updated {updated}/{len(quizzes.get('quizzes', []))} quizzes")

def list_tags():
    """List all categories and tags"""
    tags = load_tags()
    print(f"\n=== Tag Library ({len(tags)} categories) ===\n")
    
    for category, values in sorted(tags.items()):
        print(f"{category} ({len(values)} tags):")
        for value, subvalues in sorted(values.items()):
            print(f"  - {value}: {', '.join(subvalues[:3])}{'...' if len(subvalues) > 3 else ''}")
        print()

def add_tag(category, value, subvalue):
    """Add a new tag mapping"""
    tags = load_tags()
    
    if category not in tags:
        tags[category] = {}
    if value not in tags[category]:
        tags[category][value] = []
    if subvalue not in tags[category][value]:
        tags[category][value].append(subvalue)
        save_tags(tags)
        print(f"Added: {category} > {value} > {subvalue}")
    else:
        print(f"Already exists: {category} > {value} > {subvalue}")

if __name__ == '__main__':
    if '--scan' in sys.argv:
        scan_unknown_tags()
    elif '--apply' in sys.argv:
        apply_normalization()
    elif '--list' in sys.argv:
        list_tags()
    elif '--add' in sys.argv:
        idx = sys.argv.index('--add')
        if len(sys.argv) > idx + 3:
            add_tag(sys.argv[idx+1], sys.argv[idx+2], sys.argv[idx+3])
        else:
            print("Usage: python update_tags.py --add 'Category' 'Value' 'SubValue'")
    else:
        list_tags()
