#!/usr/bin/env python3
"""
Tag Management System
Usage: python update_tags.py [--scan] [--apply] [--regenerate]
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

def scan_new_tags():
    """Scan quizzes and find tags not in the normalized library"""
    tags_data = load_tags()
    normalized = tags_data.get('normalized_tags', {})
    
    # Flatten normalized tags to get all known tags
    known_tags = set()
    for canonical, variants in normalized.items():
        known_tags.update([v.lower() for v in variants])
    
    quizzes = load_quizzes()
    all_tags = []
    for q in quizzes.get('quizzes', []):
        all_tags.extend(q.get('tags', []))
    
    # Find unknown tags
    unknown_tags = []
    for tag in set(all_tags):
        if tag.lower() not in known_tags:
            unknown_tags.append(tag)
    
    unknown_counts = Counter()
    for tag in all_tags:
        if tag in unknown_tags:
            unknown_counts[tag] += 1
    
    print(f"\n=== Unknown Tags (not in library) ===")
    print(f"Found {len(unknown_tags)} unknown tags:\n")
    for tag, count in unknown_counts.most_common(30):
        print(f"  [{count:3d}] {tag}")
    
    return unknown_tags

def apply_normalization():
    """Apply normalized tags to all quizzes"""
    tags_data = load_tags()
    normalized = tags_data.get('normalized_tags', {})
    
    # Build reverse mapping: variant -> canonical
    variant_to_canonical = {}
    for canonical, variants in normalized.items():
        for variant in variants:
            variant_to_canonical[variant.lower()] = canonical
    
    quizzes = load_quizzes()
    updated = 0
    
    for quiz in quizzes.get('quizzes', []):
        old_tags = quiz.get('tags', [])
        new_tags = []
        
        for tag in old_tags:
            canonical = variant_to_canonical.get(tag.lower(), tag)
            if canonical not in new_tags:
                new_tags.append(canonical)
        
        quiz['tags'] = new_tags
        if old_tags != new_tags:
            updated += 1
    
    save_quizzes(quizzes)
    print(f"\n=== Normalization Applied ===")
    print(f"Updated {updated}/{len(quizzes.get('quizzes', []))} quizzes")

def generate_ui_tags():
    """Generate tag categories for UI"""
    tags_data = load_tags()
    quizzes = load_quizzes()
    
    # Count tags in quizzes
    all_tags = []
    for q in quizzes.get('quizzes', []):
        all_tags.extend(q.get('tags', []))
    
    tag_counts = Counter(all_tags)
    
    # Get categories from tags.json
    categories = tags_data.get('categories', {})
    
    # Add "More" category for tags not in predefined categories
    predefined = set()
    for cat_tags in categories.values():
        predefined.update(cat_tags)
    
    # Add tags that exist in quizzes but not in categories
    extra_tags = [t for t in tag_counts.keys() if t not in predefined]
    if extra_tags:
        categories['More'] = extra_tags[:20]  # Limit to 20
    
    # Only keep tags that actually exist in quizzes
    final_categories = {}
    for cat_name, cat_tags in categories.items():
        existing = [t for t in cat_tags if t in tag_counts]
        if existing:
            final_categories[cat_name] = existing
    
    print(f"\n=== Generated Tag Categories ===")
    for cat, tags in final_categories.items():
        print(f"  {cat}: {len(tags)} tags")
    
    return final_categories

def add_new_tag(raw_tag, canonical_tag):
    """Add a new tag mapping to the library"""
    tags_data = load_tags()
    
    if 'normalized_tags' not in tags_data:
        tags_data['normalized_tags'] = {}
    
    if canonical_tag not in tags_data['normalized_tags']:
        tags_data['normalized_tags'][canonical_tag] = []
    
    if raw_tag not in tags_data['normalized_tags'][canonical_tag]:
        tags_data['normalized_tags'][canonical_tag].append(raw_tag)
        save_tags(tags_data)
        print(f"Added mapping: {raw_tag} -> {canonical_tag}")
    else:
        print(f"Mapping already exists: {raw_tag} -> {canonical_tag}")

if __name__ == '__main__':
    if '--scan' in sys.argv:
        scan_new_tags()
    elif '--apply' in sys.argv:
        apply_normalization()
    elif '--regenerate' in sys.argv:
        generate_ui_tags()
    elif '--add' in sys.argv:
        # Usage: python update_tags.py --add "raw_tag" "canonical_tag"
        idx = sys.argv.index('--add')
        if len(sys.argv) > idx + 2:
            add_new_tag(sys.argv[idx+1], sys.argv[idx+2])
        else:
            print("Usage: python update_tags.py --add 'raw_tag' 'canonical_tag'")
    else:
        print("Usage: python update_tags.py [--scan] [--apply] [--regenerate] [--add raw canonical]")
        print("  --scan: Scan for new tags not in library")
        print("  --apply: Apply normalization to all quizzes")
        print("  --regenerate: Generate UI tag categories")
        print("  --add: Add new tag mapping")
