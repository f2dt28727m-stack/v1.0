from flask import Flask, request, jsonify
import json
import random
import hashlib
import os

app = Flask(__name__)

# Add CORS support
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Load common config
with open('config.json', 'r') as f:
    config = json.load(f)

# Load all quizzes from quizzes directory
quizzes = {}
quizzes_directory = 'quizzes'

if os.path.exists(quizzes_directory):
    for filename in os.listdir(quizzes_directory):
        if filename.endswith('.json'):
            quiz_id = os.path.splitext(filename)[0]
            try:
                with open(os.path.join(quizzes_directory, filename), 'r') as f:
                    quiz_data = json.load(f)
                    # Merge common scoring rules if not present
                    if 'scoringRules' not in quiz_data:
                        quiz_data['scoringRules'] = config['scoringRules']
                    quizzes[quiz_id] = quiz_data
                    print(f"Loaded quiz: {quiz_id}")
            except Exception as e:
                print(f"Error loading quiz {filename}: {e}")

# Also load the original onequiz.json for backward compatibility
with open('onequiz.json', 'r') as f:
    onequiz_data = json.load(f)
    if 'scoringRules' not in onequiz_data:
        onequiz_data['scoringRules'] = config['scoringRules']
    quizzes['onequiz'] = onequiz_data

# Simple API key for access control
API_KEY = config['commonSettings']['apiKey']

# Generate token for each session
def generate_token():
    return hashlib.sha256(str(random.random()).encode()).hexdigest()

# Validate API key
def validate_api_key(api_key):
    return api_key == API_KEY

# Validate token (simplified for demo)
def validate_token(token):
    return len(token) == 64  # Just check if it's a valid SHA256 hash

# Get all quizzes
@app.route('/api/quizzes', methods=['GET'])
def get_all_quizzes():
    quizzes_list = []
    for quiz_id, quiz_data in quizzes.items():
        quizzes_list.append({
            'quiz_id': quiz_id,
            'title': quiz_data.get('title', 'Untitled Quiz'),
            'category': quiz_data.get('category', 'General'),
            'tags': quiz_data.get('tags', []),
            'description': quiz_data.get('description', '')
        })
    return jsonify({'quizzes': quizzes_list})

# Get single quiz by ID
@app.route('/api/quizzes/<quiz_id>', methods=['GET'])
def get_single_quiz(quiz_id):
    quiz_data = quizzes.get(quiz_id)
    if not quiz_data:
        return jsonify({'error': 'Quiz not found'}), 404
    
    return jsonify({
        'quiz_id': quiz_id,
        'title': quiz_data.get('title', 'Untitled Quiz'),
        'category': quiz_data.get('category', 'General'),
        'tags': quiz_data.get('tags', []),
        'description': quiz_data.get('description', ''),
        'total_questions': len(quiz_data.get('questions', []))
    })

# Get random questions
@app.route('/api/questions', methods=['POST'])
def get_questions():
    data = request.get_json()
    api_key = data.get('api_key')
    token = data.get('token')
    quiz_id = data.get('quiz_id', 'onequiz')  # Default to onequiz if not specified
    
    if not validate_api_key(api_key) or not validate_token(token):
        return jsonify({'error': 'Unauthorized access'}), 401
    
    # Get quiz data
    quiz_data = quizzes.get(quiz_id, quizzes.get('onequiz'))
    
    # Shuffle questions and select 12
    shuffled_questions = random.sample(quiz_data['questions'], 12)
    
    # Add question IDs for tracking
    for i, q in enumerate(shuffled_questions):
        q['temp_id'] = f'q{i+1}'
    
    return jsonify({
        'questions': shuffled_questions,
        'quiz_id': quiz_id,
        'title': quiz_data['title']
    })

# Calculate result
@app.route('/api/result', methods=['POST'])
def get_result():
    data = request.get_json()
    api_key = data.get('api_key')
    token = data.get('token')
    answers = data.get('answers', {})
    quiz_id = data.get('quiz_id', 'onequiz')  # Default to onequiz if not specified
    
    if not validate_api_key(api_key) or not validate_token(token):
        return jsonify({'error': 'Unauthorized access'}), 401
    
    # Get quiz data
    quiz_data = quizzes.get(quiz_id, quizzes.get('onequiz'))
    
    # Calculate MBTI score
    dimension_scores = {
        'E': 0, 'I': 0,
        'S': 0, 'N': 0,
        'T': 0, 'F': 0,
        'J': 0, 'P': 0
    }
    
    # Process answers (simplified - in real app, you'd validate questions)
    for q_id, option_index in answers.items():
        # Find the question (in real app, you'd store session questions)
        for question in quiz_data['questions']:
            if str(question.get('qId')) == q_id or question.get('temp_id') == q_id:
                if 0 <= int(option_index) < len(question['options']):
                    option = question['options'][int(option_index)]
                    score = option['score']
                    if isinstance(score, dict):
                        # Handle score as object with multiple dimensions
                        for dim, s in score.items():
                            dimension_scores[dim] += s
                    elif isinstance(score, str):
                        # Handle score as single dimension string
                        # For single dimension, we need to determine the opposite
                        opposite = {
                            'E': 'I', 'I': 'E',
                            'S': 'N', 'N': 'S',
                            'T': 'F', 'F': 'T',
                            'J': 'P', 'P': 'J'
                        }.get(score, None)
                        if opposite:
                            dimension_scores[score] += 1
                            dimension_scores[opposite] += 0
                break
    
    # Determine MBTI type
    mbti_type = ''
    mbti_type += 'E' if dimension_scores['E'] > dimension_scores['I'] else 'I'
    mbti_type += 'S' if dimension_scores['S'] > dimension_scores['N'] else 'N'
    mbti_type += 'T' if dimension_scores['T'] > dimension_scores['F'] else 'F'
    mbti_type += 'J' if dimension_scores['J'] > dimension_scores['P'] else 'P'
    
    # Find result - handle different field names for MBTI type
    result = None
    for r in quiz_data['results']:
        if r.get('mbtiType') == mbti_type or r.get('mbti') == mbti_type:
            result = r
            break
    if not result:
        # If no match found, use the first result as fallback
        result = quiz_data['results'][0]
    
    # Calculate percentages
    percentages = {
        'extrovert_introvert': round((dimension_scores['E'] / (dimension_scores['E'] + dimension_scores['I'])) * 100) if (dimension_scores['E'] + dimension_scores['I']) > 0 else 50,
        'sensing_intuition': round((dimension_scores['S'] / (dimension_scores['S'] + dimension_scores['N'])) * 100) if (dimension_scores['S'] + dimension_scores['N']) > 0 else 50,
        'thinking_feeling': round((dimension_scores['T'] / (dimension_scores['T'] + dimension_scores['F'])) * 100) if (dimension_scores['T'] + dimension_scores['F']) > 0 else 50,
        'judging_perceiving': round((dimension_scores['J'] / (dimension_scores['J'] + dimension_scores['P'])) * 100) if (dimension_scores['J'] + dimension_scores['P']) > 0 else 50
    }
    
    return jsonify({
        'mbti_type': mbti_type,
        'result': result,
        'percentages': percentages
    })

# Get token
@app.route('/api/token', methods=['GET'])
def get_token():
    return jsonify({'token': generate_token()})

# Serve index.html for root path
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

# Serve other HTML files
@app.route('/<path:path>')
def serve_file(path):
    if path.endswith('.html'):
        return app.send_static_file(path)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
