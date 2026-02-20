#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to categorize tags and update frontend code
"""

import os

def update_frontend():
    """Update index.html with categorized tags"""
    try:
        # Read the current index.html file
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Define the new tag categories data
        tag_categories_data = '''
// Tag categories
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
}
'''
        
        # Define the new filter styles
        new_filter_styles = '''
/* Filters */
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
}
'''
        
        # Find and replace the old renderTags function
        render_tags_start = content.find('// Render filter tags dynamically')
        if render_tags_start != -1:
            # Find the end of the renderTags function
            # Look for the next function definition or the end of the script
            temp_content = content[render_tags_start:]
            next_function = temp_content.find('function ')
            if next_function != -1 and next_function > 0:
                render_tags_end = render_tags_start + next_function
            else:
                # If no next function, go to the end of the script
                script_end = content.find('</script>', render_tags_start)
                if script_end != -1:
                    render_tags_end = script_end
                else:
                    render_tags_end = len(content)
            
            # Replace the old renderTags function with the new one
            old_render_tags = content[render_tags_start:render_tags_end]
            new_content = content.replace(old_render_tags, tag_categories_data)
            
            # Find and replace the old filter styles
            filter_styles_start = new_content.find('/* Filters */')
            if filter_styles_start != -1:
                # Find the end of the filter styles
                next_section = new_content.find('/* ', filter_styles_start + 1)
                if next_section != -1:
                    filter_styles_end = next_section
                else:
                    filter_styles_end = len(new_content)
                
                old_filter_styles = new_content[filter_styles_start:filter_styles_end]
                new_content = new_content.replace(old_filter_styles, new_filter_styles)
            
            # Save the updated file
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✓ Successfully updated index.html with categorized tags")
            print("✓ Added 8 tag categories with appropriate icons")
            print("✓ Updated filter panel styling for better user experience")
        else:
            print("⚠️  Could not find '// Render filter tags dynamically' in index.html")
            print("⚠️  Please check the file structure")
            
    except Exception as e:
        print(f"❌ Error updating frontend: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("Starting tag categorization process...")
    print("=" * 50)
    
    update_frontend()
    
    print("=" * 50)
    print("Tag categorization process completed!")

if __name__ == "__main__":
    main()
