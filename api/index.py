import json
import random
import hashlib
import os
import sys

# Vercel Python Handler
def handler(request, context=None):
    global config, quizzes, API_KEY
    
    # Vercel puts files in /var/task
    BASE_DIR = '/var/task'
    
    # Initialize only once
    if not hasattr(handler, 'initialized'):
        try:
            # Load config
            config_path = os.path.join(BASE_DIR, 'config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load quizzes
            quizzes = {}
            quizzes_dir = os.path.join(BASE_DIR, 'quizzes')
            
            print(f"Base dir: {BASE_DIR}")
            print(f"Quizzes dir: {quizzes_dir}, exists: {os.path.exists(quizzes_dir)}")
            
            if os.path.exists(quizzes_dir):
                files = os.listdir(quizzes_dir)
                print(f"Quiz files: {files[:5]}...")
                for filename in files:
                    if filename.endswith('.json'):
                        quiz_id = os.path.splitext(filename)[0]
                        try:
                            with open(os.path.join(quizzes_dir, filename), 'r') as f:
                                quiz_data = json.load(f)
                                if 'scoringRules' not in quiz_data:
                                    quiz_data['scoringRules'] = config['scoringRules']
                                quizzes[quiz_id] = quiz_data
                        except Exception as e:
                            print(f"Error loading {filename}: {e}")
            
            # Load onequiz.json
            onequiz_path = os.path.join(BASE_DIR, 'onequiz.json')
            with open(onequiz_path, 'r') as f:
                onequiz_data = json.load(f)
                if 'scoringRules' not in onequiz_data:
                    onequiz_data['scoringRules'] = config['scoringRules']
                quizzes['onequiz'] = onequiz_data
            
            API_KEY = config['commonSettings']['apiKey']
            handler.initialized = True
            print(f"Initialized successfully. Loaded {len(quizzes)} quizzes")
        except Exception as e:
            print(f"Init error: {e}", file=sys.stderr)
            raise
    
    # Parse request
    path = request.url.path
    method = request.method
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,PUT,POST,DELETE,OPTIONS'
    }
    
    # Handle OPTIONS
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    # Route handling
    if path == '/api/token':
        token = hashlib.sha256(str(random.random()).encode()).hexdigest()
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'token': token})}
    
    elif path == '/api/quizzes':
        quizzes_list = []
        for quiz_id, quiz_data in quizzes.items():
            quizzes_list.append({
                'quiz_id': quiz_id,
                'title': quiz_data.get('title', 'Untitled'),
                'category': quiz_data.get('category', 'General'),
                'tags': quiz_data.get('tags', []),
                'description': quiz_data.get('description', '')
            })
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'quizzes': quizzes_list})}
    
    elif path == '/api/questions' and method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except:
            data = {}
        
        api_key = data.get('api_key', '')
        token = data.get('token', '')
        quiz_id = data.get('quiz_id', 'onequiz')
        
        if api_key != API_KEY or len(token) != 64:
            return {'statusCode': 401, 'headers': headers, 'body': json.dumps({'error': 'Unauthorized'})}
        
        quiz_data = quizzes.get(quiz_id, quizzes.get('onequiz'))
        shuffled = random.sample(quiz_data['questions'], min(12, len(quiz_data['questions'])))
        
        for i, q in enumerate(shuffled):
            q['temp_id'] = f'q{i+1}'
        
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({
            'questions': shuffled,
            'quiz_id': quiz_id,
            'title': quiz_data['title']
        })}
    
    elif path == '/api/result' and method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except:
            data = {}
        
        api_key = data.get('api_key', '')
        token = data.get('token', '')
        answers = data.get('answers', {})
        quiz_id = data.get('quiz_id', 'onequiz')
        
        if api_key != API_KEY or len(token) != 64:
            return {'statusCode': 401, 'headers': headers, 'body': json.dumps({'error': 'Unauthorized'})}
        
        quiz_data = quizzes.get(quiz_id, quizzes.get('onequiz'))
        
        dimension_scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
        
        for q_id, option_index in answers.items():
            for question in quiz_data['questions']:
                if str(question.get('qId')) == q_id or question.get('temp_id') == q_id:
                    if 0 <= int(option_index) < len(question['options']):
                        option = question['options'][int(option_index)]
                        score = option.get('score', '')
                        if isinstance(score, dict):
                            for dim, s in score.items():
                                dimension_scores[dim] += s
                        elif isinstance(score, str):
                            opp = {'E': 'I', 'I': 'E', 'S': 'N', 'N': 'S', 'T': 'F', 'F': 'T', 'J': 'P', 'P': 'J'}.get(score)
                            if opp:
                                dimension_scores[score] += 1
                    break
        
        mbti = ''
        mbti += 'E' if dimension_scores['E'] > dimension_scores['I'] else 'I'
        mbti += 'S' if dimension_scores['S'] > dimension_scores['N'] else 'N'
        mbti += 'T' if dimension_scores['T'] > dimension_scores['F'] else 'F'
        mbti += 'J' if dimension_scores['J'] > dimension_scores['P'] else 'P'
        
        result = None
        for r in quiz_data.get('results', []):
            if r.get('mbtiType') == mbti or r.get('mbti') == mbti:
                result = r
                break
        result = result or quiz_data.get('results', [{}])[0]
        
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({
            'mbti_type': mbti,
            'result': result,
            'percentages': {
                'extrovert_introvert': 50,
                'sensing_intuition': 50,
                'thinking_feeling': 50,
                'judging_perceiving': 50
            }
        })}
    
    # Serve static files
    elif path == '/' or path == '/index.html':
        try:
            with open(os.path.join(BASE_DIR, 'index.html'), 'r') as f:
                return {'statusCode': 200, 'headers': {'Content-Type': 'text/html'}, 'body': f.read()}
        except Exception as e:
            return {'statusCode': 404, 'headers': headers, 'body': f'Not found: {e}'}
    
    elif path.endswith('.html'):
        try:
            filename = path.lstrip('/')
            with open(os.path.join(BASE_DIR, filename), 'r') as f:
                return {'statusCode': 200, 'headers': {'Content-Type': 'text/html'}, 'body': f.read()}
        except Exception as e:
            return {'statusCode': 404, 'headers': headers, 'body': f'Not found: {e}'}
    
    else:
        return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Not found'})}
