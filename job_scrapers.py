"""
Job board scrapers for LinkedIn, Indeed, Glassdoor, and ZipRecruiter

NOTE: Web scraping job boards is complex due to:
- Anti-bot measures (CAPTCHAs, rate limiting)
- Frequent website structure changes
- Terms of Service restrictions

This module provides a framework. Users should:
1. Review each platform's Terms of Service
2. Consider using official APIs where available
3. Implement rate limiting and respectful scraping
4. Be prepared for CAPTCHA challenges
"""

import logging
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import config
import database

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class JobScraper:
    """Base class for job board scrapers"""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
    
    def init_driver(self):
        """Initialize Selenium WebDriver"""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=options)
    
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
    
    def search_jobs(self, job_title: str, location: str) -> List[Dict]:
        """Search for jobs - to be implemented by subclasses"""
        raise NotImplementedError


class LinkedInScraper(JobScraper):
    """LinkedIn job scraper"""
    
    def search_jobs(self, job_title: str, location: str, limit: int = 25) -> List[Dict]:
        """
        Search LinkedIn for jobs
        
        NOTE: LinkedIn has strong anti-bot measures. This is a basic implementation.
        For production use, consider LinkedIn's official API or manual application.
        """
        logger.info(f"Searching LinkedIn: {job_title} in {location}")
        
        jobs = []
        
        try:
            self.init_driver()
            
            # Build search URL
            search_query = job_title.replace(' ', '%20')
            location_query = location.replace(' ', '%20')
            url = f"https://www.linkedin.com/jobs/search/?keywords={search_query}&location={location_query}"
            
            self.driver.get(url)
            time.sleep(3)  # Wait for page load
            
            # Note: LinkedIn requires login for detailed job info
            # This will only get publicly visible job listings
            
            job_cards = self.driver.find_elements(By.CLASS_NAME, "base-card")
            
            for card in job_cards[:limit]:
                try:
                    title_elem = card.find_element(By.CLASS_NAME, "base-search-card__title")
                    company_elem = card.find_element(By.CLASS_NAME, "base-search-card__subtitle")
                    link_elem = card.find_element(By.TAG_NAME, "a")
                    
                    job = {
                        "title": title_elem.text.strip(),
                        "company": company_elem.text.strip(),
                        "url": link_elem.get_attribute("href"),
                        "platform": "LinkedIn",
                        "location": location,
                        "description": "",  # Would need to visit individual page
                    }
                    
                    jobs.append(job)
                    logger.info(f"Found: {job['title']} at {job['company']}")
                    
                except Exception as e:
                    logger.error(f"Error parsing job card: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"LinkedIn search error: {e}")
        finally:
            self.close_driver()
        
        return jobs


class IndeedScraper(JobScraper):
    """Indeed job scraper with enhanced reliability"""
    
    def search_jobs(self, job_title: str, location: str, limit: int = 25) -> List[Dict]:
        """Search Indeed for jobs with retry logic"""
        logger.info(f"Searching Indeed: {job_title} in {location}")
        
        jobs = []
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Indeed is more scraping-friendly than LinkedIn
                search_query = job_title.replace(' ', '+')
                location_query = location.replace(' ', '+')
                url = f"https://www.indeed.com/jobs?q={search_query}&l={location_query}"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try multiple selectors (Indeed changes their HTML frequently)
                    job_cards = (
                        soup.find_all('div', class_='job_seen_beacon') or
                        soup.find_all('div', class_='jobsearch-SerpJobCard') or
                        soup.find_all('div', attrs={'data-jk': True})
                    )
                    
                    if not job_cards:
                        logger.warning("No job cards found with known selectors")
                        if attempt < max_retries - 1:
                            time.sleep(3)
                            continue
                    
                    for card in job_cards[:limit]:
                        try:
                            # Try multiple ways to extract title
                            title_elem = (
                                card.find('h2', class_='jobTitle') or
                                card.find('a', class_='jcs-JobTitle') or
                                card.find('h2', attrs={'class': lambda x: x and 'jobTitle' in x})
                            )
                            
                            # Try multiple ways to extract company
                            company_elem = (
                                card.find('span', class_='companyName') or
                                card.find('span', attrs={'data-testid': 'company-name'}) or
                                card.find('span', attrs={'class': lambda x: x and 'company' in x.lower()})
                            )
                            
                            if title_elem and company_elem:
                                # Extract job URL
                                link = title_elem.find('a') or card.find('a', attrs={'data-jk': True})
                                job_id = link.get('data-jk', '') if link else card.get('data-jk', '')
                                job_url = f"https://www.indeed.com/viewjob?jk={job_id}" if job_id else ""
                                
                                # Extract location if available
                                location_elem = card.find('div', class_='companyLocation')
                                job_location = location_elem.get_text(strip=True) if location_elem else location
                                
                                # Extract snippet/description if available
                                snippet_elem = card.find('div', class_='job-snippet')
                                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                                
                                job = {
                                    "title": title_elem.get_text(strip=True),
                                    "company": company_elem.get_text(strip=True),
                                    "url": job_url,
                                    "platform": "Indeed",
                                    "location": job_location,
                                    "description": snippet,
                                }
                                
                                jobs.append(job)
                                logger.info(f"Found: {job['title']} at {job['company']}")
                        
                        except Exception as e:
                            logger.debug(f"Error parsing Indeed job card: {e}")
                            continue
                    
                    # Success - break retry loop
                    break
                    
                elif response.status_code == 429:
                    logger.warning(f"Indeed rate limit hit (attempt {attempt + 1}/{max_retries})")
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.warning(f"Indeed returned status {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        
            except requests.exceptions.Timeout:
                logger.warning(f"Indeed request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(3)
            except Exception as e:
                logger.error(f"Indeed search error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.info(f"Indeed search complete: {len(jobs)} jobs found")
        time.sleep(2)  # Be respectful with scraping
        
        return jobs


class GlassdoorScraper(JobScraper):
    """Glassdoor job scraper"""
    
    def search_jobs(self, job_title: str, location: str, limit: int = 25) -> List[Dict]:
        """Search Glassdoor for jobs"""
        logger.info(f"Searching Glassdoor: {job_title} in {location}")
        
        # Glassdoor has strong anti-scraping measures
        # Recommend using official API or manual browsing
        
        logger.warning("Glassdoor scraping is challenging due to anti-bot measures")
        logger.warning("Consider using Glassdoor API or manual application")
        
        return []


class ZipRecruiterScraper(JobScraper):
    """ZipRecruiter job scraper"""
    
    def search_jobs(self, job_title: str, location: str, limit: int = 25) -> List[Dict]:
        """Search ZipRecruiter for jobs"""
        logger.info(f"Searching ZipRecruiter: {job_title} in {location}")
        
        # Similar challenges as other platforms
        logger.warning("ZipRecruiter scraping requires careful implementation")
        
        return []


class JobAggregator:
    """Aggregates jobs from multiple platforms including API and web scraping"""
    
    def __init__(self, use_api: bool = True):
        self.use_api = use_api
        self.scrapers = {
            "linkedin": LinkedInScraper() if config.ENABLED_PLATFORMS.get("linkedin") else None,
            "indeed": IndeedScraper() if config.ENABLED_PLATFORMS.get("indeed") else None,
            "glassdoor": GlassdoorScraper() if config.ENABLED_PLATFORMS.get("glassdoor") else None,
            "ziprecruiter": ZipRecruiterScraper() if config.ENABLED_PLATFORMS.get("ziprecruiter") else None,
        }
        
        # Try to import API search
        self.api_searcher = None
        if use_api:
            try:
                from job_api_search import JobAPISearch
                self.api_searcher = JobAPISearch()
                logger.info("API-based job search enabled")
            except ImportError:
                logger.warning("API search module not available")
            except Exception as e:
                logger.warning(f"Could not initialize API search: {e}")
    
    def search_all_platforms(self, job_title: str, location: str, limit_per_platform: int = 10) -> List[Dict]:
        """Search all enabled platforms for jobs"""
        all_jobs = []
        
        # Try API search first (more reliable)
        db = database.get_db()
        if self.api_searcher:
            try:
                logger.info("Expert Hunting via API...")
                api_jobs = self.api_searcher.search_jobs(
                    job_title, 
                    location, 
                    num_pages=3 # Scout deeper
                )
                all_jobs.extend(api_jobs)
            except Exception as e:
                logger.warning(f"API search failed: {e}")
        
        # Fall back to web scraping if needed
        for platform, scraper in self.scrapers.items():
            if scraper:
                logger.info(f"Scouting {platform}...")
                try:
                    jobs = scraper.search_jobs(job_title, location, limit=limit_per_platform)
                    for job in jobs:
                        if not db.job_seen(job['url']):
                            all_jobs.append(job)
                            db.add_discovered_job(job['url'])
                except Exception as e:
                    logger.error(f"Error scouting {platform}: {e}")
        
        logger.info(f"Total jobs found: {len(all_jobs)}")
        return all_jobs
    
    def get_job_description(self, job_url: str) -> str:
        """
        Fetch detailed job description from URL
        
        NOTE: This requires visiting the job page, which may trigger anti-bot measures
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(job_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract text from page (very basic)
            # Each platform has different structure
            text = soup.get_text(separator=' ', strip=True)
            
            # Limit to reasonable length
            return text[:5000]
            
        except Exception as e:
            logger.error(f"Error fetching job description: {e}")
            return "Description not available"


def search_jobs(job_titles: List[str], locations: List[str]) -> List[Dict]:
    """
    Utility function to search for jobs across all platforms
    
    Args:
        job_titles: List of job titles to search
        locations: List of locations to search
    
    Returns:
        List of job dictionaries
    """
    aggregator = JobAggregator()
    all_jobs = []
    
    for title in job_titles:
        for location in locations:
            jobs = aggregator.search_all_platforms(title, location)
            all_jobs.extend(jobs)
            time.sleep(5)  # Rate limiting between searches
    
    # Remove duplicates based on URL
    unique_jobs = {job['url']: job for job in all_jobs if job.get('url')}
    return list(unique_jobs.values())
