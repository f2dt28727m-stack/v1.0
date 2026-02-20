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
                print(f'Processed: {filename}')
            except Exception as e:
                print(f'Error loading {filename}: {e}')
    
    # 处理onequiz.json
    try:
        with open('onequiz.json', 'r') as f:
            data = json.load(f)
            if 'tags' in data:
                all_tags.extend(data['tags'])
        print('Processed: onequiz.json')
    except Exception as e:
        print(f'Error loading onequiz.json: {e}')
    
    # 去重并排序
    unique_tags = sorted(list(set(all_tags)))
    
    print('\nAll unique tags:')
    for tag in unique_tags:
        print(f'- {tag}')
    print(f'\nTotal unique tags: {len(unique_tags)}')
    
    return unique_tags

# 处理选项中的括号内容
def process_options():
    quizzes_dir = 'quizzes'
    
    # 遍历quizzes目录中的所有问卷
    for filename in os.listdir(quizzes_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(quizzes_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # 处理问题选项
                if 'questions' in data:
                    for question in data['questions']:
                        if 'options' in question:
                            for option in question['options']:
                                if 'text' in option:
                                    # 删除括号内的内容
                                    original_text = option['text']
                                    new_text = original_text.split('(')[0].strip()
                                    option['text'] = new_text
                                    if original_text != new_text:
                                        print(f'Updated option in {filename}: {original_text} -> {new_text}')
                
                # 保存更新后的数据
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f'Updated: {filename}')
            except Exception as e:
                print(f'Error processing {filename}: {e}')
    
    # 处理onequiz.json
    try:
        with open('onequiz.json', 'r') as f:
            data = json.load(f)
        
        # 处理问题选项
        if 'questions' in data:
            for question in data['questions']:
                if 'options' in question:
                    for option in question['options']:
                        if 'text' in option:
                            # 删除括号内的内容
                            original_text = option['text']
                            new_text = original_text.split('(')[0].strip()
                            option['text'] = new_text
                            if original_text != new_text:
                                print(f'Updated option in onequiz.json: {original_text} -> {new_text}')
        
        # 保存更新后的数据
        with open('onequiz.json', 'w') as f:
            json.dump(data, f, indent=2)
        print('Updated: onequiz.json')
    except Exception as e:
        print(f'Error processing onequiz.json: {e}')

if __name__ == '__main__':
    print('Collecting tags...')
    unique_tags = collect_tags()
    
    print('\nProcessing options...')
    process_options()
