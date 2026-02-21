#!/bin/bash

# 英文版 -> 中文版 同步脚本
# 依赖: curl, jq
# 用法: ./sync_translation.sh [quiz_number]

QUIZZES_DIR="/Users/jerrysrick/.openclaw/workspace/psych-test/quizzes"
QUIZZES_ZH_DIR="/Users/jerrysrick/.openclaw/workspace/psych-test/quizzes_zh"

# 翻译函数 - 使用 LibreTranslate (免费开源)
translate_text() {
    local text="$1"
    local escaped_text=$(echo "$text" | jq -Rs .)
    
    local result=$(curl -s -X POST "https://libretranslate.com/translate" \
        -H "Content-Type: application/json" \
        -d "{\"q\": $escaped_text, \"source\": \"en\", \"target\": \"zh\"}" 2>/dev/null)
    
    echo "$result" | jq -r '.translatedText // empty'
}

# 备用翻译 - 使用 MyMemory API (免费，无需 API key)
translate_text_backup() {
    local text="$1"
    local encoded=$(echo "$text" | jq -Rs . | sed 's/["\\]//g' | xargs -I {} curl -s "https://api.mymemory.translated.net/get?q={}&langpair=en|zh-CN")
    echo "$encoded" | jq -r '.responseData.translatedText // empty'
}

# 处理整个 JSON 文件
translate_quiz_file() {
    local quiz_file="$1"
    local quiz_name=$(basename "$quiz_file")
    
    echo "📝 处理: $quiz_name"
    
    # 读取英文版
    local content=$(cat "$quiz_file")
    
    # 提取需要翻译的字段
    local title=$(echo "$content" | jq -r '.title // empty')
    local description=$(echo "$content" | jq -r '.description // empty')
    
    # 翻译 title
    local zh_title=$(translate_text "$title")
    if [ -z "$zh_title" ]; then
        zh_title="$title"
    fi
    
    # 翻译 description
    local zh_description=$(translate_text "$description")
    if [ -z "$zh_description" ]; then
        zh_description="$description"
    fi
    
    # 翻译 questions
    local questions=$(echo "$content" | jq '.questions')
    local zh_questions="["
    
    local first=true
    echo "$questions" | jq -c '.[]' | while read -r q; do
        local q_text=$(echo "$q" | jq -r '.question')
        local q_text_zh=$(translate_text "$q_text")
        
        local options=$(echo "$q" | jq '.options')
        local zh_options="["
        local opt_first=true
        echo "$options" | jq -c '.[]' | while read -r opt; do
            local opt_text=$(echo "$opt" | jq -r '.text')
            local opt_text_zh=$(translate_text "$opt_text")
            if [ "$opt_first" = true ]; then
                zh_options+="{\"text\": \"$opt_text_zh\"}"
                opt_first=false
            else
                zh_options+=", {\"text\": \"$opt_text_zh\"}"
            fi
        done
        zh_options+="]"
        
        if [ "$first" = true ]; then
            zh_questions+="{\"question\": \"$q_text_zh\", \"options\": $zh_options}"
            first=false
        else
            zh_questions+=", {\"question\": \"$q_text_zh\", \"options\": $zh_options}"
        fi
    done
    zh_questions+="]"
    
    # 翻译 results
    local results=$(echo "$content" | jq '.results')
    # ... 类似处理 ...
    
    # 写入中文版
    local zh_file="$QUIZZES_ZH_DIR/$quiz_name"
    
    # 简单替换 title 和 description
    echo "$content" | jq --arg title "$zh_title" --arg desc "$zh_description" \
        '.title = $title | .description = $desc' > "$zh_file"
    
    echo "✅ 已更新: $quiz_name"
}

# 单个文件模式
if [ -n "$1" ]; then
    quiz_num="$1"
    if [ -f "$QUIZZES_DIR/quiz_${quiz_num}.json" ]; then
        translate_quiz_file "$QUIZZES_DIR/quiz_${quiz_num}.json"
    else
        echo "❌ 文件不存在: quiz_${quiz_num}.json"
    fi
    exit 0
fi

echo "用法:"
echo "  ./sync_translation.sh 1     # 翻译 quiz_1"
echo "  ./sync_translation.sh      # 查看帮助"
