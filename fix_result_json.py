import json
import re

# 读取result.json文件
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/result.json', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON部分，更精确的匹配
json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
if not json_match:
    # 尝试另一种匹配方式
    json_match = re.search(r'\[.*\]', content, re.DOTALL)

if json_match:
    json_content = json_match.group(0)
    # 修复转义字符和RTF格式
    json_content = json_content.replace('\'92', "'")
    json_content = json_content.replace('\r\n', ' ')
    json_content = json_content.replace('\n', ' ')
    json_content = json_content.replace('\r', ' ')
    json_content = re.sub(r'\\[a-z0-9]+', '', json_content)
    
    # 尝试解析
    try:
        data = json.loads(json_content)
        print('成功解析JSON数据')
        print('测试数量:', len(data))
        
        # 保存清理后的数据
        with open('/Users/jerrysrick/.openclaw/workspace/psych-test/clean_result.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print('清理后的数据已保存到 clean_result.json')
        
        # 显示测试标题
        print('\n测试标题:')
        for i, test in enumerate(data):
            print(f'{i+1}. {test.get("title")}')
            print(f'   quizId: {test.get("quizId")}')
            print(f'   结果数量: {len(test.get("results", []))}')
    except json.JSONDecodeError as e:
        print('JSON解析错误:', e)
        # 保存原始提取的内容以便查看
        with open('/Users/jerrysrick/.openclaw/workspace/psych-test/extracted_json.txt', 'w', encoding='utf-8') as f:
            f.write(json_content)
        print('提取的内容已保存到 extracted_json.txt')
else:
    print('未找到JSON数据')
