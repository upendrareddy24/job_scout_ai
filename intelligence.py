import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from google import genai
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
    """Handles AI logic with caching and prompt optimization using the new google-genai SDK."""
    
    def __init__(self):
        self.perplexity_url = "https://api.perplexity.ai/chat/completions"
        self.perplexity_headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        self.cache = CacheManager()
        self.client = None
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)

    def scout_jobs(self, search_query: str) -> List[Dict[str, Any]]:
        """Uses Perplexity to find real-time job listings in the USA (with caching)."""
        cache_key = f"scout_{search_query}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached jobs for: {search_query}")
            return cached_data

        if not PERPLEXITY_API_KEY:
            logger.error("Perplexity API key missing.")
            return []

        prompt = f"Find top 10 USA job openings for: '{search_query}'. Return ONLY JSON list: [{{'title': '...', 'company': '...', 'location': '...', 'url': '...', 'requirements': '...'}}]"

        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "system", "content": "You are a career scout. Return ONLY JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(self.perplexity_url, headers=self.perplexity_headers, json=payload, timeout=30)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            
            # Perplexity might wrap JSON in backticks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            jobs = json.loads(content)
            if isinstance(jobs, dict):
                for key in ["jobs", "data", "results"]:
                    if key in jobs:
                        jobs = jobs[key]
                        break
            
            if isinstance(jobs, list):
                self.cache.set(cache_key, jobs)
                return jobs
            return []
        except Exception as e:
            logger.error(f"Perplexity scouting failed: {e}")
            return []

    def analyze_match(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Uses Gemini to calculate compatibility (with caching)."""
        import hashlib
        inputs_hash = hashlib.md5((resume_text + job_description).encode()).hexdigest()
        cache_key = f"match_{inputs_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info("Returning cached match analysis.")
            return cached_data

        if not self.client:
            return {"score": 50, "verdict": "Gemini key missing.", "strengths": [], "gaps": []}
        
        prompt = f"""
        Analyze match between Resume and Job. 
        RESUME: {resume_text[:2000]} 
        JOB: {job_description[:1000]}
        Return JSON ONLY: {{ "score": 0-100, "verdict": "brief text", "strengths": ["s1", "s2", "s3"], "gaps": ["g1", "g2", "g3"] }}
        """

        try:
            response = self.client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            clean_content = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_content)
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return {"score": 0, "verdict": f"Match analysis failed: {str(e)}", "strengths": [], "gaps": []}

    def extract_search_profile(self, resume_text: str) -> Dict[str, Any]:
        """Analyzes a resume to determine best search query (with caching)."""
        import hashlib
        resume_hash = hashlib.md5(resume_text.encode()).hexdigest()
        cache_key = f"profile_{resume_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not self.client:
            return {"query": "Software Engineer", "location": "USA"}

        prompt = f"Extract optimized job search query from Resume: {resume_text[:2000]}. Return JSON ONLY: {{ 'query': '...', 'location': '...' }}"
        
        try:
            response = self.client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            clean_content = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_content)
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Search profile extraction failed: {e}")
            return {"query": "Software Engineer", "location": "USA"}
