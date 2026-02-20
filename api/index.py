import json
import random
import hashlib
import os

# Simple API handler for Vercel
def handler(event, context):
    # Get path from event
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    # CORS headers
    cors = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
    
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors, 'body': ''}
    
    # Only handle /api/* routes
    if not path.startswith('/api/'):
        return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Not found'})}
    
    # Base directory
    base = '/var/task'
    
    # Load config
    try:
        with open(f'{base}/config.json') as f:
            config = json.load(f)
        api_key = config['commonSettings']['apiKey']
    except:
        api_key = 'default_key'
    
    # /api/token
    if path == '/api/token':
        token = hashlib.sha256(str(random.random()).encode()).hexdigest()
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({'token': token})}
    
    # Load quizzes
    quizzes = {}
    try:
        for f in os.listdir(f'{base}/quizzes'):
            if f.endswith('.json'):
                qid = f.replace('.json', '')
                with open(f'{base}/quizzes/{f}') as fp:
                    quizzes[qid] = json.load(fp)
    except:
        pass
    
    # /api/quizzes
    if path == '/api/quizzes':
        lst = []
        for qid, q in quizzes.items():
            lst.append({
                'quiz_id': qid,
                'title': q.get('title', 'Untitled'),
                'category': q.get('category', 'General'),
                'tags': q.get('tags', []),
                'description': q.get('description', '')
            })
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({'quizzes': lst})}
    
    # /api/questions (POST)
    if path == '/api/questions' and method == 'POST':
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        # Simple auth - just check token exists
        token = data.get('token', '')
        if len(token) != 64:
            return {'statusCode': 401, 'headers': cors, 'body': json.dumps({'error': 'Unauthorized'})}
        
        quiz_id = data.get('quiz_id', 'onequiz')
        quiz = quizzes.get(quiz_id)
        
        if not quiz:
            # Try to load from onequiz.json
            try:
                with open(f'{base}/onequiz.json') as f:
                    quiz = json.load(f)
            except:
                return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Quiz not found'})}
        
        # Get 12 random questions
        questions = quiz.get('questions', [])
        if len(questions) > 12:
            questions = random.sample(questions, 12)
        
        # Add temp_id to each question
        for i, q in enumerate(questions):
            q['temp_id'] = f'q{i+1}'
        
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({
            'questions': questions,
            'quiz_id': quiz_id,
            'title': quiz.get('title', 'Quiz')
        })}
    
    # /api/result (POST)
    if path == '/api/result' and method == 'POST':
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        token = data.get('token', '')
        if len(token) != 64:
            return {'statusCode': 401, 'headers': cors, 'body': json.dumps({'error': 'Unauthorized'})}
        
        answers = data.get('answers', {})
        quiz_id = data.get('quiz_id', 'onequiz')
        quiz = quizzes.get(quiz_id)
        
        if not quiz:
            try:
                with open(f'{base}/onequiz.json') as f:
                    quiz = json.load(f)
            except:
                return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Quiz not found'})}
        
        # Calculate MBTI scores
        scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
        
        for q_id, opt_idx in answers.items():
            for q in quiz.get('questions', []):
                if str(q.get('qId')) == q_id or q.get('temp_id') == q_id:
                    opts = q.get('options', [])
                    if 0 <= int(opt_idx) < len(opts):
                        score = opts[int(opt_idx)].get('score', '')
                        if isinstance(score, str):
                            opp = {'E': 'I', 'I': 'E', 'S': 'N', 'N': 'S', 'T': 'F', 'F': 'T', 'J': 'P', 'P': 'J'}
                            if score in opp:
                                scores[score] += 1
                        elif isinstance(score, dict):
                            for k, v in score.items():
                                scores[k] = scores.get(k, 0) + v
                    break
        
        # Determine MBTI
        mbti = ''
        mbti += 'E' if scores['E'] >= scores['I'] else 'I'
        mbti += 'S' if scores['S'] >= scores['N'] else 'N'
        mbti += 'T' if scores['T'] >= scores['F'] else 'F'
        mbti += 'J' if scores['J'] >= scores['P'] else 'P'
        
        # Find result
        result = None
        for r in quiz.get('results', []):
            if r.get('mbtiType') == mbti or r.get('mbti') == mbti:
                result = r
                break
        if not result:
            result = quiz.get('results', [{}])[0]
        
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({
            'mbti_type': mbti,
            'result': result,
            'percentages': {
                'extrovert_introvert': 50,
                'sensing_intuition': 50,
                'thinking_feeling': 50,
                'judging_perceiving': 50
            }
        })}
    
    return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Not found'})}
