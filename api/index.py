# -*- coding: utf-8 -*-
import json
import random
import hashlib
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_DIR = '/var/task'

# Load config and quizzes at startup
_quizzes = {}
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
    print(f"Loaded {len(_quizzes)} quizzes")
except Exception as e:
    print(f"Init error: {e}")
    _api_key = ''

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.route('/api/token', methods=['GET'])
def get_token():
    token = hashlib.sha256(str(random.random()).encode()).hexdigest()
    return jsonify({'token': token})

@app.route('/api/quizzes', methods=['GET'])
def get_quizzes():
    lst = []
    for qid, q in _quizzes.items():
        lst.append({
            'quiz_id': qid,
            'title': q.get('title', 'Untitled'),
            'category': q.get('category', 'General'),
            'tags': q.get('tags', []),
            'description': q.get('description', '')
        })
    return jsonify({'quizzes': lst})

@app.route('/api/quizzes/<quiz_id>', methods=['GET'])
def get_single_quiz(quiz_id):
    quiz = _quizzes.get(quiz_id)
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    return jsonify({
        'quiz_id': quiz_id,
        'title': quiz.get('title', 'Untitled'),
        'category': quiz.get('category', 'General'),
        'tags': quiz.get('tags', []),
        'description': quiz.get('description', '')
    })

@app.route('/api/questions', methods=['POST'])
def get_questions():
    data = request.get_json() or {}
    token = data.get('token', '')
    
    if len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401
    
    quiz_id = data.get('quiz_id', 'quiz_1')
    quiz = _quizzes.get(quiz_id)
    
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    questions = quiz.get('questions', [])
    if len(questions) > 12:
        questions = random.sample(questions, 12)
    
    for i, q in enumerate(questions):
        q['temp_id'] = f'q{i+1}'
    
    return jsonify({
        'questions': questions,
        'quiz_id': quiz_id,
        'title': quiz.get('title', 'Quiz')
    })

@app.route('/api/result', methods=['POST'])
def get_result():
    data = request.get_json() or {}
    token = data.get('token', '')
    
    if len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401
    
    answers = data.get('answers', {})
    quiz_id = data.get('quiz_id', 'quiz_1')
    quiz = _quizzes.get(quiz_id)
    
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
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

# Vercel handler
def handler(event, context=None):
    return app(event, context)
