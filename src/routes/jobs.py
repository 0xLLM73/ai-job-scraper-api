from flask import Blueprint, request, jsonify
import json
import os
import logging
from typing import List, Dict, Any
import threading
import time

import sys
import os
# Add the src directory to the path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from job_scraper import JobScraper
from supabase_integration import supabase_scraper
from integrated_flexible_scraper import IntegratedFlexibleScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

jobs_bp = Blueprint('jobs', __name__)

# Global variables for configuration
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Log the loaded configuration
if FIRECRAWL_API_KEY:
    logger.info(f"Firecrawl API Key loaded, starting with: {FIRECRAWL_API_KEY[:4]}...")
else:
    logger.warning("Firecrawl API Key not found. Please set FIRECRAWL_API_KEY in your .env file.")

if SUPABASE_URL and SUPABASE_KEY:
    logger.info("Supabase credentials loaded.")
else:
    logger.warning("Supabase credentials not found. Database functionality will be limited.")

# Initialize services
scraper = JobScraper(FIRECRAWL_API_KEY)
flexible_scraper = IntegratedFlexibleScraper(FIRECRAWL_API_KEY, supabase_scraper)

# Global variable to track scraping sessions
scraping_sessions = {}

@jobs_bp.route('/scrape/flexible', methods=['POST'])
def scrape_jobs_flexible():
    """Endpoint to scrape job postings using AI-powered flexible scraper"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        # Add support for single URL from 'url' key
        if 'url' in data and data['url'] not in urls:
            urls.append(data['url'])
        
        if not urls:
            return jsonify({'error': 'No URLs provided'}), 400
        
        # Create session in Supabase
        try:
            session_id = supabase_scraper.create_scrape_session(urls, user_id=None)  # TODO: Add user authentication
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return jsonify({'error': 'Failed to create scraping session'}), 500
        
        # Start flexible scraping in background thread
        def scrape_background_flexible():
            try:
                # Update session status to running
                supabase_scraper.update_session_status(session_id, 'running')
                
                scraping_sessions[session_id] = {
                    'status': 'running',
                    'total_urls': len(urls),
                    'completed': 0,
                    'results': [],
                    'errors': []
                }
                
                # Use the integrated flexible scraper
                results = flexible_scraper.scrape_multiple_jobs_flexible(urls, session_id)
                
                # Process results
                successful_results = []
                for i, result in enumerate(results):
                    if result['success']:
                        successful_results.append(result)
                        scraping_sessions[session_id]['results'].append(result)
                    else:
                        error_msg = f"Error scraping {urls[i]}: {result.get('error', 'Unknown error')}"
                        scraping_sessions[session_id]['errors'].append(error_msg)
                    
                    scraping_sessions[session_id]['completed'] = i + 1
                
                # Update final session status
                supabase_scraper.update_session_status(
                    session_id, 
                    'completed',
                    scraped_jobs_count=len(successful_results),
                    summary={
                        'total_scraped': len(successful_results), 
                        'total_errors': len(scraping_sessions[session_id]['errors']),
                        'method': 'flexible_ai',
                        'avg_confidence': sum(r.get('confidence_score', 0) for r in successful_results) / max(len(successful_results), 1)
                    }
                )
                supabase_scraper.update_session_progress(session_id, len(urls))
                
                scraping_sessions[session_id]['status'] = 'completed'
                logger.info(f"Flexible scraping session {session_id} completed: {len(successful_results)}/{len(urls)} successful")
                
            except Exception as e:
                supabase_scraper.update_session_status(session_id, 'failed', errors=[str(e)])
                scraping_sessions[session_id]['status'] = 'failed'
                scraping_sessions[session_id]['errors'].append(str(e))
                logger.error(f"Flexible scraping session {session_id} failed: {e}")
        
        # Start background thread
        thread = threading.Thread(target=scrape_background_flexible)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'started',
            'method': 'flexible_ai',
            'message': f'Started AI-powered flexible scraping of {len(urls)} job postings'
        })
        
    except Exception as e:
        logger.error(f"Error in scrape_jobs_flexible endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/scrape', methods=['POST'])
def scrape_jobs():
    """Endpoint to scrape job postings"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        # Add support for single URL from 'url' key
        if 'url' in data and data['url'] not in urls:
            urls.append(data['url'])
        
        if not urls:
            return jsonify({'error': 'No URLs provided'}), 400
        
        # Create session in Supabase
        try:
            session_id = supabase_scraper.create_scrape_session(urls, user_id=None)  # TODO: Add user authentication
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return jsonify({'error': 'Failed to create scraping session'}), 500
        
        # Start scraping in background thread
        def scrape_background():
            try:
                # Update session status to running
                supabase_scraper.update_session_status(session_id, 'running')
                
                scraping_sessions[session_id] = {
                    'status': 'running',
                    'total_urls': len(urls),
                    'completed': 0,
                    'results': [],
                    'errors': []
                }
                
                results = []
                for i, url in enumerate(urls):
                    try:
                        logger.info(f"Scraping job {i+1}/{len(urls)}: {url}")
                        supabase_scraper.update_session_progress(session_id, i, url)
                        supabase_scraper.log_scrape_info(session_id, url, f"Starting scrape {i+1}/{len(urls)}")
                        
                        result = scraper.scrape_job(url)
                        
                        if result:
                            results.append(result)
                            
                            # Store in Supabase
                            job_id = supabase_scraper.save_job_posting(result, session_id)
                            if job_id:
                                result['stored_job_id'] = job_id
                                supabase_scraper.log_scrape_info(session_id, url, f"Successfully saved job posting: {job_id}")
                        
                        scraping_sessions[session_id]['completed'] = i + 1
                        scraping_sessions[session_id]['results'] = results
                        
                    except Exception as e:
                        error_msg = f"Error scraping {url}: {str(e)}"
                        logger.error(error_msg)
                        scraping_sessions[session_id]['errors'].append(error_msg)
                        supabase_scraper.log_scrape_error(session_id, url, error_msg, {'exception': str(e)})
                
                # Update final session status
                supabase_scraper.update_session_status(
                    session_id, 
                    'completed',
                    scraped_jobs_count=len(results),
                    summary={'total_scraped': len(results), 'total_errors': len(scraping_sessions[session_id]['errors'])}
                )
                supabase_scraper.update_session_progress(session_id, len(urls))
                
                scraping_sessions[session_id]['status'] = 'completed'
                logger.info(f"Scraping session {session_id} completed")
                
            except Exception as e:
                supabase_scraper.update_session_status(session_id, 'failed', errors=[str(e)])
                scraping_sessions[session_id]['status'] = 'failed'
                scraping_sessions[session_id]['errors'].append(str(e))
                logger.error(f"Scraping session {session_id} failed: {e}")
        
        # Start background thread
        thread = threading.Thread(target=scrape_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'started',
            'message': f'Started scraping {len(urls)} job postings'
        })
        
    except Exception as e:
        logger.error(f"Error in scrape_jobs endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/scrape/status/<session_id>', methods=['GET'])
def get_scraping_status(session_id):
    """Get the status of a scraping session"""
    try:
        # Get from Supabase first
        session_data = supabase_scraper.get_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get local session data for additional info
        local_session = scraping_sessions.get(session_id, {})
        
        return jsonify({
            'session_id': session_id,
            'status': session_data['status'],
            'total_urls': session_data['total_urls'],
            'completed_urls': session_data.get('completed_urls', 0),
            'progress_percentage': session_data.get('progress_percentage', 0),
            'current_url': session_data.get('current_url'),
            'scraped_jobs_count': session_data.get('scraped_jobs_count', 0),
            'started_at': session_data.get('started_at'),
            'completed_at': session_data.get('completed_at'),
            'estimated_completion': session_data.get('estimated_completion'),
            'success_count': len(local_session.get('results', [])),
            'error_count': len(local_session.get('errors', [])),
            'errors': local_session.get('errors', [])
        })
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/scrape/results/<session_id>', methods=['GET'])
def get_scraping_results(session_id):
    """Get the results of a scraping session"""
    try:
        if session_id not in scraping_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        session_data = scraping_sessions[session_id]
        
        return jsonify({
            'session_id': session_id,
            'status': session_data['status'],
            'results': session_data['results']
        })
        
    except Exception as e:
        logger.error(f"Error getting scraping results: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """Get all jobs from Supabase"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get filters from query parameters
        filters = {}
        if request.args.get('company'):
            filters['company'] = request.args.get('company')
        if request.args.get('location'):
            filters['location'] = request.args.get('location')
        if request.args.get('is_active') is not None:
            filters['is_active'] = request.args.get('is_active').lower() == 'true'
        
        jobs = supabase_scraper.get_job_postings(limit=limit, offset=offset, filters=filters)
        
        return jsonify({
            'jobs': jobs,
            'count': len(jobs),
            'limit': limit,
            'offset': offset,
            'filters': filters
        })
        
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/scrape/sessions', methods=['GET'])
def get_all_sessions():
    """Get all scraping sessions (for admin/debugging)"""
    try:
        # TODO: Add user authentication and filter by user
        limit = request.args.get('limit', 20, type=int)
        
        # For now, return all sessions - in production, filter by user
        sessions = []  # TODO: Implement get_all_sessions in supabase_scraper
        
        return jsonify({
            'sessions': sessions,
            'count': len(sessions),
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/scrape/sessions/<session_id>/logs', methods=['GET'])
def get_session_logs(session_id):
    """Get logs for a specific scraping session"""
    try:
        logs = supabase_scraper.get_session_logs(session_id)
        
        return jsonify({
            'session_id': session_id,
            'logs': logs,
            'count': len(logs)
        })
        
    except Exception as e:
        logger.error(f"Error getting session logs: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_details(job_id):
    """Get detailed job information including form structure"""
    if job_id == 'undefined':
        return jsonify({'error': 'Invalid job ID'}), 400
    try:
        storage_client = get_storage()
        if not storage_client:
            logger.warning("Supabase not configured. Cannot fetch job details.")
            return jsonify({'error': 'Job not found, Supabase not configured'}), 404
        
        job_data = storage_client.get_job_with_form(job_id)
        
        if not job_data:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job_data)
        
    except Exception as e:
        logger.error(f"Error getting job details: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/jobs/search', methods=['GET'])
def search_jobs():
    """Search jobs by query"""
    try:
        storage_client = get_storage()
        if not storage_client:
            return jsonify({'error': 'Supabase not configured'}), 500
        
        query = request.args.get('q', '')
        limit = request.args.get('limit', 50, type=int)
        
        if not query:
            return jsonify({'error': 'Query parameter required'}), 400
        
        jobs = storage_client.search_jobs(query, limit=limit)
        
        return jsonify({
            'jobs': jobs,
            'query': query,
            'count': len(jobs)
        })
        
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/jobs/<job_id>/interact', methods=['POST'])
def log_interaction(job_id):
    """Log user interaction with a job"""
    try:
        storage_client = get_storage()
        if not storage_client:
            return jsonify({'error': 'Supabase not configured'}), 500
        
        data = request.get_json()
        user_id = data.get('user_id', 'anonymous')
        interaction_type = data.get('interaction_type', 'view')
        interaction_data = data.get('interaction_data', {})
        
        success = storage_client.log_user_interaction(
            job_id, user_id, interaction_type, interaction_data
        )
        
        if success:
            return jsonify({'message': 'Interaction logged successfully'})
        else:
            return jsonify({'error': 'Failed to log interaction'}), 500
        
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/config', methods=['GET'])
def get_config():
    """Get configuration status"""
    supabase_connected = False
    try:
        # Test Supabase connection by creating a test session
        test_session = supabase_scraper.create_scrape_session(['test'], user_id=None)
        supabase_connected = bool(test_session)
    except Exception as e:
        logger.warning(f"Supabase connection test failed: {e}")
        supabase_connected = False
    
    return jsonify({
        'firecrawl_configured': bool(FIRECRAWL_API_KEY),
        'supabase_configured': bool(SUPABASE_URL and SUPABASE_KEY),
        'supabase_connected': supabase_connected
    })

@jobs_bp.route('/demo/scrape', methods=['POST'])
def demo_scrape():
    """Demo endpoint that scrapes without storing in Supabase"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({'error': 'No URLs provided'}), 400
        
        results = []
        for url in urls:
            try:
                result = scraper.scrape_job(url)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
        
        return jsonify({
            'results': results,
            'count': len(results),
            'message': f'Successfully scraped {len(results)}/{len(urls)} jobs'
        })
        
    except Exception as e:
        logger.error(f"Error in demo scrape: {e}")
        return jsonify({'error': str(e)}), 500

