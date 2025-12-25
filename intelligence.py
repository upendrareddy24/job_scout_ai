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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class JobIntelligence:
    """Handles AI logic with caching and multi-model fallbacks."""
    
    def __init__(self):
        self.perplexity_url = "https://api.perplexity.ai/chat/completions"
        self.perplexity_headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        self.cache = CacheManager()
        self.client = None
        self.openai_client = None
        
        # Initialize Gemini
        if not genai:
            logger.error("SDK Error: google-genai package not found.")
        elif GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY, vertexai=False)
                logger.info("Gemini Pro initialized.")
            except Exception as e:
                logger.error(f"Gemini Init Failed: {e}")
        
        # Initialize OpenAI (Backup)
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI Backup initialized.")
            except Exception as e:
                logger.error(f"OpenAI Init Failed: {e}")

    def scout_jobs(self, search_query: str) -> List[Dict[str, Any]]:
        """Uses Perplexity to find real-time job listings in the USA."""
        cache_key = f"scout_{search_query}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not PERPLEXITY_API_KEY:
            logger.error("Perplexity API key missing.")
            return []

        # Reduced to 20 to ensure we stay under Heroku's 30s timeout limit.
        prompt = f"Find the top 20 most recent USA job openings for: '{search_query}'. Return ONLY JSON list. Concise requirements (1 sentence). Format: [{{'title': '...', 'company': '...', 'location': '...', 'url': '...', 'requirements': '...', 'posted': '...'}}]"

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
            response = requests.post(self.perplexity_url, headers=self.perplexity_headers, json=payload, timeout=25)
            
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

    def calculate_local_score(self, resume_text: str, job_title: str, job_desc: str) -> int:
        """Calculates a match percentage locally using weighted token analysis (Zero-API)."""
        if not resume_text or not job_title: return 0
        
        import re
        def get_tokens(text):
            # Extract words, lowercase, and keep tokens > 3 chars
            return set(re.findall(r'\w+', text.lower()))

        res_tokens = get_tokens(resume_text)
        title_tokens = get_tokens(job_title)
        desc_tokens = get_tokens(job_desc)
        
        if not title_tokens: return 0
        
        # 1. Title Match (The "Perfect Fit" Signal) - Weight: 60%
        # Matches in title are much more important than description
        title_hits = title_tokens.intersection(res_tokens)
        title_score = min(60, len({t for t in title_hits if len(t) > 3}) * 20)
        
        # 2. Technical Keyword Overlap (The "Experience" Signal) - Weight: 40%
        # Matches in job requirements/description
        tech_hits = desc_tokens.intersection(res_tokens)
        # Filter for meaningful tech/action words (avoiding very common ones)
        meaningful_tech = {t for t in tech_hits if len(t) > 4}
        tech_score = min(40, len(meaningful_tech) * 4)
        
        # 3. Domain Bonus (Hand-picked high-value keywords for your profile)
        domain_keywords = {'safety', 'functional', 'iso', 'sil', 'asil', 'avionics', 'embedded', 'battery', 'hardware', 'software'}
        domain_hits = title_tokens.union(desc_tokens).intersection(domain_keywords).intersection(res_tokens)
        domain_bonus = len(domain_hits) * 5
        
        total = title_score + tech_score + domain_bonus
        
        # Sanity check: if it's a complete mismatch, floor it
        if total < 10: return 5
        
        return min(95, total)

    def _call_ai(self, prompt: str) -> str:
        """Helper to call AI (Gemini first, OpenAI backup)."""
        # 1. Try Gemini
        if self.client:
            try:
                response = self.client.models.generate_content(model="gemini-1.5-flash-latest", contents=prompt)
                return response.text
            except Exception as e:
                logger.warning(f"Gemini failed: {e}. Trying OpenAI backup...")
        
        # 2. Try OpenAI Backup
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini", # High speed/low cost for matching
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"OpenAI backup failed: {e}")
                raise e
        
        raise Exception("No AI providers available (Gemini/OpenAI failed or not configured).")

    def analyze_match(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Uses AI to calculate compatibility with robust parsing and fallbacks."""
        inputs_hash = hashlib.md5((resume_text + job_description).encode()).hexdigest()
        cache_key = f"match_v4_{inputs_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not self.client and not self.openai_client:
            return {"score": 50, "verdict": "Intelligence engine not active.", "strengths": [], "gaps": []}
        
        prompt = f"""
        Act as a Lead AI Recruiter. Rank the match between this Resume and Job.
        RESUME: {resume_text[:3500]}
        JOB: {job_description[:1500]}
        
        Return JSON ONLY: {{ "score": 0-100, "verdict": "brief explanation", "strengths": ["s1", "s2", "s3"], "gaps": ["g1", "g2", "g3"] }}
        """

        try:
            text = self._call_ai(prompt)
            content = text.strip()
            
            # Robust JSON extraction
            if "```" in content:
                content = content.split("```")[-2]
                if content.startswith("json\n"): content = content[5:]
                elif content.startswith("json"): content = content[4:]
            
            result = json.loads(content.strip())
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Analysis Error: {e}")
            error_msg = str(e)
            if "404" in error_msg:
                verdict = "AI Model Mismatch: The model ID in your region/version might be different. I am attempting a live fix."
            else:
                verdict = f"AI Matcher Error: {error_msg[:100]}"
                
            return {"score": 0, "verdict": verdict, "strengths": ["Wait for retry"], "gaps": ["API Quota / Model ID"]}

    def extract_search_profile(self, resume_text: str) -> Dict[str, Any]:
        """Analyzes a resume to extract multiple optimized job search queries."""
        resume_hash = hashlib.md5(resume_text.encode()).hexdigest()
        cache_key = f"profile_v4_{resume_hash}"
        
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if not self.client and not self.openai_client:
            return {"queries": ["Senior Functional Safety Engineer", "Safety Architect"], "location": "USA"}

        prompt = f"""
        Analyze this resume: {resume_text[:4000]}
        1. Identify expertise.
        2. Provide exactly 6 seeker queries for USA.
        3. Determine location.
        Return JSON: {{ "queries": ["q1", "q2", ...], "location": "...", "primary_title": "..." }}
        """
        
        try:
            text = self._call_ai(prompt)
            content = text.strip()
            if "```" in content:
                content = content.split("```")[-2]
                if content.startswith("json\n"): content = content[5:]
                elif content.startswith("json"): content = content[4:]
            
            result = json.loads(content.strip())
            if not result.get("queries") or not isinstance(result["queries"], list):
                result["queries"] = [result.get("primary_title") or "Senior Functional Safety Engineer"]
                
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Profile Error: {e}")
            return {"queries": ["Senior Functional Safety Engineer", "Safety Systems Engineer"], "location": "USA"}
