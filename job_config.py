"""
Configuration settings for the job application bot
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== JOB SEARCH PREFERENCES =====

# Job titles to search for (will be matched against your resume experience)
JOB_TITLES = [
    "Software Engineer",
    "Software Developer",
    "Full Stack Developer",
    "Backend Engineer",
    "Frontend Engineer",
    "Data Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
]

# Locations (use "Remote" for remote jobs, or specific cities)
LOCATIONS = [
    "Remote",
    "United States",
    # Add specific cities if needed:
    # "New York, NY",
    # "San Francisco, CA",
    # "Austin, TX",
]

# Experience levels to search for
EXPERIENCE_LEVELS = [
    "Entry Level",
    "Mid Level", 
    "Senior Level",
    "Lead",
]

# Job platforms to use
ENABLED_PLATFORMS = {
    "linkedin": True,
    "indeed": True,
    "glassdoor": True,
    "ziprecruiter": True,
}

# ===== APPLICATION SETTINGS =====

# Maximum applications to submit per day
DAILY_APPLICATION_LIMIT = 10

# Minimum match score (0-100) to apply
# Higher = more selective
MIN_MATCH_SCORE = 60

# Skip jobs with required assessments
SKIP_ASSESSMENTS = True

# ===== EXPERT HUNTER SETTINGS =====
# Casting a wider net for fresh leads
JOBS_PER_SEARCH_PER_PLATFORM = 30
PAGES_TO_SEARCH = 3

# ===== RESUME SETTINGS =====

# Resume format preference (pdf or docx)
RESUME_FORMAT = "docx"

# Master resume filename (in resumes/master/)
MASTER_RESUME_FILENAME = "master_resume.docx"

# ===== AI SETTINGS =====

# Which AI service to use (openai, anthropic, or google)
# Will auto-detect based on which API key is available
AI_SERVICE = os.getenv("AI_SERVICE", "")

# Auto-detect AI service if not specified
if not AI_SERVICE:
    if os.getenv("OPENAI_API_KEY"):
        AI_SERVICE = "openai"
    elif os.getenv("ANTHROPIC_API_KEY"):
        AI_SERVICE = "anthropic"
    elif os.getenv("GOOGLE_AI_API_KEY"):
        AI_SERVICE = "google"
    else:
        AI_SERVICE = "openai"  # Default

# AI model settings
AI_MODELS = {
    "openai": "gpt-4",
    "anthropic": "claude-3-sonnet-20240229",
    "google": "gemini-pro",
}

# ===== API SETTINGS =====

# RapidAPI key for job search (optional but recommended)
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# ===== CREDENTIALS (from .env file) =====

# AI API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")

# Job Platform Credentials
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

INDEED_EMAIL = os.getenv("INDEED_EMAIL")
INDEED_PASSWORD = os.getenv("INDEED_PASSWORD")

GLASSDOOR_EMAIL = os.getenv("GLASSDOOR_EMAIL")
GLASSDOOR_PASSWORD = os.getenv("GLASSDOOR_PASSWORD")

ZIPRECRUITER_EMAIL = os.getenv("ZIPRECRUITER_EMAIL")
ZIPRECRUITER_PASSWORD = os.getenv("ZIPRECRUITER_PASSWORD")

# Personal Information
YOUR_NAME = os.getenv("YOUR_NAME", "")
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "")
YOUR_PHONE = os.getenv("YOUR_PHONE", "")
YOUR_LINKEDIN = os.getenv("YOUR_LINKEDIN", "")
YOUR_LOCATION = os.getenv("YOUR_LOCATION", "")

# Cover letter
COVER_LETTER_ENABLED = os.getenv("COVER_LETTER_ENABLED", "false").lower() == "true"

# ===== PATHS =====

import pathlib

BASE_DIR = pathlib.Path(__file__).parent
RESUME_DIR = BASE_DIR / "resumes"
MASTER_RESUME_DIR = RESUME_DIR / "master"
CUSTOMIZED_RESUME_DIR = RESUME_DIR / "customized"
JOB_DESCRIPTIONS_DIR = BASE_DIR / "job_descriptions"
DATABASE_PATH = BASE_DIR / "applications.db"

# ===== LOGGING =====

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
