import json
import re

# 读取result.json文件
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/result.json', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON部分
json_match = re.search(r'\[.*\]', content, re.DOTALL)
if json_match:
    json_content = json_match.group(0)
    # 修复转义字符
    json_content = json_content.replace('\'92', "'")
    
    try:
        data = json.loads(json_content)
        print('Result.json 中的测试数量:', len(data))
        print('\nResult.json 中的测试:')
        for i, test in enumerate(data):
            print(f'{i+1}. quizId: {test.get("quizId")}, title: {test.get("title")}')
            print(f'   结果数量: {len(test.get("results", []))}')
    except json.JSONDecodeError as e:
        print('JSON解析错误:', e)
else:
    print('未找到JSON数据')

print('\n' + '='*50 + '\n')

# 读取result_skin.json
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/data/result_skin.json', 'r', encoding='utf-8') as f:
    skin_data = json.load(f)
    print('Result_skin.json 中的测试数量:', len(skin_data))
    print('\nResult_skin.json 中的测试:')
    for i, test in enumerate(skin_data):
        print(f'{i+1}. test_id: {test.get("test_id")}, title: {test.get("title")}')
        print(f'   结果数量: {len(test.get("results", []))}')

print('\n' + '='*50 + '\n')

# 读取test_data.json
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/data/test_data.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)
    print('Test_data.json 中的测试数量:', len(test_data))
    print('\nTest_data.json 中的测试:')
    for i, test in enumerate(test_data):
        print(f'{i+1}. test_id: {test.get("test_id")}, title: {test.get("title")}')
        print(f'   category_id: {test.get("category_id")}, tags: {test.get("tags")}')

print('\n' + '='*50 + '\n')
print('数据匹配分析:')
print('-'*50)

# 分析匹配情况
result_titles = [test.get('title') for test in data] if json_match and 'data' in locals() else []
skin_titles = [test.get('title') for test in skin_data]
test_titles = [test.get('title') for test in test_data]

print('\nResult.json 与 Result_skin.json 匹配情况:')
for title in result_titles:
    if title in skin_titles:
        print(f'✓ 匹配: {title}')
    else:
        print(f'✗ 不匹配: {title}')

print('\nTest_data.json 与 Result_skin.json 匹配情况:')
for title in test_titles:
    if title in skin_titles:
        print(f'✓ 匹配: {title}')
    else:
        print(f'✗ 不匹配: {title}')
