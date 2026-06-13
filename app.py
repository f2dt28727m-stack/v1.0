from flask import Flask, request, jsonify, send_from_directory, Response
import json
import random
import hashlib
import os
import re
import sys
import time
import threading
from collections import deque

# Make api/index.py importable as a module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import index as seo  # noqa: E402  -- shares _quizzes, helpers, build_* functions

app = Flask(__name__, static_folder='static')

# Detect Vercel environment
IS_VERCEL = os.environ.get('VERCEL', '') == '1'

# Get the correct base directory for Vercel
if IS_VERCEL:
    BASE_DIR = '/var/task'
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"Running on Vercel: {IS_VERCEL}, Base dir: {BASE_DIR}")

def get_file_path(filename):
    """Get the correct file path whether locally or on Vercel"""
    return os.path.join(BASE_DIR, filename)

# Reuse the quiz dict and helpers from api/index.py
quizzes = seo._quizzes

# ---------- Rate limit (mirrors api/index.py) ----------
_request_log: dict = {}
_rl_lock = threading.Lock()
RATE_LIMITS = seo.RATE_LIMITS


def _check_rate_limit(bucket):
    """Return (allowed, headers, retry_after). Falls back to in-memory only;
    api/index.py uses Upstash when env vars are set, this Flask version stays local."""
    ip = request.headers.get('CF-Connecting-IP') or \
         (request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or None) or \
         request.headers.get('X-Real-IP') or request.remote_addr or 'unknown'
    max_req, window_s = RATE_LIMITS.get(bucket, (60, 60))
    key = f"{bucket}:{ip}"
    now = time.time()
    with _rl_lock:
        log = _request_log.setdefault(key, deque())
        while log and log[0] < now - window_s:
            log.popleft()
        if len(log) >= max_req:
            retry_after = int(window_s - (now - log[0])) if log else window_s
            return False, {
                'X-RateLimit-Limit': str(max_req),
                'X-RateLimit-Remaining': '0',
                'Retry-After': str(retry_after),
            }, retry_after
        log.append(now)
        return True, {
            'X-RateLimit-Limit': str(max_req),
            'X-RateLimit-Remaining': str(max_req - len(log)),
        }, 0


def _enforce(bucket):
    """Run global + bucket rate limit; if blocked, return a Flask response, else None."""
    for b in ('global', bucket):
        allowed, hdrs, _ = _check_rate_limit(b)
        if not allowed:
            resp = jsonify({'error': f'Rate limit exceeded ({b})'})
            resp.status_code = 429
            for k, v in hdrs.items():
                resp.headers[k] = v
            return resp
    return None


def generate_token():
    return hashlib.sha256(str(random.random()).encode()).hexdigest()

def validate_token(token):
    return len(token) == 64

@app.route('/api/quizzes', methods=['GET'])
def get_all_quizzes():
    blocked = _enforce('read')
    if blocked:
        return blocked
    quizzes_list = []
    for quiz_id, quiz_data in quizzes.items():
        if quiz_id == 'onequiz':
            continue
        quizzes_list.append({
            'quiz_id': quiz_id,
            'title': quiz_data.get('title', 'Untitled Quiz'),
            'category': quiz_data.get('category', 'General'),
            'tags': quiz_data.get('tags', []),
            'description': quiz_data.get('description', '')
        })
    # Sort by quiz_id for stable, deterministic order (matches production)
    quizzes_list.sort(key=lambda x: x['quiz_id'])
    return Response(json.dumps({'quizzes': quizzes_list}, ensure_ascii=False), mimetype='application/json')

@app.route('/api/quizzes/<quiz_id>', methods=['GET'])
def get_single_quiz(quiz_id):
    blocked = _enforce('read')
    if blocked:
        return blocked
    if not re.match(r'^[A-Za-z0-9_]+$', quiz_id):
        return jsonify({'error': 'Invalid id'}), 400
    quiz_data = quizzes.get(quiz_id)
    if not quiz_data:
        return jsonify({'error': 'Quiz not found'}), 404

    return Response(json.dumps({
        'quiz_id': quiz_id,
        'title': quiz_data.get('title', 'Untitled Quiz'),
        'category': quiz_data.get('category', 'General'),
        'tags': quiz_data.get('tags', []),
        'description': quiz_data.get('description', ''),
        'emoji': quiz_data.get('emoji', ['❓', '✨', '🎯'])
    }, ensure_ascii=False), mimetype='application/json')

@app.route('/api/questions', methods=['POST'])
def get_questions():
    blocked = _enforce('questions')
    if blocked:
        return blocked
    data = request.get_json() or {}
    token = data.get('token', '')
    quiz_id = data.get('quiz_id', 'quiz_1')

    if len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401

    quiz_data = quizzes.get(quiz_id)
    if not quiz_data:
        return jsonify({'error': 'Quiz not found', 'available': list(quizzes.keys())}), 404

    questions = quiz_data.get('questions', [])
    for i, q in enumerate(questions):
        q['temp_id'] = f'q{i+1}'

    return jsonify({
        'questions': questions,
        'quiz_id': quiz_id,
        'title': quiz_data.get('title', 'Quiz')
    })

@app.route('/api/result', methods=['POST'])
def get_result():
    blocked = _enforce('result')
    if blocked:
        return blocked
    data = request.get_json() or {}
    token = data.get('token', '')
    answers = data.get('answers', {})
    quiz_id = data.get('quiz_id', 'quiz_1')

    if len(token) != 64:
        return jsonify({'error': 'Unauthorized'}), 401

    quiz_data = quizzes.get(quiz_id)
    if not quiz_data:
        return jsonify({'error': 'Quiz not found'}), 404

    dimension_scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}

    for q_id, option_index in answers.items():
        for question in quiz_data.get('questions', []):
            if str(question.get('qId')) == q_id or question.get('temp_id') == q_id:
                opts = question.get('options', [])
                try:
                    if 0 <= int(option_index) < len(opts):
                        score = opts[int(option_index)].get('score', '')
                        if isinstance(score, str) and score in dimension_scores:
                            dimension_scores[score] += 1
                        elif isinstance(score, dict):
                            for k, v in score.items():
                                if k in dimension_scores:
                                    dimension_scores[k] += v
                except (ValueError, TypeError):
                    pass
                break

    mbti_type = ''
    mbti_type += 'E' if dimension_scores['E'] >= dimension_scores['I'] else 'I'
    mbti_type += 'S' if dimension_scores['S'] >= dimension_scores['N'] else 'N'
    mbti_type += 'T' if dimension_scores['T'] >= dimension_scores['F'] else 'F'
    mbti_type += 'J' if dimension_scores['J'] >= dimension_scores['P'] else 'P'

    result = None
    for r in quiz_data.get('results', []):
        if r.get('mbtiType') == mbti_type or r.get('mbti') == mbti_type:
            result = r
            break
    if not result:
        result = quiz_data.get('results', [{}])[0]

    total_ei = dimension_scores['E'] + dimension_scores['I'] if dimension_scores['E'] + dimension_scores['I'] > 0 else 1
    total_sn = dimension_scores['S'] + dimension_scores['N'] if dimension_scores['S'] + dimension_scores['N'] > 0 else 1
    total_tf = dimension_scores['T'] + dimension_scores['F'] if dimension_scores['T'] + dimension_scores['F'] > 0 else 1
    total_jp = dimension_scores['J'] + dimension_scores['P'] if dimension_scores['J'] + dimension_scores['P'] > 0 else 1

    return Response(json.dumps({
        'mbti_type': mbti_type,
        'result': result,
        'percentages': {
            'extrovert_introvert': int(dimension_scores['E'] * 100 / total_ei),
            'sensing_intuition': int(dimension_scores['S'] * 100 / total_sn),
            'thinking_feeling': int(dimension_scores['T'] * 100 / total_tf),
            'judging_perceiving': int(dimension_scores['J'] * 100 / total_jp)
        }
    }, ensure_ascii=False), mimetype='application/json')

@app.route('/api/token', methods=['POST'])
def get_token():
    blocked = _enforce('token')
    if blocked:
        return blocked
    data = request.get_json(silent=True) or {}
    turnstile_token = data.get('turnstile_token', '')
    if not seo.verify_turnstile(turnstile_token,
                                 remote_ip=request.headers.get('CF-Connecting-IP')):
        return jsonify({'error': 'Turnstile verification failed'}), 401
    return jsonify({'token': generate_token()})

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Return tag library from data/tags.json (matches production)."""
    blocked = _enforce('read')
    if blocked:
        return blocked
    tags_path = os.path.join(BASE_DIR, 'data', 'tags.json')
    if not os.path.exists(tags_path):
        return Response('{}', mimetype='application/json')
    with open(tags_path, 'r', encoding='utf-8') as f:
        # Use json.dumps to preserve insertion order (matches Vercel api/index.py)
        return Response(json.dumps(json.load(f)), mimetype='application/json')

# ---------- SEO routes (reuses build_* from api/index.py) ----------
@app.route('/robots.txt')
def robots():
    return Response(seo.build_robots_txt(), mimetype='text/plain; charset=utf-8')

@app.route('/sitemap.xml')
def sitemap():
    return Response(seo.build_sitemap_xml(), mimetype='application/xml; charset=utf-8')

@app.route('/quiz/<path:rest>')
def quiz_detail(rest):
    """SSR detail page (reuses build_quiz_html from api/index.py)."""
    rest = (rest or '').rstrip('/')
    quiz_id = rest.split('-', 1)[0] if '-' in rest else rest
    if not re.match(r'^[A-Za-z0-9_]+$', quiz_id):
        return Response('Invalid quiz id', status=404, mimetype='text/plain')
    summary = seo.get_quiz_summary(quiz_id)
    if not summary:
        return Response('<!doctype html><meta charset="utf-8"><title>Not found</title>'
                        '<h1>Quiz not found</h1><p><a href="/">Back to home</a></p>',
                        status=404, mimetype='text/html; charset=utf-8')
    return Response(seo.build_quiz_html(quiz_id, summary), mimetype='text/html; charset=utf-8')

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    # /api/* and /quiz/* have explicit routes above; if they didn't match
    # (e.g. wrong method, bad path), let Flask return 404/405 instead of
    # shadowing them with this catch-all.
    if path.startswith(('api/', 'quiz/')):
        return jsonify({'error': 'Not found'}), 404
    if path.endswith('.html'):
        try:
            return send_from_directory(BASE_DIR, path)
        except:
            return jsonify({'error': 'File not found'}), 404
    # Serve static files from quizzes, css, js, data directories
    for static_dir in ['quizzes', 'css', 'js', 'data', 'static']:
        static_path = os.path.join(BASE_DIR, static_dir)
        if os.path.exists(os.path.join(static_path, path)):
            return send_from_directory(static_path, path)
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
