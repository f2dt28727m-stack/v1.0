import json
import re

# 读取result.json文件
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/result.json', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除RTF格式标记
content = re.sub(r'\\[a-z0-9]+', '', content)
content = re.sub(r'\{[^}]*\}', '', content)
content = re.sub(r'\[\*[^\]]*\]', '', content)

# 修复转义字符
content = content.replace('\'92', "'")
content = content.replace('\'96', "–")
content = content.replace('\\', '')

# 提取JSON数组部分
json_match = re.search(r'\[.*\]', content, re.DOTALL)
if json_match:
    json_content = json_match.group(0)
    
    # 清理空白字符
    json_content = re.sub(r'\s+', ' ', json_content)
    json_content = json_content.strip()
    
    # 修复JSON格式
    json_content = json_content.replace(' {', '{')
    json_content = json_content.replace('} ', '}')
    json_content = json_content.replace(' [', '[')
    json_content = json_content.replace('] ', ']')
    json_content = json_content.replace(', }', '}')
    json_content = json_content.replace(', ]', ']')
    
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
        # 保存处理后的内容以便查看
        with open('/Users/jerrysrick/.openclaw/workspace/psych-test/processed_json.txt', 'w', encoding='utf-8') as f:
            f.write(json_content)
        print('处理后的内容已保存到 processed_json.txt')
else:
    print('未找到JSON数据')
