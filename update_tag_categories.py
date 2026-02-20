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
    return unique_tags

# 创建tag分类
def create_tag_categories(tags):
    # 定义tag分类
    categories = {
        'Entertainment': ['Disney', 'Princess', 'Harry Potter', 'Hogwarts', 'Wizarding World', 'Marvel', 'MCU', 'Star Wars', 'Anime', 'Comics', 'Villain'],
        'Personality': ['MBTI', 'Personality', 'Love Language', 'Love', 'Relationships', 'Emotions'],
        'Interests': ['Travel', 'Adventure', 'Food', 'Cooking', 'Eating', 'Music', 'Sound', 'Rhythm'],
        'Career': ['Career', 'Work', 'Success'],
        'Fantasy': ['Magic', 'Creature', 'Mythology', 'Fairy Tale', 'Fantasy', 'Spirit Animal', 'Dark Side'],
        'Knowledge': ['History', 'Historical Figure', 'Astrology', 'Horoscope', 'Zodiac', 'Galaxy', 'Sci-Fi', 'Legacy'],
        'Lifestyle': ['Nature', 'Wanderlust', 'Symbolism'],
        'Other': ['Character', 'Sidekick', 'Superhero', 'Otaku', '趣味']
    }
    
    # 确保所有tag都被分类
    categorized_tags = {}
    uncategorized = []
    
    for tag in tags:
        found = False
        for category, category_tags in categories.items():
            if tag in category_tags:
                if category not in categorized_tags:
                    categorized_tags[category] = []
                categorized_tags[category].append(tag)
                found = True
                break
        if not found:
            uncategorized.append(tag)
    
    # 处理未分类的tag
    if uncategorized:
        categorized_tags['Other'] = categorized_tags.get('Other', []) + uncategorized
    
    # 对每个分类中的tag排序
    for category in categorized_tags:
        categorized_tags[category].sort()
    
    print('Tag categories:')
    for category, category_tags in categorized_tags.items():
        print(f'\n{category}:')
        for tag in category_tags:
            print(f'- {tag}')
    
    return categorized_tags

# 更新前端代码以分类展示tag
def update_frontend_categories(categories):
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
        
        # 创建新的分类tag列表
        new_tag_list = 'const tagCategories = {\n'
        
        # 为每个分类分配一个图标
        category_icons = {
            'Entertainment': '🎬',
            'Personality': '🧠',
            'Interests': '🌟',
            'Career': '💼',
            'Fantasy': '🧙',
            'Knowledge': '📚',
            'Lifestyle': '🌿',
            'Other': '🔍'
        }
        
        # 为每个tag分配一个图标
        tag_icons = {
            'Disney': '🏰',
            'Princess': '👸',
            'Harry Potter': '⚡',
            'Hogwarts': '🏰',
            'Wizarding World': '🪄',
            'Marvel': '🦸',
            'MCU': '🎬',
            'Star Wars': '🌌',
            'Anime': '🎌',
            'Comics': '📚',
            'Villain': '🎭',
            'MBTI': '🔍',
            'Personality': '🧠',
            'Love Language': '💖',
            'Love': '❤️',
            'Relationships': '👥',
            'Emotions': '😊',
            'Travel': '✈️',
            'Adventure': '⛰️',
            'Food': '🍕',
            'Cooking': '🍳',
            'Eating': '🍽️',
            'Music': '🎵',
            'Sound': '🔊',
            'Rhythm': '🎶',
            'Career': '💼',
            'Work': '💪',
            'Success': '🏆',
            'Magic': '🪄',
            'Creature': '🐉',
            'Mythology': '🏛️',
            'Fairy Tale': '🧚',
            'Fantasy': '✨',
            'Spirit Animal': '🐾',
            'Dark Side': '🌑',
            'History': '📜',
            'Historical Figure': '👑',
            'Astrology': '⭐',
            'Horoscope': '🔮',
            'Zodiac': '♈',
            'Galaxy': '🌌',
            'Sci-Fi': '🚀',
            'Legacy': '🏛️',
            'Nature': '🌿',
            'Wanderlust': '🌍',
            'Symbolism': '🔣',
            'Character': '🎭',
            'Sidekick': '🤝',
            'Superhero': '🦸',
            'Otaku': '🎮',
            '趣味': '🎯'
        }
        
        for category, category_tags in categories.items():
            category_icon = category_icons.get(category, '🔍')
            new_tag_list += f'    "{category}": {{\n'
            new_tag_list += f'        icon: "{category_icon}",\n'
            new_tag_list += '        tags: [\n'
            
            for tag in category_tags:
                tag_id = tag.lower().replace(' ', '_').replace('-', '_')
                tag_icon = tag_icons.get(tag, '🔍')
                new_tag_list += '            {tag_id: "' + tag_id + '", text: "' + tag + '", icon: "' + tag_icon + '"},\n'
            
            new_tag_list = new_tag_list.rstrip(',\n') + '\n'
            new_tag_list += '        ]\n'
            new_tag_list += '    },\n'
        
        new_tag_list = new_tag_list.rstrip(',\n') + '\n' + '};'
        
        # 找到并替换原有的tag列表和样式
        try:
            # 读取文件内容
            with open('index.html', 'r') as f:
                content = f.read()
            
            # 找到现有的renderTags函数并替换
            import re
            old_render_tags = re.search(r'// Render filter tags dynamically[\s\S]*?function renderTags\(\)\{[\s\S]*?\}', content).group(0)
            
            # 创建新的tag分类和renderTags函数
            new_content = content.replace(old_render_tags, '''// Tag categories
const tagCategories = {
    "Entertainment": {
        icon: "🎬",
        tags: [
            {tag_id: "disney", text: "Disney", icon: "🏰"},
            {tag_id: "princess", text: "Princess", icon: "👸"},
            {tag_id: "harry_potter", text: "Harry Potter", icon: "⚡"},
            {tag_id: "hogwarts", text: "Hogwarts", icon: "🏰"},
            {tag_id: "wizarding_world", text: "Wizarding World", icon: "🪄"},
            {tag_id: "marvel", text: "Marvel", icon: "🦸"},
            {tag_id: "mcu", text: "MCU", icon: "🎬"},
            {tag_id: "star_wars", text: "Star Wars", icon: "🌌"},
            {tag_id: "anime", text: "Anime", icon: "🎌"},
            {tag_id: "comics", text: "Comics", icon: "📚"},
            {tag_id: "villain", text: "Villain", icon: "🎭"}
        ]
    },
    "Personality": {
        icon: "🧠",
        tags: [
            {tag_id: "mbti", text: "MBTI", icon: "🔍"},
            {tag_id: "personality", text: "Personality", icon: "🧠"},
            {tag_id: "love_language", text: "Love Language", icon: "💖"},
            {tag_id: "love", text: "Love", icon: "❤️"},
            {tag_id: "relationships", text: "Relationships", icon: "👥"},
            {tag_id: "emotions", text: "Emotions", icon: "😊"}
        ]
    },
    "Interests": {
        icon: "🌟",
        tags: [
            {tag_id: "travel", text: "Travel", icon: "✈️"},
            {tag_id: "adventure", text: "Adventure", icon: "⛰️"},
            {tag_id: "food", text: "Food", icon: "🍕"},
            {tag_id: "cooking", text: "Cooking", icon: "🍳"},
            {tag_id: "eating", text: "Eating", icon: "🍽️"},
            {tag_id: "music", text: "Music", icon: "🎵"},
            {tag_id: "sound", text: "Sound", icon: "🔊"},
            {tag_id: "rhythm", text: "Rhythm", icon: "🎶"}
        ]
    },
    "Career": {
        icon: "💼",
        tags: [
            {tag_id: "career", text: "Career", icon: "💼"},
            {tag_id: "work", text: "Work", icon: "💪"},
            {tag_id: "success", text: "Success", icon: "🏆"}
        ]
    },
    "Fantasy": {
        icon: "🧙",
        tags: [
            {tag_id: "magic", text: "Magic", icon: "🪄"},
            {tag_id: "creature", text: "Creature", icon: "🐉"},
            {tag_id: "mythology", text: "Mythology", icon: "🏛️"},
            {tag_id: "fairy_tale", text: "Fairy Tale", icon: "🧚"},
            {tag_id: "fantasy", text: "Fantasy", icon: "✨"},
            {tag_id: "spirit_animal", text: "Spirit Animal", icon: "🐾"},
            {tag_id: "dark_side", text: "Dark Side", icon: "🌑"}
        ]
    },
    "Knowledge": {
        icon: "📚",
        tags: [
            {tag_id: "history", text: "History", icon: "📜"},
            {tag_id: "historical_figure", text: "Historical Figure", icon: "👑"},
            {tag_id: "astrology", text: "Astrology", icon: "⭐"},
            {tag_id: "horoscope", text: "Horoscope", icon: "🔮"},
            {tag_id: "zodiac", text: "Zodiac", icon: "♈"},
            {tag_id: "galaxy", text: "Galaxy", icon: "🌌"},
            {tag_id: "sci_fi", text: "Sci-Fi", icon: "🚀"},
            {tag_id: "legacy", text: "Legacy", icon: "🏛️"}
        ]
    },
    "Lifestyle": {
        icon: "🌿",
        tags: [
            {tag_id: "nature", text: "Nature", icon: "🌿"},
            {tag_id: "wanderlust", text: "Wanderlust", icon: "🌍"},
            {tag_id: "symbolism", text: "Symbolism", icon: "🔣"}
        ]
    },
    "Other": {
        icon: "🔍",
        tags: [
            {tag_id: "character", text: "Character", icon: "🎭"},
            {tag_id: "sidekick", text: "Sidekick", icon: "🤝"},
            {tag_id: "superhero", text: "Superhero", icon: "🦸"},
            {tag_id: "otaku", text: "Otaku", icon: "🎮"},
            {tag_id: "趣味", text: "趣味", icon: "🎯"}
        ]
    }
};

// Render filter tags dynamically
function renderTags() {
    const filterPanel = document.getElementById('filter-panel');
    let html = '';
    
    // Render each category
    for (const [category, categoryData] of Object.entries(tagCategories)) {
        html += `
        <div class="category-section">
            <div class="category-header">
                <span class="category-icon">${categoryData.icon}</span>
                <span class="category-title">${category}</span>
            </div>
            <div class="category-tags">
        `;
        
        // Render tags in this category
        categoryData.tags.forEach(tag => {
            html += `
                <div class="filter-tag" data-tag="${tag.tag_id}" onclick="toggleTag('${tag.tag_id}')">
                    ${tag.icon} ${tag.text}
                </div>
            `;
        });
        
        html += `
            </div>
        </div>
        `;
    }
    
    filterPanel.innerHTML = html;
}''')
            
            # 找到现有的Filters样式并替换
            old_filters_style = re.search(r'/* Filters */[\s\S]*?\.filter-tag\.active \{[\s\S]*?\}', new_content).group(0)
            new_filters_style = '''/* Filters */
        .filter-bar {
            display: flex;
            gap: 8px;
            padding: 12px 20px;
            align-items: center;
        }
        .sort-btn {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
        }
        .sort-btn.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-toggle {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
            margin-left: auto;
        }
        .filter-toggle.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-panel {
            display: none;
            padding: 15px 20px;
            flex-direction: column;
            gap: 15px;
        }
        .filter-panel.show {
            display: flex;
        }
        .category-section {
            margin-bottom: 10px;
        }
        .category-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            padding-left: 8px;
        }
        .category-icon {
            font-size: 16px;
        }
        .category-title {
            font-size: 14px;
            font-weight: 600;
            color: #00d4ff;
        }
        .category-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding-left: 8px;
        }
        .filter-tag {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
            transition: all 0.2s;
        }
        .filter-tag:hover {
            border-color: #444;
        }
        .filter-tag.active {
            background: rgba(0,212,255,0.2);
            color: #00d4ff;
            border-color: #00d4ff;
        }'''
            
            new_content = new_content.replace(old_filters_style, new_filters_style)
            
            # 保存更新后的文件
            with open('index.html', 'w') as f:
                f.write(new_content)
            
            print('\nUpdated index.html with categorized tags')
        except Exception as e:
            print(f'Error updating index.html: {e}')
            
            # 如果正则表达式失败，使用简单的字符串替换
            try:
                with open('index.html', 'r') as f:
                    content = f.read()
                
                # 简单替换
                if '// Render filter tags dynamically' in content:
                    # 替换整个脚本部分
                    new_script = '''// Tag categories
const tagCategories = {
    "Entertainment": {
        icon: "🎬",
        tags: [
            {tag_id: "disney", text: "Disney", icon: "🏰"},
            {tag_id: "princess", text: "Princess", icon: "👸"},
            {tag_id: "harry_potter", text: "Harry Potter", icon: "⚡"},
            {tag_id: "hogwarts", text: "Hogwarts", icon: "🏰"},
            {tag_id: "wizarding_world", text: "Wizarding World", icon: "🪄"},
            {tag_id: "marvel", text: "Marvel", icon: "🦸"},
            {tag_id: "mcu", text: "MCU", icon: "🎬"},
            {tag_id: "star_wars", text: "Star Wars", icon: "🌌"},
            {tag_id: "anime", text: "Anime", icon: "🎌"},
            {tag_id: "comics", text: "Comics", icon: "📚"},
            {tag_id: "villain", text: "Villain", icon: "🎭"}
        ]
    },
    "Personality": {
        icon: "🧠",
        tags: [
            {tag_id: "mbti", text: "MBTI", icon: "🔍"},
            {tag_id: "personality", text: "Personality", icon: "🧠"},
            {tag_id: "love_language", text: "Love Language", icon: "💖"},
            {tag_id: "love", text: "Love", icon: "❤️"},
            {tag_id: "relationships", text: "Relationships", icon: "👥"},
            {tag_id: "emotions", text: "Emotions", icon: "😊"}
        ]
    },
    "Interests": {
        icon: "🌟",
        tags: [
            {tag_id: "travel", text: "Travel", icon: "✈️"},
            {tag_id: "adventure", text: "Adventure", icon: "⛰️"},
            {tag_id: "food", text: "Food", icon: "🍕"},
            {tag_id: "cooking", text: "Cooking", icon: "🍳"},
            {tag_id: "eating", text: "Eating", icon: "🍽️"},
            {tag_id: "music", text: "Music", icon: "🎵"},
            {tag_id: "sound", text: "Sound", icon: "🔊"},
            {tag_id: "rhythm", text: "Rhythm", icon: "🎶"}
        ]
    },
    "Career": {
        icon: "💼",
        tags: [
            {tag_id: "career", text: "Career", icon: "💼"},
            {tag_id: "work", text: "Work", icon: "💪"},
            {tag_id: "success", text: "Success", icon: "🏆"}
        ]
    },
    "Fantasy": {
        icon: "🧙",
        tags: [
            {tag_id: "magic", text: "Magic", icon: "🪄"},
            {tag_id: "creature", text: "Creature", icon: "🐉"},
            {tag_id: "mythology", text: "Mythology", icon: "🏛️"},
            {tag_id: "fairy_tale", text: "Fairy Tale", icon: "🧚"},
            {tag_id: "fantasy", text: "Fantasy", icon: "✨"},
            {tag_id: "spirit_animal", text: "Spirit Animal", icon: "🐾"},
            {tag_id: "dark_side", text: "Dark Side", icon: "🌑"}
        ]
    },
    "Knowledge": {
        icon: "📚",
        tags: [
            {tag_id: "history", text: "History", icon: "📜"},
            {tag_id: "historical_figure", text: "Historical Figure", icon: "👑"},
            {tag_id: "astrology", text: "Astrology", icon: "⭐"},
            {tag_id: "horoscope", text: "Horoscope", icon: "🔮"},
            {tag_id: "zodiac", text: "Zodiac", icon: "♈"},
            {tag_id: "galaxy", text: "Galaxy", icon: "🌌"},
            {tag_id: "sci_fi", text: "Sci-Fi", icon: "🚀"},
            {tag_id: "legacy", text: "Legacy", icon: "🏛️"}
        ]
    },
    "Lifestyle": {
        icon: "🌿",
        tags: [
            {tag_id: "nature", text: "Nature", icon: "🌿"},
            {tag_id: "wanderlust", text: "Wanderlust", icon: "🌍"},
            {tag_id: "symbolism", text: "Symbolism", icon: "🔣"}
        ]
    },
    "Other": {
        icon: "🔍",
        tags: [
            {tag_id: "character", text: "Character", icon: "🎭"},
            {tag_id: "sidekick", text: "Sidekick", icon: "🤝"},
            {tag_id: "superhero", text: "Superhero", icon: "🦸"},
            {tag_id: "otaku", text: "Otaku", icon: "🎮"},
            {tag_id: "趣味", text: "趣味", icon: "🎵"}
        ]
    }
};

// Render filter tags dynamically
function renderTags() {
    const filterPanel = document.getElementById('filter-panel');
    let html = '';
    
    // Render each category
    for (const [category, categoryData] of Object.entries(tagCategories)) {
        html += `
        <div class="category-section">
            <div class="category-header">
                <span class="category-icon">${categoryData.icon}</span>
                <span class="category-title">${category}</span>
            </div>
            <div class="category-tags">
        `;
        
        // Render tags in this category
        categoryData.tags.forEach(tag => {
            html += `
                <div class="filter-tag" data-tag="${tag.tag_id}" onclick="toggleTag('${tag.tag_id}')">
                    ${tag.icon} ${tag.text}
                </div>
            `;
        });
        
        html += `
            </div>
        </div>
        `;
    }
    
    filterPanel.innerHTML = html;
}'''
                    
                    # 替换样式
                    old_css = '''/* Filters */
        .filter-bar {
            display: flex;
            gap: 8px;
            padding: 12px 20px;
            align-items: center;
        }
        .sort-btn {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
        }
        .sort-btn.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-toggle {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
            margin-left: auto;
        }
        .filter-toggle.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-panel {
            display: none;
            padding: 0 20px 15px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .filter-panel.show {
            display: flex;
        }
        .filter-tag {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
        }
        .filter-tag.active {
            background: rgba(0,212,255,0.2);
            color: #00d4ff;
            border-color: #00d4ff;
        }'''
                    
                    new_css = '''/* Filters */
        .filter-bar {
            display: flex;
            gap: 8px;
            padding: 12px 20px;
            align-items: center;
        }
        .sort-btn {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
        }
        .sort-btn.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-toggle {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
            margin-left: auto;
        }
        .filter-toggle.active {
            background: #00d4ff;
            color: #000;
            border-color: #00d4ff;
        }
        .filter-panel {
            display: none;
            padding: 15px 20px;
            flex-direction: column;
            gap: 15px;
        }
        .filter-panel.show {
            display: flex;
        }
        .category-section {
            margin-bottom: 10px;
        }
        .category-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            padding-left: 8px;
        }
        .category-icon {
            font-size: 16px;
        }
        .category-title {
            font-size: 14px;
            font-weight: 600;
            color: #00d4ff;
        }
        .category-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding-left: 8px;
        }
        .filter-tag {
            padding: 8px 14px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            font-size: 13px;
            color: #888;
            cursor: pointer;
            transition: all 0.2s;
        }
        .filter-tag:hover {
            border-color: #444;
        }
        .filter-tag.active {
            background: rgba(0,212,255,0.2);
            color: #00d4ff;
            border-color: #00d4ff;
        }'''
                    
                    # 替换内容
                    new_content = content.replace(old_css, new_css)
                    
                    # 保存文件
                    with open('index.html', 'w') as f:
                        f.write(new_content)
                    
                    print('\nUpdated index.html with categorized tags (simple method)')
            except Exception as e2:
                print(f'Error with simple replacement: {e2}')

if __name__ == '__main__':
    print('Collecting tags...')
    unique_tags = collect_tags()
    
    print('\nCreating tag categories...')
    categories = create_tag_categories(unique_tags)
    
    print('\nUpdating frontend with categorized tags...')
    update_frontend_categories(categories)
    
    print('\nTag categorization completed!')
