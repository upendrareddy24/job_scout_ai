import os
import logging
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from intelligence import JobIntelligence
from resume_parser import ResumeParser

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'resumes'
intel = JobIntelligence()
parser = ResumeParser()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        text = parser.extract_text(filepath)
        structured = parser.get_structured_data(text)
        return jsonify({
            "resume_text": text,
            "suggested_query": structured.get("search_query"),
            "location": structured.get("location")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scout', methods=['POST'])
def scout():
    # In a full flow, we'd take a resume, extract query, then scout.
    # For now, let's allow a manual query check too.
    data = request.json
    query = data.get('query', 'Software Engineer')
    location = data.get('location', 'USA')
    
    jobs = intel.scout_jobs(f"{query} in {location}")
    return jsonify({"jobs": jobs})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    resume_text = data.get('resume_text', '')
    job_desc = data.get('job_description', '')
    
    if not resume_text or not job_desc:
        return jsonify({"error": "Missing resume or job description"}), 400
        
    match = intel.analyze_match(resume_text, job_desc)
    return jsonify(match)

if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv("PORT", 5011)))
