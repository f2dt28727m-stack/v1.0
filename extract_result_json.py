import json
import re

# 读取result.json文件
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/result.json', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取所有的quiz对象
quiz_pattern = r'\{\s*"quizId":\s*\d+,\s*"title":\s*"[^"]+",\s*"results":\s*\[[^\]]*\]\s*\}'
quiz_matches = re.findall(quiz_pattern, content, re.DOTALL)

if quiz_matches:
    print(f'找到 {len(quiz_matches)} 个测试对象')
    
    # 重建JSON数组
    quizzes = []
    for i, quiz_match in enumerate(quiz_matches):
        # 修复转义字符
        quiz_str = quiz_match.replace('\'92', "'")
        quiz_str = quiz_match.replace('\'96', "–")
        
        try:
            quiz = json.loads(quiz_str)
            quizzes.append(quiz)
            print(f'✓ 成功解析测试 {i+1}: {quiz.get("title")}')
        except json.JSONDecodeError as e:
            print(f'✗ 解析测试 {i+1} 失败:', e)
    
    # 保存重建的数据
    if quizzes:
        with open('/Users/jerrysrick/.openclaw/workspace/psych-test/clean_result.json', 'w', encoding='utf-8') as f:
            json.dump(quizzes, f, indent=2, ensure_ascii=False)
        print(f'\n成功保存 {len(quizzes)} 个测试到 clean_result.json')
    else:
        print('\n没有成功解析的测试')
else:
    print('未找到测试对象')
