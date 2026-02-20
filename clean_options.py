import json
import os
import re

# Function to remove content in parentheses from options
def clean_options(option_text):
    # Remove content in parentheses (including the parentheses themselves)
    cleaned_text = re.sub(r'\s*\([^)]*\)', '', option_text)
    return cleaned_text.strip()

# Process all quiz files in the quizzes directory
def process_quiz_files(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if the file has questions
                if 'questions' in data:
                    updated = False
                    for question in data['questions']:
                        if 'options' in question:
                            for option in question['options']:
                                if 'text' in option:
                                    original_text = option['text']
                                    cleaned_text = clean_options(original_text)
                                    if cleaned_text != original_text:
                                        option['text'] = cleaned_text
                                        updated = True
                    
                    if updated:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"Updated: {filename}")
                    else:
                        print(f"No changes needed: {filename}")
                else:
                    print(f"No questions found: {filename}")
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    quizzes_directory = os.path.join(os.path.dirname(__file__), 'quizzes')
    print(f"Processing quiz files in: {quizzes_directory}")
    process_quiz_files(quizzes_directory)
    print("Processing completed!")
