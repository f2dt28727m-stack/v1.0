import json

try:
    with open('onequiz.json', 'r') as f:
        data = json.load(f)
    print('JSON is valid!')
    print('Number of questions:', len(data.get('questions', [])))
    print('Number of results:', len(data.get('results', [])))
except json.JSONDecodeError as e:
    print('JSON is invalid:', e)
except Exception as e:
    print('Error:', e)
