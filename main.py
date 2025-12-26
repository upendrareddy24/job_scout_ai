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

# Initialize Hunter's Memory (Expert Database)
try:
    import database
    db = database.get_db()
    logger.info("Hunter's Memory initialized.")
except Exception as e:
    logger.error(f"Database Init Failed: {e}")

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
        # Use intel to get a better profile than the basic parser
        profile = intel.extract_search_profile(text)
        return jsonify({
            "resume_text": text,
            "suggested_queries": profile.get("queries", []),
            "suggested_query": profile.get("queries", ["Senior Functional Safety Engineer"])[0],
            "primary_title": profile.get("primary_title"),
            "location": profile.get("location", "USA")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scout', methods=['POST'])
def scout():
    data = request.json
    query = data.get('query', 'Software Engineer')
    location = data.get('location', 'USA')
    resume_text = data.get('resume_text', '')
    
    raw_jobs = intel.scout_jobs(f"{query} in {location}")
    
    # Calculate local scores for instant UI updates
    processed_jobs = []
    for job in raw_jobs:
        if resume_text:
            job['local_score'] = intel.calculate_local_score(
                resume_text, 
                job.get('title', ''), 
                job.get('requirements', '')
            )
        else:
            job['local_score'] = 0
        processed_jobs.append(job)
        
    return jsonify({"jobs": processed_jobs})

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
    app.run(debug=False, port=int(os.getenv("PORT", 5011)))
