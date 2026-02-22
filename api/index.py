# -*- coding: utf-8 -*-
import json
import random
import hashlib
import os

# Try multiple possible paths
possible_dirs = [
    os.path.dirname(os.path.abspath(__file__)),
    '/var/task',
    os.getcwd()
]

BASE_DIR = None
for d in possible_dirs:
    if os.path.exists(os.path.join(d, 'quizzes')):
        BASE_DIR = d
        break

if BASE_DIR is None:
    BASE_DIR = possible_dirs[0]

# Load quizzes at cold start
_quizzes = {}
_config = {}
try:
    config_path = os.path.join(BASE_DIR, 'config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            _config = json.load(f)
    
    quizzes_dir = os.path.join(BASE_DIR, 'quizzes')
    if os.path.exists(quizzes_dir):
        for f in os.listdir(quizzes_dir):
            if f.endswith('.json'):
                qid = f.replace('.json', '')
                try:
                    with open(os.path.join(quizzes_dir, f)) as fp:
                        _quizzes[qid] = json.load(fp)
                except Exception as e:
                    print(f"Error loading {f}: {e}")
    print(f"Loaded {len(_quizzes)} quizzes from {quizzes_dir}")
    print(f"Quiz IDs: {list(_quizzes.keys())[:5]}")
except Exception as e:
    print(f"Init error: {e}")

def get_cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }

def app(environ, start_response):
    """WSGI app for Vercel"""
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    # Read body
    try:
        body_size = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(body_size).decode('utf-8') if body_size > 0 else ''
    except:
        body = ''
    
    headers = get_cors_headers()
    
    # Handle OPTIONS
    if method == 'OPTIONS':
        start_response('200 OK', list(headers.items()))
        return [b'']
    
    # /api/token
    if path == '/api/token':
        token = hashlib.sha256(str(random.random()).encode()).hexdigest()
        response = json.dumps({'token': token})
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # /api/quizzes (GET) - list all quizzes
    if path == '/api/quizzes' or path == '/api/quizzes/':
        lst = []
        for qid, q in _quizzes.items():
            lst.append({
                'quiz_id': qid,
                'title': q.get('title', 'Untitled'),
                'category': q.get('category', 'General'),
                'tags': q.get('tags', []),
                'description': q.get('description', '')
            })
        response = json.dumps({'quizzes': lst})
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # /api/quizzes/<id> (GET) - single quiz
    if path.startswith('/api/quizzes/') and method == 'GET':
        quiz_id = path.split('/api/quizzes/')[1]
        quiz = _quizzes.get(quiz_id)
        if not quiz:
            response = json.dumps({'error': 'Quiz not found', 'loaded': list(_quizzes.keys())})
            start_response('404 NOT FOUND', list(headers.items()) + [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]
        response = json.dumps({
            'quiz_id': quiz_id,
            'title': quiz.get('title', 'Untitled'),
            'category': quiz.get('category', 'General'),
            'tags': quiz.get('tags', []),
            'description': quiz.get('description', '')
        })
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # /api/tags (GET) - return tag library
    if path == '/api/tags' and method == 'GET':
        tags_file = os.path.join(QUIZZES_DIR, '..', 'data', 'tags.json')
        if os.path.exists(tags_file):
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
        else:
            tags_data = {}
        
        response = json.dumps(tags_data)
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # /api/questions (POST)
    if path == '/api/questions' and method == 'POST':
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        token = data.get('token', '')
        if len(token) != 64:
            response = json.dumps({'error': 'Unauthorized'})
            start_response('401 UNAUTHORIZED', list(headers.items()) + [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]
        
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        
        if not quiz:
            response = json.dumps({'error': 'Quiz not found', 'available': list(_quizzes.keys())})
            start_response('404 NOT FOUND', list(headers.items()) + [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]
        
        questions = quiz.get('questions', [])
        if len(questions) > 12:
            questions = random.sample(questions, 12)
        
        for i, q in enumerate(questions):
            q['temp_id'] = f'q{i+1}'
        
        response = json.dumps({
            'questions': questions,
            'quiz_id': quiz_id,
            'title': quiz.get('title', 'Quiz')
        })
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # /api/result (POST)
    if path == '/api/result' and method == 'POST':
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        token = data.get('token', '')
        if len(token) != 64:
            response = json.dumps({'error': 'Unauthorized'})
            start_response('401 UNAUTHORIZED', list(headers.items()) + [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]
        
        answers = data.get('answers', {})
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        
        if not quiz:
            response = json.dumps({'error': 'Quiz not found'})
            start_response('404 NOT FOUND', list(headers.items()) + [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]
        
        scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
        
        for q_id, opt_idx in answers.items():
            for q in quiz.get('questions', []):
                if str(q.get('qId')) == q_id or q.get('temp_id') == q_id:
                    opts = q.get('options', [])
                    if 0 <= int(opt_idx) < len(opts):
                        score = opts[int(opt_idx)].get('score', '')
                        if isinstance(score, str) and score in scores:
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
        
        # Calculate percentages based on actual scores
        total_ei = scores['E'] + scores['I'] if scores['E'] + scores['I'] > 0 else 1
        total_sn = scores['S'] + scores['N'] if scores['S'] + scores['N'] > 0 else 1
        total_tf = scores['T'] + scores['F'] if scores['T'] + scores['F'] > 0 else 1
        total_jp = scores['J'] + scores['P'] if scores['J'] + scores['P'] > 0 else 1
        
        response = json.dumps({
            'mbti_type': mbti,
            'result': result,
            'percentages': {
                'extrovert_introvert': int(scores['E'] * 100 / total_ei),
                'sensing_intuition': int(scores['S'] * 100 / total_sn),
                'thinking_feeling': int(scores['T'] * 100 / total_tf),
                'judging_perceiving': int(scores['J'] * 100 / total_jp)
            }
        })
        start_response('200 OK', list(headers.items()) + [('Content-Type', 'application/json')])
        return [response.encode('utf-8')]
    
    # Default: 404
    response = json.dumps({'error': 'Not found', 'path': path})
    start_response('404 NOT FOUND', list(headers.items()) + [('Content-Type', 'application/json')])
    return [response.encode('utf-8')]
