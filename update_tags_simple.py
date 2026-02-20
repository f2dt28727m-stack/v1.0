import json
import os

# 主函数
def main():
    print('Starting tag categorization...')
    
    # 1. 更新前端代码，添加分类标签
    update_frontend_categories()
    
    print('\nTag categorization completed successfully!')

# 更新前端代码以分类展示tag
def update_frontend_categories():
    try:
        # 读取index.html文件
        with open('index.html', 'r') as f:
            content = f.read()
        
        # 定义新的标签分类数据
        new_tag_categories = '''// Tag categories
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
}'''
        
        # 定义新的过滤器样式
        new_filter_styles = '''/* Filters */
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