"""
API-based job search using RapidAPI JSearch
More reliable than web scraping, with structured data from multiple platforms
"""

import os
import logging
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
import config

load_dotenv()
logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
JSEARCH_API_URL = "https://jsearch.p.rapidapi.com/search"


class JobAPISearch:
    """Search jobs using RapidAPI JSearch"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or RAPIDAPI_KEY
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
    
    def search_jobs(self, query: str, location: str = "United States", 
                   num_pages: int = 3, remote_only: bool = False) -> List[Dict]:
        """
        Search for jobs with Hunter's Memory (deduplication)
        """
        if not self.api_key:
            logger.warning("No RapidAPI key. Skipping.")
            return []
            
        db = database.get_db()
        all_jobs = []
        
        logger.info(f"Expert Hunting for '{query}' in {location} (Pages: {num_pages})")
        
        for page in range(1, num_pages + 1):
            try:
                params = {
                    "query": f"{query} {location}",
                    "page": str(page),
                    "num_pages": "1",
                }
                if remote_only: params["remote_jobs_only"] = "true"
                
                response = requests.get(JSEARCH_API_URL, headers=self.headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    jobs_data = data.get("data", [])
                    
                    found_count = 0
                    for job in jobs_data:
                        url = job.get("job_apply_link") or job.get("job_google_link", "")
                        
                        # --- HUNTER'S MEMORY: DEDUPLICATION ---
                        if db.job_seen(url):
                            continue
                            
                        standardized_job = {
                            "title": job.get("job_title", ""),
                            "company": job.get("employer_name", ""),
                            "location": job.get("job_city", location),
                            "url": url,
                            "description": job.get("job_description", ""),
                            "platform": "JSearch API",
                            "job_type": job.get("job_employment_type", ""),
                            "posted_date": job.get("job_posted_at_datetime_utc", ""),
                        }
                        
                        all_jobs.append(standardized_job)
                        db.add_discovered_job(url) # Mark as seen immediately
                        found_count += 1
                        
                    logger.info(f"Page {page}: {found_count} fresh jobs found.")
                    
                elif response.status_code == 429:
                    logger.error("API rate limit hit. Hunter is laying low.")
                    break
                else:
                    logger.warning(f"API Error {response.status_code}. Skipping page.")
                    
            except Exception as e:
                logger.error(f"Search error: {e}")
                break
                
        return all_jobs
    
    def _format_salary(self, job: Dict) -> str:
        """Format salary information"""
        min_salary = job.get("job_min_salary")
        max_salary = job.get("job_max_salary")
        
        if min_salary and max_salary:
            return f"${min_salary:,} - ${max_salary:,}"
        elif min_salary:
            return f"${min_salary:,}+"
        elif max_salary:
            return f"Up to ${max_salary:,}"
        else:
            return "Not specified"


def search_jobs_api(job_title: str, location: str = "United States", 
                    num_pages: int = 1, remote_only: bool = False) -> List[Dict]:
    """
    Utility function to search jobs via API
    
    Args:
        job_title: Job title or keywords
        location: Location string
        num_pages: Number of pages (10 jobs per page)
        remote_only: Filter for remote jobs only
    
    Returns:
        List of job dictionaries
    """
    searcher = JobAPISearch()
    return searcher.search_jobs(job_title, location, num_pages, remote_only)


def search_multiple_titles(job_titles: List[str], locations: List[str], 
                          jobs_per_search: int = 10) -> List[Dict]:
    """
    Search for multiple job titles across multiple locations
    
    Args:
        job_titles: List of job titles to search
        locations: List of locations
        jobs_per_search: Number of jobs to fetch per search
    
    Returns:
        Deduplicated list of jobs
    """
    searcher = JobAPISearch()
    all_jobs = []
    
    for title in job_titles:
        for location in locations:
            jobs = searcher.search_jobs(
                title, 
                location, 
                num_pages=max(1, jobs_per_search // 10)
            )
            all_jobs.extend(jobs)
    
    # Deduplicate by URL
    unique_jobs = {}
    for job in all_jobs:
        url = job.get('url', '')
        if url and url not in unique_jobs:
            unique_jobs[url] = job
    
    return list(unique_jobs.values())
