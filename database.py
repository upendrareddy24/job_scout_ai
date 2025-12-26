"""
Database module for tracking job applications
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
import logging
import config

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class ApplicationDatabase:
    """Manages the SQLite database for application tracking"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or config.DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Applications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                job_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                applied_date TEXT NOT NULL,
                status TEXT DEFAULT 'submitted',
                resume_path TEXT,
                job_description TEXT,
                match_score INTEGER,
                notes TEXT,
                UNIQUE(job_url)
            )
        ''')
        
        # Application status history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                updated_date TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        ''')
        
        # Discovered jobs table (Hunter's Memory)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discovered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT NOT NULL,
                discovered_date TEXT NOT NULL,
                UNIQUE(job_url)
            )
        ''')
        
        # Search terms table (Dynamic Pivoting)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                term_type TEXT NOT NULL, -- 'title' or 'location'
                is_active INTEGER DEFAULT 1,
                UNIQUE(term, term_type)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def add_application(self, company: str, position: str, job_url: str, 
                       platform: str, resume_path: str, job_description: str,
                       match_score: int, notes: Optional[str] = None) -> Optional[int]:
        """Add a new application record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            applied_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO applications 
                (company, position, job_url, platform, applied_date, resume_path, 
                 job_description, match_score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company, position, job_url, platform, applied_date, resume_path,
                  job_description, match_score, notes))
            
            app_id = cursor.lastrowid
            
            # Add to status history
            cursor.execute('''
                INSERT INTO status_history (application_id, status, updated_date)
                VALUES (?, 'submitted', ?)
            ''', (app_id, applied_date))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added application: {company} - {position} (ID: {app_id})")
            return app_id
            
        except sqlite3.IntegrityError:
            logger.warning(f"Application already exists: {job_url}")
            return None
        except Exception as e:
            logger.error(f"Error adding application: {str(e)}")
            return None
    
    def application_exists(self, job_url: str) -> bool:
        """Check if an application for this job already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM applications WHERE job_url = ?', (job_url,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None

    def job_seen(self, job_url: str) -> bool:
        """Check if the job has been discovered or applied to before"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check both tables
        cursor.execute('SELECT id FROM applications WHERE job_url = ?', (job_url,))
        if cursor.fetchone():
            conn.close()
            return True
            
        cursor.execute('SELECT id FROM discovered_jobs WHERE job_url = ?', (job_url,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None

    def add_discovered_job(self, job_url: str):
        """Record a discovered job to avoid seeing it again"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            discovered_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('INSERT OR IGNORE INTO discovered_jobs (job_url, discovered_date) VALUES (?, ?)', 
                          (job_url, discovered_date))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding discovered job: {e}")

    def add_search_term(self, term: str, term_type: str = "title"):
        """Add a new search term dynamically"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO search_terms (term, term_type) VALUES (?, ?)', 
                          (term, term_type))
            conn.commit()
            conn.close()
            logger.info(f"Added search {term_type}: {term}")
        except Exception as e:
            logger.error(f"Error adding search term: {e}")

    def delete_search_term(self, term: str):
        """Remove a search term"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM search_terms WHERE term = ?', (term,))
            conn.commit()
            conn.close()
            logger.info(f"Deleted search term: {term}")
        except Exception as e:
            logger.error(f"Error deleting search term: {e}")

    def get_search_terms(self, term_type: str = "title") -> List[str]:
        """Get all active search terms for a given type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT term FROM search_terms WHERE term_type = ? AND is_active = 1', (term_type,))
        terms = [row[0] for row in cursor.fetchall()]
        conn.close()
        return terms
    
    def get_applications_today(self) -> int:
        """Get count of applications submitted today"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM applications 
            WHERE DATE(applied_date) = DATE(?)
        ''', (today,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def get_all_applications(self, limit: int = 100) -> List[Dict]:
        """Get recent applications"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM applications 
            ORDER BY applied_date DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        applications = [dict(row) for row in rows]
        
        conn.close()
        return applications
    
    def update_status(self, application_id: int, status: str, notes: Optional[str] = None):
        """Update application status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updated_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            UPDATE applications SET status = ? WHERE id = ?
        ''', (status, application_id))
        
        cursor.execute('''
            INSERT INTO status_history (application_id, status, updated_date, notes)
            VALUES (?, ?, ?, ?)
        ''', (application_id, status, updated_date, notes))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated application {application_id} status to: {status}")
    
    def get_stats(self) -> Dict:
        """Get application statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total applications
        cursor.execute('SELECT COUNT(*) FROM applications')
        total = cursor.fetchone()[0]
        
        # Applications by status
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM applications 
            GROUP BY status
        ''')
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Applications by platform
        cursor.execute('''
            SELECT platform, COUNT(*) as count 
            FROM applications 
            GROUP BY platform
        ''')
        by_platform = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Applications this week
        cursor.execute('''
            SELECT COUNT(*) FROM applications 
            WHERE DATE(applied_date) >= DATE('now', '-7 days')
        ''')
        this_week = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "by_status": by_status,
            "by_platform": by_platform,
            "this_week": this_week
        }


# Utility function
def get_db():
    """Get database instance"""
    return ApplicationDatabase()
