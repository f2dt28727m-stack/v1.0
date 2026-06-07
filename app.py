from flask import Flask, request, jsonify, send_from_directory
import json
import random
import hashlib
import os

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

# Load common config
config_path = get_file_path('config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Load all quizzes from quizzes directory
quizzes = {}
quizzes_directory = os.path.join(BASE_DIR, 'quizzes')

if os.path.exists(quizzes_directory):
    for filename in os.listdir(quizzes_directory):
        if filename.endswith('.json'):
            quiz_id = os.path.splitext(filename)[0]
            try:
                with open(os.path.join(quizzes_directory, filename), 'r') as f:
                    quiz_data = json.load(f)
                    if 'scoringRules' not in quiz_data:
                        quiz_data['scoringRules'] = config['scoringRules']
                    quizzes[quiz_id] = quiz_data
                    print(f"Loaded quiz: {quiz_id}")
            except Exception as e:
                print(f"Error loading quiz {filename}: {e}")

# Also load the original onequiz.json for backward compatibility
onequiz_path = get_file_path('onequiz.json')
if os.path.exists(onequiz_path):
    with open(onequiz_path, 'r') as f:
        onequiz_data = json.load(f)
        if 'scoringRules' not in onequiz_data:
            onequiz_data['scoringRules'] = config['scoringRules']
        quizzes['onequiz'] = onequiz_data

API_KEY = config['commonSettings']['apiKey']

def generate_token():
    return hashlib.sha256(str(random.random()).encode()).hexdigest()

def validate_api_key(api_key):
    return api_key == API_KEY

def validate_token(token):
    return len(token) == 64

@app.route('/api/quizzes', methods=['GET'])
def get_all_quizzes():
    from flask import Response
    import json as _json
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
    return Response(_json.dumps({'quizzes': quizzes_list}), mimetype='application/json')

@app.route('/api/quizzes/<quiz_id>', methods=['GET'])
def get_single_quiz(quiz_id):
    from flask import Response
    import json as _json
    quiz_data = quizzes.get(quiz_id)
    if not quiz_data:
        return jsonify({'error': 'Quiz not found'}), 404

    return Response(_json.dumps({
        'quiz_id': quiz_id,
        'title': quiz_data.get('title', 'Untitled Quiz'),
        'category': quiz_data.get('category', 'General'),
        'tags': quiz_data.get('tags', []),
        'description': quiz_data.get('description', ''),
        'emoji': quiz_data.get('emoji', ['❓', '✨', '🎯'])
    }), mimetype='application/json')

@app.route('/api/questions', methods=['POST'])
def get_questions():
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
    from flask import Response
    import json as _json
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

    return Response(_json.dumps({
        'mbti_type': mbti_type,
        'result': result,
        'percentages': {
            'extrovert_introvert': int(dimension_scores['E'] * 100 / total_ei),
            'sensing_intuition': int(dimension_scores['S'] * 100 / total_sn),
            'thinking_feeling': int(dimension_scores['T'] * 100 / total_tf),
            'judging_perceiving': int(dimension_scores['J'] * 100 / total_jp)
        }
    }), mimetype='application/json')

@app.route('/api/token', methods=['GET'])
def get_token():
    return jsonify({'token': generate_token()})

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Return tag library from data/tags.json (matches production)."""
    from flask import Response
    import json as _json
    tags_path = os.path.join(BASE_DIR, 'data', 'tags.json')
    if not os.path.exists(tags_path):
        return Response('{}', mimetype='application/json')
    with open(tags_path, 'r', encoding='utf-8') as f:
        # Use json.dumps to preserve insertion order (matches Vercel api/index.py)
        return Response(_json.dumps(_json.load(f)), mimetype='application/json')

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_file(path):
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
