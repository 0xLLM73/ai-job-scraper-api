#!/usr/bin/env python3
"""
Supabase Integration Module
Handles storing scraped job data into Supabase database
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    print("Installing supabase-py...")
    os.system("pip3 install supabase")
    from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SupabaseJobScraper:
    """Enhanced Supabase integration for job scraper with existing platform integration"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.logger = logging.getLogger(__name__)
    
    # Session Management
    def create_scrape_session(self, urls: List[str], user_id: Optional[str] = None) -> str:
        """Create a new scraping session"""
        try:
            session_data = {
                'urls': urls,
                'total_urls': len(urls),
                'status': 'pending',
                'initiated_by': user_id,
                'started_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.client.table('scrape_sessions').insert(session_data).execute()
            session_id = result.data[0]['id']
            
            self.logger.info(f"Created scrape session {session_id} with {len(urls)} URLs")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Failed to create scrape session: {e}")
            raise
    
    def update_session_status(self, session_id: str, status: str, **kwargs) -> bool:
        """Update session status and metadata"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            update_data.update(kwargs)
            
            if status == 'completed':
                update_data['completed_at'] = datetime.now(timezone.utc).isoformat()
            
            self.client.table('scrape_sessions').update(update_data).eq('id', session_id).execute()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    def update_session_progress(self, session_id: str, completed_urls: int, current_url: str = None) -> bool:
        """Update session progress"""
        try:
            # Get total URLs for this session
            session = self.client.table('scrape_sessions').select('total_urls').eq('id', session_id).execute()
            if not session.data:
                return False
            
            total_urls = session.data[0]['total_urls']
            progress = (completed_urls / total_urls) * 100 if total_urls > 0 else 0
            
            update_data = {
                'completed_urls': completed_urls,
                'progress_percentage': round(progress, 2)
            }
            
            if current_url:
                update_data['current_url'] = current_url
            
            self.client.table('scrape_sessions').update(update_data).eq('id', session_id).execute()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update session progress {session_id}: {e}")
            return False
    
    # Job Storage
    def save_job_posting(self, job_data: Dict[str, Any], session_id: str = None) -> Optional[str]:
        """Save a scraped job posting to the database"""
        try:
            # Prepare job posting data
            posting_data = {
                'url': job_data.get('url'),
                'title': job_data.get('title', ''),
                'company': job_data.get('company', ''),
                'location': job_data.get('location'),
                'job_type': job_data.get('job_type'),
                'salary_range': job_data.get('salary_range'),
                'experience_level': job_data.get('experience_level'),
                'description': job_data.get('description', ''),
                'requirements': job_data.get('requirements', []),
                'benefits': job_data.get('benefits', []),
                'skills': job_data.get('skills', []),
                'application_url': job_data.get('application_url'),
                'application_email': job_data.get('application_email'),
                'application_form_structure': job_data.get('application_form_structure', {}),
                'source_platform': job_data.get('source_platform'),
                'raw_data': job_data,
                'scraped_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Handle potential duplicates
            existing = self.client.table('job_postings').select('id').eq('url', job_data.get('url')).execute()
            
            if existing.data:
                # Update existing job posting
                job_id = existing.data[0]['id']
                posting_data['last_updated'] = datetime.now(timezone.utc).isoformat()
                self.client.table('job_postings').update(posting_data).eq('id', job_id).execute()
                self.logger.info(f"Updated existing job posting: {job_id}")
            else:
                # Insert new job posting
                result = self.client.table('job_postings').insert(posting_data).execute()
                job_id = result.data[0]['id']
                self.logger.info(f"Saved new job posting: {job_id}")
            
            return job_id
            
        except Exception as e:
            self.logger.error(f"Failed to save job posting: {e}")
            if session_id:
                self.log_scrape_error(session_id, job_data.get('url', 'unknown'), f"Database save error: {e}")
            return None
    
    def get_job_postings(self, limit: int = 50, offset: int = 0, filters: Dict = None) -> List[Dict]:
        """Get job postings with optional filters"""
        try:
            query = self.client.table('job_postings').select('*')
            
            if filters:
                if filters.get('company'):
                    query = query.ilike('company', f"%{filters['company']}%")
                if filters.get('location'):
                    query = query.ilike('location', f"%{filters['location']}%")
                if filters.get('is_active') is not None:
                    query = query.eq('is_active', filters['is_active'])
            
            query = query.order('scraped_at', desc=True).range(offset, offset + limit - 1)
            result = query.execute()
            
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to get job postings: {e}")
            return []
    
    # Logging
    def log_scrape_error(self, session_id: str, url: str, error_message: str, error_details: Dict = None):
        """Log a scraping error"""
        try:
            log_data = {
                'session_id': session_id,
                'url': url,
                'log_level': 'error',
                'message': error_message,
                'error_details': error_details or {}
            }
            
            self.client.table('scrape_logs').insert(log_data).execute()
            
        except Exception as e:
            self.logger.error(f"Failed to log error: {e}")
    
    def log_scrape_info(self, session_id: str, url: str, message: str):
        """Log scraping information"""
        try:
            log_data = {
                'session_id': session_id,
                'url': url,
                'log_level': 'info',
                'message': message
            }
            
            self.client.table('scrape_logs').insert(log_data).execute()
            
        except Exception as e:
            self.logger.error(f"Failed to log info: {e}")
    
    # Session Queries
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session details"""
        try:
            result = self.client.table('scrape_sessions').select('*').eq('id', session_id).execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            self.logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get sessions for a specific user"""
        try:
            result = self.client.table('scrape_sessions').select('*').eq('initiated_by', user_id).order('created_at', desc=True).limit(limit).execute()
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to get user sessions: {e}")
            return []
    
    def get_session_logs(self, session_id: str) -> List[Dict]:
        """Get logs for a session"""
        try:
            result = self.client.table('scrape_logs').select('*').eq('session_id', session_id).order('created_at', desc=True).execute()
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to get session logs: {e}")
            return []
    
    # User Integration (works with existing users table)
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user details from existing users table"""
        try:
            result = self.client.table('users').select('*').eq('id', user_id).execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            self.logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    # Migration helper - merge scraped jobs to main jobs table
    def merge_to_main_jobs(self, job_posting_id: str, user_id: str) -> Optional[str]:
        """Merge a scraped job posting to the main jobs table"""
        try:
            # Get the job posting
            posting = self.client.table('job_postings').select('*').eq('id', job_posting_id).execute()
            if not posting.data:
                return None
            
            posting_data = posting.data[0]
            
            # Create entry in main jobs table
            job_data = {
                'title': posting_data['title'],
                'company': posting_data['company'],
                'description': posting_data['description'],
                'location': posting_data['location'],
                'type': posting_data.get('job_type', 'full-time'),
                'salary_range': posting_data['salary_range'],
                'requirements': posting_data.get('requirements', []),
                'benefits': posting_data.get('benefits', []),
                'posted_by': user_id,
                'application_url': posting_data['application_url'],
                'application_email': posting_data['application_email']
            }
            
            result = self.client.table('jobs').insert(job_data).execute()
            job_id = result.data[0]['id']
            
            # Update job_posting to reference the main job
            self.client.table('job_postings').update({'merged_to_job_id': job_id}).eq('id', job_posting_id).execute()
            
            self.logger.info(f"Merged job posting {job_posting_id} to main jobs table as {job_id}")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Failed to merge job posting: {e}")
            return None

# Global instance
supabase_scraper = SupabaseJobScraper()

class SupabaseJobStorage:
    """Handles storing job data in Supabase database"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client"""
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")
    
    def test_connection(self) -> bool:
        """Test the Supabase connection"""
        try:
            # Try to query a simple table or perform a basic operation
            result = self.client.table('job_postings').select('id').limit(1).execute()
            logger.info("Supabase connection test successful")
            return True
        except Exception as e:
            logger.error(f"Supabase connection test failed: {e}")
            return False
    
    def create_tables(self) -> bool:
        """Create the database tables if they don't exist"""
        try:
            # Note: In a real implementation, you would run these SQL commands
            # through Supabase SQL editor or migration scripts
            logger.info("Tables should be created through Supabase SQL editor")
            logger.info("Please run the SQL schema from supabase_schema_design.md")
            return True
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return False
    
    def insert_job_posting(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Insert a job posting into the database"""
        try:
            # Prepare job posting data
            job_posting_data = {
                'url': job_data['url'],
                'job_title': job_data['job_title'],
                'company_name': job_data['company_name'],
                'company_description': job_data.get('company_description'),
                'location': job_data.get('location'),
                'employment_type': job_data.get('employment_type'),
                'department': job_data.get('department'),
                'salary_min': job_data.get('salary_min'),
                'salary_max': job_data.get('salary_max'),
                'salary_currency': job_data.get('salary_currency', 'USD'),
                'salary_text': job_data.get('salary_text'),
                'job_description': job_data.get('job_description'),
                'responsibilities': job_data.get('responsibilities', []),
                'qualifications': job_data.get('qualifications', []),
                'benefits': job_data.get('benefits', []),
                'ats_platform': job_data.get('ats_platform'),
                'application_url': job_data.get('application_url'),
                'company_logo_url': job_data.get('company_logo_url'),
                'posted_date': job_data.get('posted_date'),
                'metadata': job_data.get('metadata', {}),
                'scraped_at': datetime.now().isoformat(),
                'is_active': True
            }
            
            # Insert job posting
            result = self.client.table('job_postings').insert(job_posting_data).execute()
            
            if result.data:
                job_id = result.data[0]['id']
                logger.info(f"Successfully inserted job posting: {job_id}")
                return job_id
            else:
                logger.error("Failed to insert job posting - no data returned")
                return None
                
        except Exception as e:
            logger.error(f"Error inserting job posting: {e}")
            return None
    
    def insert_application_form(self, job_id: str, form_data: Dict[str, Any]) -> Optional[str]:
        """Insert application form data"""
        try:
            form_data_prepared = {
                'job_posting_id': job_id,
                'form_url': form_data.get('form_url'),
                'form_method': form_data.get('form_method', 'POST'),
                'form_action': form_data.get('form_action'),
                'requires_auth': form_data.get('requires_auth', False),
                'has_captcha': form_data.get('has_captcha', False),
                'autofill_available': form_data.get('autofill_available', False)
            }
            
            result = self.client.table('application_forms').insert(form_data_prepared).execute()
            
            if result.data:
                form_id = result.data[0]['id']
                logger.info(f"Successfully inserted application form: {form_id}")
                return form_id
            else:
                logger.error("Failed to insert application form")
                return None
                
        except Exception as e:
            logger.error(f"Error inserting application form: {e}")
            return None
    
    def insert_form_fields(self, form_id: str, fields_data: List[Dict[str, Any]]) -> bool:
        """Insert form fields data"""
        try:
            fields_prepared = []
            for field in fields_data:
                field_data = {
                    'application_form_id': form_id,
                    'field_name': field.get('field_name'),
                    'field_label': field.get('field_label'),
                    'field_type': field.get('field_type', 'text'),
                    'field_placeholder': field.get('field_placeholder'),
                    'is_required': field.get('is_required', False),
                    'field_order': field.get('field_order', 0),
                    'validation_rules': field.get('validation_rules', {}),
                    'options': field.get('options', []),
                    'default_value': field.get('default_value'),
                    'help_text': field.get('help_text'),
                    'section_name': field.get('section_name'),
                    'visibility': field.get('visibility', 'public'),
                    'conditional_logic': field.get('conditional_logic', {})
                }
                fields_prepared.append(field_data)
            
            if fields_prepared:
                result = self.client.table('form_fields').insert(fields_prepared).execute()
                
                if result.data:
                    logger.info(f"Successfully inserted {len(result.data)} form fields")
                    return True
                else:
                    logger.error("Failed to insert form fields")
                    return False
            else:
                logger.info("No form fields to insert")
                return True
                
        except Exception as e:
            logger.error(f"Error inserting form fields: {e}")
            return False
    
    def insert_competency_questions(self, form_id: str, questions_data: List[Dict[str, Any]]) -> bool:
        """Insert competency questions data"""
        try:
            questions_prepared = []
            for question in questions_data:
                question_data = {
                    'application_form_id': form_id,
                    'question_text': question.get('question_text'),
                    'question_type': question.get('question_type', 'behavioral'),
                    'is_required': question.get('is_required', False),
                    'word_limit': question.get('word_limit'),
                    'character_limit': question.get('character_limit'),
                    'question_order': question.get('question_order', 0),
                    'section_name': question.get('section_name'),
                    'help_text': question.get('help_text')
                }
                questions_prepared.append(question_data)
            
            if questions_prepared:
                result = self.client.table('competency_questions').insert(questions_prepared).execute()
                
                if result.data:
                    logger.info(f"Successfully inserted {len(result.data)} competency questions")
                    return True
                else:
                    logger.error("Failed to insert competency questions")
                    return False
            else:
                logger.info("No competency questions to insert")
                return True
                
        except Exception as e:
            logger.error(f"Error inserting competency questions: {e}")
            return False
    
    def store_complete_job(self, scraped_data: Dict[str, Any]) -> Optional[str]:
        """Store complete job data (posting, form, fields, questions)"""
        try:
            logger.info(f"Storing complete job data for: {scraped_data['job_posting']['job_title']}")
            
            # Insert job posting
            job_id = self.insert_job_posting(scraped_data['job_posting'])
            if not job_id:
                logger.error("Failed to insert job posting")
                return None
            
            # Insert application form
            form_id = self.insert_application_form(job_id, scraped_data['application_form'])
            if not form_id:
                logger.error("Failed to insert application form")
                return None
            
            # Insert form fields
            if not self.insert_form_fields(form_id, scraped_data['form_fields']):
                logger.error("Failed to insert form fields")
                return None
            
            # Insert competency questions
            if not self.insert_competency_questions(form_id, scraped_data['competency_questions']):
                logger.error("Failed to insert competency questions")
                return None
            
            logger.info(f"Successfully stored complete job data with ID: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Error storing complete job data: {e}")
            return None
    
    def store_multiple_jobs(self, scraped_jobs: List[Dict[str, Any]]) -> List[str]:
        """Store multiple jobs and return list of job IDs"""
        job_ids = []
        
        for i, job_data in enumerate(scraped_jobs):
            logger.info(f"Storing job {i+1}/{len(scraped_jobs)}")
            job_id = self.store_complete_job(job_data)
            if job_id:
                job_ids.append(job_id)
        
        logger.info(f"Successfully stored {len(job_ids)}/{len(scraped_jobs)} jobs")
        return job_ids
    
    def get_job_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Check if a job already exists by URL"""
        try:
            result = self.client.table('job_postings').select('*').eq('url', url).execute()
            
            if result.data:
                return result.data[0]
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error checking job by URL: {e}")
            return None
    
    def get_all_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all jobs with pagination"""
        try:
            result = self.client.table('job_postings').select('*').eq('is_active', True).range(offset, offset + limit - 1).execute()
            
            if result.data:
                return result.data
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting all jobs: {e}")
            return []
    
    def get_job_with_form(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get complete job data including form structure"""
        try:
            # Get job posting
            job_result = self.client.table('job_postings').select('*').eq('id', job_id).execute()
            
            if not job_result.data:
                return None
            
            job_data = job_result.data[0]
            
            # Get application form
            form_result = self.client.table('application_forms').select('*').eq('job_posting_id', job_id).execute()
            
            if form_result.data:
                form_data = form_result.data[0]
                form_id = form_data['id']
                
                # Get form fields
                fields_result = self.client.table('form_fields').select('*').eq('application_form_id', form_id).order('field_order').execute()
                
                # Get competency questions
                questions_result = self.client.table('competency_questions').select('*').eq('application_form_id', form_id).order('question_order').execute()
                
                return {
                    'job_posting': job_data,
                    'application_form': form_data,
                    'form_fields': fields_result.data if fields_result.data else [],
                    'competency_questions': questions_result.data if questions_result.data else []
                }
            else:
                return {
                    'job_posting': job_data,
                    'application_form': None,
                    'form_fields': [],
                    'competency_questions': []
                }
                
        except Exception as e:
            logger.error(f"Error getting job with form: {e}")
            return None
    
    def search_jobs(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search jobs by title, company, or location"""
        try:
            # Note: This is a simple text search. For production, you might want to use
            # full-text search or more sophisticated search capabilities
            result = self.client.table('job_postings').select('*').or_(
                f'job_title.ilike.%{query}%,company_name.ilike.%{query}%,location.ilike.%{query}%'
            ).eq('is_active', True).limit(limit).execute()
            
            if result.data:
                return result.data
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error searching jobs: {e}")
            return []
    
    def log_user_interaction(self, job_id: str, user_id: str, interaction_type: str, interaction_data: Dict[str, Any] = None) -> bool:
        """Log user interaction with a job posting"""
        try:
            interaction_data_prepared = {
                'job_posting_id': job_id,
                'user_id': user_id,
                'interaction_type': interaction_type,
                'interaction_data': interaction_data or {}
            }
            
            result = self.client.table('user_interactions').insert(interaction_data_prepared).execute()
            
            if result.data:
                logger.info(f"Logged user interaction: {interaction_type}")
                return True
            else:
                logger.error("Failed to log user interaction")
                return False
                
        except Exception as e:
            logger.error(f"Error logging user interaction: {e}")
            return False

def main():
    """Example usage of Supabase integration"""
    # Note: You need to provide your actual Supabase URL and key
    supabase_url = "YOUR_SUPABASE_URL"
    supabase_key = "YOUR_SUPABASE_ANON_KEY"
    
    # Initialize storage
    storage = SupabaseJobStorage(supabase_url, supabase_key)
    
    # Test connection
    if storage.test_connection():
        print("Supabase connection successful!")
        
        # Load scraped jobs data
        try:
            with open('/home/ubuntu/scraped_jobs.json', 'r') as f:
                scraped_jobs = json.load(f)
            
            # Store jobs in Supabase
            job_ids = storage.store_multiple_jobs(scraped_jobs)
            print(f"Stored {len(job_ids)} jobs in Supabase")
            
            # Test retrieval
            if job_ids:
                job_data = storage.get_job_with_form(job_ids[0])
                print(f"Retrieved job: {job_data['job_posting']['job_title']}")
                
        except FileNotFoundError:
            print("No scraped jobs file found. Run job_scraper.py first.")
    else:
        print("Failed to connect to Supabase. Please check your credentials.")

    # Form-specific operations
    def create_form_scrape_session(self, session_data) -> str:
        """Create a new form scraping session"""
        try:
            session_record = {
                'urls': session_data.urls,
                'total_urls': session_data.total_urls,
                'processed_urls': session_data.processed_urls,
                'successful_forms': session_data.successful_forms,
                'failed_forms': session_data.failed_forms,
                'status': session_data.status,
                'progress_percentage': session_data.progress_percentage,
                'summary': session_data.summary,
                'error_details': session_data.error_details,
                'user_id': session_data.user_id,
                'started_at': session_data.started_at.isoformat() if session_data.started_at else None
            }
            
            result = self.client.table('form_scrape_sessions').insert(session_record).execute()
            
            if result.data:
                session_id = result.data[0]['id']
                self.logger.info(f"Created form scrape session: {session_id}")
                return session_id
            else:
                raise Exception("No data returned from session creation")
                
        except Exception as e:
            self.logger.error(f"Failed to create form scrape session: {e}")
            raise
    
    def update_session_progress(self, session_id: str, status: str, progress_percentage: float, processed_urls: int):
        """Update session progress"""
        try:
            update_data = {
                'status': status,
                'progress_percentage': progress_percentage,
                'processed_urls': processed_urls
            }
            
            result = self.client.table('form_scrape_sessions').update(update_data).eq('id', session_id).execute()
            
            if not result.data:
                self.logger.warning(f"No session found with ID: {session_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to update session progress: {e}")
    
    def complete_form_scrape_session(self, session_data):
        """Complete a form scraping session"""
        try:
            update_data = {
                'status': session_data.status,
                'processed_urls': session_data.processed_urls,
                'successful_forms': session_data.successful_forms,
                'failed_forms': session_data.failed_forms,
                'progress_percentage': session_data.progress_percentage,
                'summary': session_data.summary,
                'completed_at': session_data.completed_at.isoformat() if session_data.completed_at else None
            }
            
            result = self.client.table('form_scrape_sessions').update(update_data).eq('id', session_data.id).execute()
            
            if result.data:
                self.logger.info(f"Completed form scrape session: {session_data.id}")
            else:
                self.logger.warning(f"No session found with ID: {session_data.id}")
                
        except Exception as e:
            self.logger.error(f"Failed to complete form scrape session: {e}")
    
    def fail_form_scrape_session(self, session_id: str, error_message: str):
        """Mark a form scraping session as failed"""
        try:
            update_data = {
                'status': 'failed',
                'error_details': {'error': error_message},
                'completed_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.client.table('form_scrape_sessions').update(update_data).eq('id', session_id).execute()
            
            if result.data:
                self.logger.info(f"Marked form scrape session as failed: {session_id}")
            else:
                self.logger.warning(f"No session found with ID: {session_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to mark session as failed: {e}")
    
    def get_form_scrape_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get form scraping session details"""
        try:
            result = self.client.table('form_scrape_sessions').select('*').eq('id', session_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                self.logger.warning(f"No session found with ID: {session_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get form scrape session: {e}")
            return None
    
    def store_form_data(self, form_data, ai_result=None) -> Dict[str, Any]:
        """Store Google Form data in Supabase"""
        try:
            # Prepare form record
            form_record = {
                'url': form_data.url,
                'title': form_data.title,
                'description': form_data.description,
                'form_id': form_data.form_id,
                'owner_email': form_data.owner_email,
                'response_count': form_data.response_count,
                'is_accepting_responses': form_data.is_accepting_responses,
                'requires_login': form_data.requires_login,
                'allow_response_editing': form_data.allow_response_editing,
                'collect_email': form_data.collect_email,
                'raw_data': form_data.raw_data,
                'scraped_at': form_data.scraped_at.isoformat() if form_data.scraped_at else None,
                'last_updated': form_data.last_updated.isoformat() if form_data.last_updated else None
            }
            
            # Insert form
            form_result = self.client.table('forms').insert(form_record).execute()
            
            if not form_result.data:
                raise Exception("Failed to insert form record")
            
            form_id = form_result.data[0]['id']
            self.logger.info(f"Stored form: {form_id} - {form_data.title}")
            
            # Store questions
            question_ids = []
            for question in form_data.questions:
                question_record = {
                    'form_id': form_id,
                    'question_index': question.question_index,
                    'question_text': question.question_text,
                    'question_type': question.question_type.value,
                    'description': question.description,
                    'is_required': question.is_required,
                    'has_other_option': question.has_other_option,
                    'validation_rules': [
                        {
                            'rule_type': rule.rule_type,
                            'value': rule.value,
                            'error_message': rule.error_message
                        } for rule in question.validation_rules
                    ],
                    'settings': question.settings
                }
                
                question_result = self.client.table('form_questions').insert(question_record).execute()
                
                if question_result.data:
                    question_id = question_result.data[0]['id']
                    question_ids.append(question_id)
                    
                    # Store question options
                    for option in question.options:
                        option_record = {
                            'question_id': question_id,
                            'option_index': option.option_index,
                            'option_text': option.option_text,
                            'is_other_option': option.is_other_option
                        }
                        
                        self.client.table('question_options').insert(option_record).execute()
            
            # Store sections
            section_ids = []
            for section in form_data.sections:
                section_record = {
                    'form_id': form_id,
                    'section_index': section.section_index,
                    'title': section.title,
                    'description': section.description
                }
                
                section_result = self.client.table('form_sections').insert(section_record).execute()
                
                if section_result.data:
                    section_ids.append(section_result.data[0]['id'])
            
            self.logger.info(f"Stored form data: {len(question_ids)} questions, {len(section_ids)} sections")
            
            return {
                'form_id': form_id,
                'question_ids': question_ids,
                'section_ids': section_ids,
                'questions_count': len(question_ids),
                'sections_count': len(section_ids)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to store form data: {e}")
            raise
    
    def store_processing_logs(self, logs: List[Dict[str, Any]]):
        """Store form processing logs"""
        try:
            if not logs:
                return
            
            # Prepare log records
            log_records = []
            for log in logs:
                log_record = {
                    'session_id': log.get('session_id'),
                    'url': log.get('url'),
                    'processing_stage': log.get('processing_stage'),
                    'status': log.get('status'),
                    'message': log.get('message'),
                    'details': log.get('details', {}),
                    'processing_time_ms': log.get('processing_time_ms'),
                    'form_id': log.get('form_id')
                }
                log_records.append(log_record)
            
            # Insert logs
            result = self.client.table('form_processing_logs').insert(log_records).execute()
            
            if result.data:
                self.logger.info(f"Stored {len(result.data)} processing logs")
            
        except Exception as e:
            self.logger.error(f"Failed to store processing logs: {e}")
    
    def get_form_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get form data by URL"""
        try:
            result = self.client.table('forms').select('*').eq('url', url).execute()
            
            if result.data:
                return result.data[0]
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get form by URL: {e}")
            return None
    
    def get_form_with_questions(self, form_id: str) -> Optional[Dict[str, Any]]:
        """Get complete form data with questions and options"""
        try:
            # Get form
            form_result = self.client.table('forms').select('*').eq('id', form_id).execute()
            
            if not form_result.data:
                return None
            
            form_data = form_result.data[0]
            
            # Get questions
            questions_result = self.client.table('form_questions').select('*').eq('form_id', form_id).order('question_index').execute()
            
            questions = []
            for question in questions_result.data:
                # Get options for this question
                options_result = self.client.table('question_options').select('*').eq('question_id', question['id']).order('option_index').execute()
                
                question['options'] = options_result.data
                questions.append(question)
            
            form_data['questions'] = questions
            
            # Get sections
            sections_result = self.client.table('form_sections').select('*').eq('form_id', form_id).order('section_index').execute()
            form_data['sections'] = sections_result.data
            
            return form_data
            
        except Exception as e:
            self.logger.error(f"Failed to get form with questions: {e}")
            return None
    
    def get_recent_forms(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently scraped forms"""
        try:
            result = self.client.table('forms').select('*').order('scraped_at', desc=True).limit(limit).execute()
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to get recent forms: {e}")
            return []
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a scraping session"""
        try:
            # Get session info
            session = self.get_form_scrape_session(session_id)
            if not session:
                return {}
            
            # Get processing logs
            logs_result = self.client.table('form_processing_logs').select('*').eq('session_id', session_id).execute()
            
            logs = logs_result.data
            
            # Calculate statistics
            stats = {
                'session_info': session,
                'total_logs': len(logs),
                'logs_by_stage': {},
                'logs_by_status': {},
                'processing_times': [],
                'errors': []
            }
            
            for log in logs:
                stage = log.get('processing_stage', 'unknown')
                status = log.get('status', 'unknown')
                
                stats['logs_by_stage'][stage] = stats['logs_by_stage'].get(stage, 0) + 1
                stats['logs_by_status'][status] = stats['logs_by_status'].get(status, 0) + 1
                
                if log.get('processing_time_ms'):
                    stats['processing_times'].append(log['processing_time_ms'])
                
                if status == 'error':
                    stats['errors'].append({
                        'url': log.get('url'),
                        'stage': stage,
                        'message': log.get('message'),
                        'details': log.get('details', {})
                    })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get session statistics: {e}")
            return {}

if __name__ == "__main__":
    main()
