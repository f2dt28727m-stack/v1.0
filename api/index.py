import json
import random
import hashlib
import os
import sys
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from urllib.parse import urlparse, parse_qs

# Vercel Python - use Flask
from flask import Flask, request, jsonify

app = Flask(__name__, static_folder='static')

BASE_DIR = '/var/task'

# Load config and quizzes at startup
try:
    config_path = os.path.join(BASE_DIR, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    quizzes = {}
    quizzes_dir = os.path.join(BASE_DIR, 'quizzes')
    
    if os.path.exists(quizzes_dir):
        for filename in os.listdir(quizzes_dir):
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
    
    onequiz_path = os.path.join(BASE_DIR, 'onequiz.json')
    with open(onequiz_path, 'r') as f:
        onequiz_data = json.load(f)
        if 'scoringRules' not in onequiz_data:
            onequiz_data['scoringRules'] = config['scoringRules']
        quizzes['onequiz'] = onequiz_data
    
    API_KEY = config['commonSettings']['apiKey']
    print(f"Loaded {len(quizzes)} quizzes")
except Exception as e:
    print(f"Init error: {e}", file=sys.stderr)
    quizzes = {}
    API_KEY = ''

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/token', methods=['GET'])
def get_token():
    token = hashlib.sha256(str(random.random()).encode()).hexdigest()
    return jsonify({'token': token})

@app.route('/api/quizzes', methods=['GET'])
def get_quizzes():
    quizzes_list = []
    for quiz_id, quiz_data in quizzes.items():
        quizzes_list.append({
            'quiz_id': quiz_id,
            'title': quiz_data.get('title', 'Untitled'),
            'category': quiz_data.get('category', 'General'),
            'tags': quiz_data.get('tags', []),
            'description': quiz_data.get('description', '')
        })
    return jsonify({'quizzes': quizzes_list})

@app.route('/api/questions', methods=['POST'])
def get_questions():
    data = request.get_json() or {}
    api_key = data.get('api_key', '')
    token = data.get('token', '')
    quiz_id = data.get('quiz_id', 'onequiz')
    
    if api_key != API_KEY or len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401
    
    quiz_data = quizzes.get(quiz_id, quizzes.get('onequiz'))
    if not quiz_data:
        return jsonify({'error': 'Quiz not found'}), 404
    
    shuffled = random.sample(quiz_data['questions'], min(12, len(quiz_data['questions'])))
    
    for i, q in enumerate(shuffled):
        q['temp_id'] = f'q{i+1}'
    
    return jsonify({
        'questions': shuffled,
        'quiz_id': quiz_id,
        'title': quiz_data['title']
    })

@app.route('/api/result', methods=['POST'])
def get_result():
    data = request.get_json() or {}
    api_key = data.get('api_key', '')
    token = data.get('token', '')
    answers = data.get('answers', {})
    quiz_id = data.get('quiz_id', 'onequiz')
    
    if api_key != API_KEY or len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401
    
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
    
    return jsonify({
        'mbti_type': mbti,
        'result': result,
        'percentages': {
            'extrovert_introvert': 50,
            'sensing_intuition': 50,
            'thinking_feeling': 50,
            'judging_perceiving': 50
        }
    })

@app.route('/')
def serve_index():
    try:
        with open(os.path.join(BASE_DIR, 'index.html'), 'r') as f:
            return f.read(), 200, {'Content-Type': 'text/html'}
    except Exception as e:
        return f'Not found: {e}', 404

@app.route('/<path:path>')
def serve_file(path):
    if path.endswith('.html'):
        try:
            with open(os.path.join(BASE_DIR, path), 'r') as f:
                return f.read(), 200, {'Content-Type': 'text/html'}
        except:
            return 'Not found', 404
    return 'Not found', 404

# Vercel handler
def handler(event, context):
    return app(event, context)
