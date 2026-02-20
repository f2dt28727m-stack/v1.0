import json
import random
import hashlib
import os

BASE_DIR = '/var/task'

# Load config and quizzes at module load time
_quizzes = {}
_config = {}
_api_key = ''

def _init():
    global _quizzes, _config, _api_key
    try:
        with open(os.path.join(BASE_DIR, 'config.json')) as f:
            _config = json.load(f)
        _api_key = _config.get('commonSettings', {}).get('apiKey', '')
        
        quizzes_dir = os.path.join(BASE_DIR, 'quizzes')
        if os.path.exists(quizzes_dir):
            for f in os.listdir(quizzes_dir):
                if f.endswith('.json'):
                    qid = f.replace('.json', '')
                    try:
                        with open(os.path.join(quizzes_dir, f)) as fp:
                            _quizzes[qid] = json.load(fp)
                    except:
                        pass
    except Exception as e:
        print(f"Init error: {e}")

_init()

def handler(request, context=None):
    """Vercel Python handler - takes request dict and returns response dict"""
    
    # Handle both dict-style and object-style requests
    if hasattr(request, 'url'):
        # It's a WSGI-style request object
        path = request.url.path
        method = request.method
        body = request.get_data(as_text=True) or ''
        headers = dict(request.headers)
    else:
        # It's a Vercel event dict
        path = request.get('path', '/')
        method = request.get('httpMethod', 'GET')
        body = request.get('body', '')
        if isinstance(body, str):
            try:
                body = body.encode('utf-8')
            except:
                pass
        headers = request.get('headers', {})
    
    cors = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
    
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors, 'body': ''}
    
    # Parse body if POST
    data = {}
    if body:
        try:
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body) if body else {}
        except:
            pass
    
    # Route: /api/token
    if path == '/api/token':
        token = hashlib.sha256(str(random.random()).encode()).hexdigest()
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({'token': token})}
    
    # Route: /api/quizzes (GET)
    if path == '/api/quizzes' and method == 'GET':
        lst = []
        for qid, q in _quizzes.items():
            lst.append({
                'quiz_id': qid,
                'title': q.get('title', 'Untitled'),
                'category': q.get('category', 'General'),
                'tags': q.get('tags', []),
                'description': q.get('description', '')
            })
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({'quizzes': lst})}
    
    # Route: /api/questions (POST)
    if path == '/api/questions' and method == 'POST':
        token = data.get('token', '')
        if len(token) != 64:
            return {'statusCode': 401, 'headers': cors, 'body': json.dumps({'error': 'Unauthorized'})}
        
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        
        if not quiz:
            return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Quiz not found'})}
        
        questions = quiz.get('questions', [])
        if len(questions) > 12:
            questions = random.sample(questions, 12)
        
        for i, q in enumerate(questions):
            q['temp_id'] = f'q{i+1}'
        
        return {'statusCode': 200, 'headers': cors, 'body': json.dumps({
            'questions': questions,
            'quiz_id': quiz_id,
            'title': quiz.get('title', 'Quiz')
        })}
    
    # Route: /api/result (POST)
    if path == '/api/result' and method == 'POST':
        token = data.get('token', '')
        if len(token) != 64:
            return {'statusCode': 401, 'headers': cors, 'body': json.dumps({'error': 'Unauthorized'})}
        
        answers = data.get('answers', {})
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        
        if not quiz:
            return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Quiz not found'})}
        
        scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
        
        for q_id, opt_idx in answers.items():
            for q in quiz.get('questions', []):
                if str(q.get('qId')) == q_id or q.get('temp_id') == q_id:
                    opts = q.get('options', [])
                    if 0 <= int(opt_idx) < len(opts):
                        score = opts[int(opt_idx)].get('score', '')
                        if isinstance(score, str):
                            if score in scores:
                                scores[score] += 1
                        elif isinstance(score, dict):
                            for k, v in score.items():
                                if k in scores:
                                    scores[k] += v
                    break
        
        mbti = ''
        mbti += 'E' if scores['E'] >= scores['I'] else 'I'
        mbti += 'S' if scores['S'] >= scores['N'] else 'N'
        mbti += 'T' if scores['T'] >= scores['F'] else 'F'
        mbti += 'J' if scores['J'] >= scores['P'] else 'P'
        
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
            'percentages': {'extrovert_introvert': 50, 'sensing_intuition': 50, 'thinking_feeling': 50, 'judging_perceiving': 50}
        })}
    
    return {'statusCode': 404, 'headers': cors, 'body': json.dumps({'error': 'Not found'})}
