import os
import json
import logging
import requests
import hashlib
from typing import List, Dict, Any, Optional
try:
    from google import genai
except ImportError:
    genai = None
from dotenv import load_dotenv
from cache_manager import CacheManager

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class JobIntelligence:
    """Handles AI logic with caching and robust logging."""
    
    def __init__(self):
        self.perplexity_url = "https://api.perplexity.ai/chat/completions"
        self.perplexity_headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        self.cache = CacheManager()
        self.client = None
        
        if not genai:
            logger.error("SDK Error: google-genai package not found or import failed.")
        elif GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini Client initialized successfully.")
            except Exception as e:
                logger.error(f"Gemini Init Failed: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found in environment.")

    def scout_jobs(self, search_query: str) -> List[Dict[str, Any]]:
        """Uses Perplexity to find real-time job listings in the USA."""
        cache_key = f"scout_{search_query}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not PERPLEXITY_API_KEY:
            logger.error("Perplexity API key missing.")
            return []

        prompt = f"Find top 10 USA job openings for: '{search_query}'. Return ONLY JSON list of objects. Format: [{{'title': '...', 'company': '...', 'location': '...', 'url': '...', 'requirements': '...'}}]"

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a career scout. Return ONLY JSON."},
                {"role": "user", "content": prompt}
            ]
            # Removed invalid response_format
        }

        try:
            logger.info(f"Scouting for: {search_query}")
            response = requests.post(self.perplexity_url, headers=self.perplexity_headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Perplexity API Error {response.status_code}: {response.text}")
                return []
                
            content = response.json()["choices"][0]["message"]["content"]
            
            # Extract JSON from markdown if present
            content = content.strip()
            if "```" in content:
                # Handle cases like ```json ... ``` or just ``` ... ```
                content = content.split("```")[-2] # Get content between the last two sets of backticks
                if content.startswith("json\n"):
                    content = content[5:]
                elif content.startswith("json"):
                    content = content[4:]
            
            content = content.strip()
            jobs = json.loads(content)
            
            if isinstance(jobs, dict):
                for key in ["jobs", "data", "results"]:
                    if key in jobs and isinstance(jobs[key], list):
                        jobs = jobs[key]
                        break
            
            if isinstance(jobs, list):
                logger.info(f"Found {len(jobs)} jobs via Perplexity.")
                self.cache.set(cache_key, jobs)
                return jobs
            
            logger.warning(f"Unexpected Perplexity format: {content}")
            return []
        except Exception as e:
            logger.error(f"Perplexity scouting failed: {str(e)}")
            return []

    def analyze_match(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Uses Gemini to calculate compatibility."""
        inputs_hash = hashlib.md5((resume_text + job_description).encode()).hexdigest()
        cache_key = f"match_{inputs_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not self.client:
            return {"score": 50, "verdict": "Gemini intelligence not active.", "strengths": [], "gaps": []}
        
        prompt = f"Match Resume and Job. RESUME: {resume_text[:3000]} JOB: {job_description[:1500]}. Return JSON ONLY: {{ 'score': 0-100, 'verdict': '...', 'strengths': [], 'gaps': [] }}"

        try:
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            content = response.text.strip()
            
            # Robust JSON extraction
            if "```" in content:
                content = content.split("```")[-2]
                if content.startswith("json\n"):
                    content = content[5:]
                elif content.startswith("json"):
                    content = content[4:]
            
            content = content.strip()
            result = json.loads(content)
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Gemini analysis failed: {str(e)}")
            # Return a more descriptive failure to the UI
            return {
                "score": 0, 
                "verdict": f"AI Matcher Error: {str(e)[:100]}", 
                "strengths": ["Analysis failed"], 
                "gaps": ["Check API Key/Quota"]
            }

    def extract_search_profile(self, resume_text: str) -> Dict[str, Any]:
        """Analyzes a resume to extract multiple optimized job search queries."""
        resume_hash = hashlib.md5(resume_text.encode()).hexdigest()
        cache_key = f"profile_v2_{resume_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not self.client:
            logger.warning("No Gemini client to extract search profile. Using generic fallback.")
            return {"queries": ["Senior Functional Safety Engineer", "Safety Systems Architect", "ISO 26262 Engineer"], "location": "USA"}

        prompt = f"""
        Analyze this resume and generate a recruitment profile.
        RESUME: {resume_text[:4000]}
        
        Tasks:
        1. Identify the candidate's exact current/past job titles.
        2. Generate 5-7 highly specific "Optimized Search Queries" (3-5 words each) that would find high-paying matching jobs on LinkedIn/Indeed. 
           - Include variations of their current role.
           - Include roles they are qualified to "step up" into.
        3. Suggest the most likely preferred location (Default to 'USA').
        
        Return JSON ONLY: {{ "queries": ["query 1", "query 2", ...], "location": "...", "primary_title": "..." }}
        """
        
        try:
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            clean_content = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_content)
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Search profile extraction failed: {e}")
            return {"queries": ["Senior Functional Safety Engineer"], "location": "USA"}
