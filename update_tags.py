import json
import os

# 收集所有tag
def collect_tags():
    quizzes_dir = 'quizzes'
    all_tags = []
    
    # 遍历quizzes目录中的所有问卷
    for filename in os.listdir(quizzes_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(quizzes_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if 'tags' in data:
                        all_tags.extend(data['tags'])
            except Exception as e:
                print(f'Error loading {filename}: {e}')
    
    # 处理onequiz.json
    try:
        with open('onequiz.json', 'r') as f:
            data = json.load(f)
            if 'tags' in data:
                all_tags.extend(data['tags'])
    except Exception as e:
        print(f'Error loading onequiz.json: {e}')
    
    # 去重并排序
    unique_tags = sorted(list(set(all_tags)))
    
    print('All unique tags:')
    for tag in unique_tags:
        print(f'- {tag}')
    print(f'Total unique tags: {len(unique_tags)}')
    
    return unique_tags

# 合并同类项
def merge_similar_tags(tags):
    # 定义tag映射，将相似的tag映射到标准值
    tag_mapping = {
        '16型人格': 'MBTI',
        '16型': 'MBTI',
        'Personality': 'Personality',
        'personality': 'Personality',
        'MBTI': 'MBTI',
        'mbti': 'MBTI',
        'Disney': 'Disney',
        'disney': 'Disney',
        'Princess': 'Princess',
        'princess': 'Princess',
        'Harry Potter': 'Harry Potter',
        'harry potter': 'Harry Potter',
        'Hogwarts': 'Hogwarts',
        'hogwarts': 'Hogwarts',
        'Wizarding World': 'Wizarding World',
        'wizarding world': 'Wizarding World',
        'Magic': 'Magic',
        'magic': 'Magic',
        'Superhero': 'Superhero',
        'superhero': 'Superhero',
        'Sidekick': 'Sidekick',
        'sidekick': 'Sidekick',
        'Comics': 'Comics',
        'comics': 'Comics',
        'Anime': 'Anime',
        'anime': 'Anime',
        'Character': 'Character',
        'character': 'Character',
        'Love Language': 'Love Language',
        'love language': 'Love Language',
        'Relationships': 'Relationships',
        'relationships': 'Relationships',
        'Love': 'Love',
        'love': 'Love',
        'Emotions': 'Emotions',
        'emotions': 'Emotions',
        'Food': 'Food',
        'food': 'Food',
        'Cooking': 'Cooking',
        'cooking': 'Cooking',
        'Eating': 'Eating',
        'eating': 'Eating',
        'Travel': 'Travel',
        'travel': 'Travel',
        'Adventure': 'Adventure',
        'adventure': 'Adventure',
        'Wanderlust': 'Wanderlust',
        'wanderlust': 'Wanderlust',
        'Career': 'Career',
        'career': 'Career',
        'Work': 'Work',
        'work': 'Work',
        'Success': 'Success',
        'success': 'Success',
        'Music': 'Music',
        'music': 'Music',
        'Sound': 'Sound',
        'sound': 'Sound',
        'Rhythm': 'Rhythm',
        'rhythm': 'Rhythm',
        'Spirit Animal': 'Spirit Animal',
        'spirit animal': 'Spirit Animal',
        'Nature': 'Nature',
        'nature': 'Nature',
        'Symbolism': 'Symbolism',
        'symbolism': 'Symbolism',
        'Mythology': 'Mythology',
        'mythology': 'Mythology',
        'Creature': 'Creature',
        'creature': 'Creature',
        'Fantasy': 'Fantasy',
        'fantasy': 'Fantasy',
        'History': 'History',
        'history': 'History',
        'Historical Figure': 'Historical Figure',
        'historical figure': 'Historical Figure',
        'Legacy': 'Legacy',
        'legacy': 'Legacy',
        'Marvel': 'Marvel',
        'marvel': 'Marvel',
        'MCU': 'MCU',
        'mcu': 'MCU',
        'Star Wars': 'Star Wars',
        'star wars': 'Star Wars',
        'Sci-Fi': 'Sci-Fi',
        'sci-fi': 'Sci-Fi',
        'Galaxy': 'Galaxy',
        'galaxy': 'Galaxy',
        'Zodiac': 'Zodiac',
        'zodiac': 'Zodiac',
        'Astrology': 'Astrology',
        'astrology': 'Astrology',
        'Horoscope': 'Horoscope',
        'horoscope': 'Horoscope',
        'Star Sign': 'Star Sign',
        'star sign': 'Star Sign',
        'Dark Side': 'Dark Side',
        'dark side': 'Dark Side',
        'Fairy Tale': 'Fairy Tale',
        'fairy tale': 'Fairy Tale',
        'Otaku': 'Otaku',
        'otaku': 'Otaku',
        'Comics': 'Comics',
        'comics': 'Comics',
        'Mystical': 'Mystical',
        'mystical': 'Mystical',
        'Timeless': 'Timeless',
        'timeless': 'Timeless',
        'Epic': 'Epic',
        'epic': 'Epic',
        'Wanderlust-filled': 'Wanderlust',
        'Intergalactic': 'Sci-Fi',
        'Cosmic': 'Cosmic',
        'cosmic': 'Cosmic',
        'Enchanting': 'Enchanting',
        'enchanting': 'Enchanting',
        'Melodic': 'Music',
        'melodic': 'Music',
        'Insightful': 'Insightful',
        'insightful': 'Insightful',
        'Heartfelt': 'Heartfelt',
        'heartfelt': 'Heartfelt',
        'Heroic': 'Heroic',
        'heroic': 'Heroic',
        'Soulful': 'Soulful',
        'soulful': 'Soulful',
        'Delicious': 'Food',
        'delicious': 'Food',
        'Magical': 'Magic',
        'magical': 'Magic',
        'Iconic': 'Iconic',
        'iconic': 'Iconic'
    }
    
    # 合并tag
    merged_tags = []
    for tag in tags:
        # 如果tag在映射中，使用映射后的值
        if tag in tag_mapping:
            merged_tag = tag_mapping[tag]
        else:
            # 否则使用原始tag
            merged_tag = tag
        
        # 避免重复
        if merged_tag not in merged_tags:
            merged_tags.append(merged_tag)
    
    # 排序
    merged_tags.sort()
    
    print('\nMerged tags:')
    for tag in merged_tags:
        print(f'- {tag}')
    print(f'Total merged tags: {len(merged_tags)}')
    
    return merged_tags

# 更新前端代码中的tag列表
def update_frontend_tags(tags):
    # 更新index.html中的tag列表
    try:
        with open('index.html', 'r') as f:
            content = f.read()
        
        # 找到tag列表的位置并替换
        old_tag_list = """const tags = [
                {tag_id: 'disney', text: 'Disney', icon: '🏰'},
                {tag_id: 'princess', text: 'Princess', icon: '👸'},
                {tag_id: 'personality', text: 'Personality', icon: '🧠'},
                {tag_id: 'mbti', text: 'MBTI', icon: '🔍'}
            ];"""
        
        # 创建新的tag列表
        new_tag_list = "const tags = [\n"
        
        # 为每个tag分配一个图标
        icons = ['🏰', '👸', '🧠', '🔍', '⚡', '🦸', '🐾', '🌟', '🎮', '🎯', '🎨', '🎭', '🎪', '🎧', '📚', '📸', '🌍', '🌌', '🌺', '🔥', '💎', '💡', '💖', '💫', '💯', '🌟', '🎯', '🎨', '🎮', '🎵']
        
        for i, tag in enumerate(tags):
            tag_id = tag.lower().replace(' ', '_').replace('-', '_')
            icon = icons[i % len(icons)]
            new_tag_list += '                {tag_id: "' + tag_id + '", text: "' + tag + '", icon: "' + icon + '"},\n'
        
        new_tag_list = new_tag_list.rstrip(',\n') + '\n            ];'
        
        # 替换tag列表
        new_content = content.replace(old_tag_list, new_tag_list)
        
        # 保存更新后的文件
        with open('index.html', 'w') as f:
            f.write(new_content)
        
        print('\nUpdated index.html with merged tags')
        
    except Exception as e:
        print(f'Error updating index.html: {e}')

if __name__ == '__main__':
    print('Collecting tags...')
    unique_tags = collect_tags()
    
    print('\nMerging similar tags...')
    merged_tags = merge_similar_tags(unique_tags)
    
    print('\nUpdating frontend tags...')
    update_frontend_tags(merged_tags)
    
    print('\nTag processing completed!')
