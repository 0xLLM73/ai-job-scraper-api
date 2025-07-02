#!/usr/bin/env python3
"""
Forms API Routes
Flask routes for Google Forms processing functionality
"""

from flask import Blueprint, request, jsonify
import json
import os
import logging
import threading
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

import sys
import os
# Add the src directory to the path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from supabase_integration import supabase_scraper
from integrated_form_scraper import IntegratedFormScraper
from models.form import validate_google_forms_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

forms_bp = Blueprint('forms', __name__)

# Global variables for configuration
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Log the loaded configuration
if FIRECRAWL_API_KEY:
    logger.info(f"Firecrawl API Key loaded for forms processing")
else:
    logger.warning("Firecrawl API Key not found. Please set FIRECRAWL_API_KEY in your .env file.")

if OPENAI_API_KEY:
    logger.info("OpenAI API Key loaded for forms processing")
else:
    logger.warning("OpenAI API Key not found. AI processing will be disabled.")

if SUPABASE_URL and SUPABASE_KEY:
    logger.info("Supabase credentials loaded for forms processing")
else:
    logger.warning("Supabase credentials not found. Database functionality will be limited.")

# Initialize services
try:
    integrated_scraper = IntegratedFormScraper(FIRECRAWL_API_KEY, supabase_scraper, OPENAI_API_KEY)
    logger.info("Integrated form scraper initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize integrated form scraper: {e}")
    integrated_scraper = None

# Global variable to track scraping sessions
form_scraping_sessions = {}

@forms_bp.route('/forms/scrape', methods=['POST'])
def scrape_forms():
    """
    Start scraping Google Forms
    
    Request body:
    {
        "urls": ["https://docs.google.com/forms/d/..."],
        "user_id": "optional_user_id"
    }
    
    Response:
    {
        "session_id": "uuid",
        "message": "Form scraping started",
        "total_urls": 1,
        "estimated_time_minutes": 2
    }
    """
    try:
        if not integrated_scraper:
            return jsonify({
                'error': 'Form scraper not available. Please check API key configuration.',
                'details': 'FIRECRAWL_API_KEY is required for form scraping'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        urls = data.get('urls', [])
        user_id = data.get('user_id')
        
        if not urls:
            return jsonify({'error': 'URLs list is required and cannot be empty'}), 400
        
        if not isinstance(urls, list):
            return jsonify({'error': 'URLs must be provided as a list'}), 400
        
        # Validate URLs
        invalid_urls = []
        valid_urls = []
        
        for url in urls:
            if not isinstance(url, str):
                invalid_urls.append(f"Invalid URL type: {type(url)}")
            elif not validate_google_forms_url(url):
                invalid_urls.append(f"Not a valid Google Forms URL: {url}")
            else:
                valid_urls.append(url)
        
        if invalid_urls:
            return jsonify({
                'error': 'Invalid URLs provided',
                'invalid_urls': invalid_urls,
                'valid_urls_count': len(valid_urls)
            }), 400
        
        if not valid_urls:
            return jsonify({'error': 'No valid Google Forms URLs provided'}), 400
        
        # Limit the number of URLs to prevent abuse
        max_urls = 50  # Configurable limit
        if len(valid_urls) > max_urls:
            return jsonify({
                'error': f'Too many URLs. Maximum allowed: {max_urls}',
                'provided_count': len(valid_urls)
            }), 400
        
        logger.info(f"Starting form scraping for {len(valid_urls)} URLs")
        
        # Start processing
        session_id = integrated_scraper.process_multiple_forms(valid_urls, user_id)
        
        # Store session info locally for quick access
        form_scraping_sessions[session_id] = {
            'urls': valid_urls,
            'total_urls': len(valid_urls),
            'user_id': user_id,
            'started_at': datetime.now().isoformat(),
            'status': 'processing'
        }
        
        # Estimate processing time (rough estimate: 30-60 seconds per form)
        estimated_time_minutes = max(1, len(valid_urls) * 0.75)  # 45 seconds per form average
        
        return jsonify({
            'session_id': session_id,
            'message': 'Form scraping started successfully',
            'total_urls': len(valid_urls),
            'estimated_time_minutes': round(estimated_time_minutes, 1),
            'status_endpoint': f'/api/forms/status/{session_id}'
        }), 202  # 202 Accepted for async processing
        
    except Exception as e:
        logger.error(f"Error starting form scraping: {str(e)}")
        return jsonify({
            'error': 'Failed to start form scraping',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/status/<session_id>', methods=['GET'])
def get_scraping_status(session_id):
    """
    Get the status of a form scraping session
    
    Response:
    {
        "id": "session_id",
        "status": "processing|completed|failed",
        "progress_percentage": 75.5,
        "processed_urls": 3,
        "total_urls": 4,
        "successful_forms": 2,
        "failed_forms": 1,
        "summary": "2 successful, 1 failed",
        "started_at": "2024-01-01T12:00:00",
        "completed_at": "2024-01-01T12:05:00",
        "estimated_remaining_minutes": 1.2
    }
    """
    try:
        if not integrated_scraper:
            return jsonify({'error': 'Form scraper not available'}), 500
        
        # Get status from database
        status_data = integrated_scraper.get_session_status(session_id)
        
        if not status_data:
            # Check local sessions as fallback
            local_session = form_scraping_sessions.get(session_id)
            if local_session:
                return jsonify({
                    'id': session_id,
                    'status': local_session.get('status', 'unknown'),
                    'total_urls': local_session.get('total_urls', 0),
                    'message': 'Session found locally but not in database'
                })
            
            return jsonify({'error': 'Session not found'}), 404
        
        # Calculate estimated remaining time
        estimated_remaining_minutes = None
        if status_data.get('status') == 'processing':
            remaining_urls = status_data.get('total_urls', 0) - status_data.get('processed_urls', 0)
            if remaining_urls > 0:
                estimated_remaining_minutes = round(remaining_urls * 0.75, 1)  # 45 seconds per form
        
        # Prepare response
        response_data = {
            'id': status_data.get('id'),
            'status': status_data.get('status'),
            'progress_percentage': status_data.get('progress_percentage', 0),
            'processed_urls': status_data.get('processed_urls', 0),
            'total_urls': status_data.get('total_urls', 0),
            'successful_forms': status_data.get('successful_forms', 0),
            'failed_forms': status_data.get('failed_forms', 0),
            'summary': status_data.get('summary'),
            'started_at': status_data.get('started_at'),
            'completed_at': status_data.get('completed_at'),
            'estimated_remaining_minutes': estimated_remaining_minutes
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {str(e)}")
        return jsonify({
            'error': 'Failed to get scraping status',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/status/<session_id>/detailed', methods=['GET'])
def get_detailed_session_status(session_id):
    """
    Get detailed status including processing logs and statistics
    """
    try:
        if not integrated_scraper:
            return jsonify({'error': 'Form scraper not available'}), 500
        
        # Get basic status
        status_data = integrated_scraper.get_session_status(session_id)
        if not status_data:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get detailed statistics
        detailed_stats = {}
        if hasattr(supabase_scraper, 'get_session_statistics'):
            try:
                detailed_stats = supabase_scraper.get_session_statistics(session_id)
            except Exception as e:
                logger.error(f"Failed to get detailed statistics: {e}")
        
        response_data = {
            'session_info': status_data,
            'detailed_statistics': detailed_stats
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting detailed session status: {str(e)}")
        return jsonify({
            'error': 'Failed to get detailed session status',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/<form_id>', methods=['GET'])
def get_form_data(form_id):
    """
    Get complete form data including questions and options
    
    Response:
    {
        "form": {
            "id": "uuid",
            "url": "https://...",
            "title": "Form Title",
            "questions": [...],
            "sections": [...]
        }
    }
    """
    try:
        if not supabase_scraper:
            return jsonify({'error': 'Database not available'}), 500
        
        form_data = supabase_scraper.get_form_with_questions(form_id)
        
        if not form_data:
            return jsonify({'error': 'Form not found'}), 404
        
        return jsonify({'form': form_data})
        
    except Exception as e:
        logger.error(f"Error getting form data: {str(e)}")
        return jsonify({
            'error': 'Failed to get form data',
            'details': str(e)
        }), 500

@forms_bp.route('/forms', methods=['GET'])
def list_forms():
    """
    List recently scraped forms
    
    Query parameters:
    - limit: Number of forms to return (default: 10, max: 100)
    - offset: Number of forms to skip (default: 0)
    
    Response:
    {
        "forms": [...],
        "total_count": 25,
        "limit": 10,
        "offset": 0
    }
    """
    try:
        if not supabase_scraper:
            return jsonify({'error': 'Database not available'}), 500
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 10)), 100)  # Max 100 forms
        offset = int(request.args.get('offset', 0))
        
        # Get forms (note: this is a simplified version, you might want to implement pagination in Supabase)
        forms = supabase_scraper.get_recent_forms(limit)
        
        return jsonify({
            'forms': forms,
            'limit': limit,
            'offset': offset,
            'returned_count': len(forms)
        })
        
    except Exception as e:
        logger.error(f"Error listing forms: {str(e)}")
        return jsonify({
            'error': 'Failed to list forms',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/search', methods=['GET'])
def search_forms():
    """
    Search forms by URL or title
    
    Query parameters:
    - q: Search query
    - limit: Number of results (default: 10, max: 50)
    
    Response:
    {
        "forms": [...],
        "query": "search term",
        "results_count": 5
    }
    """
    try:
        if not supabase_scraper:
            return jsonify({'error': 'Database not available'}), 500
        
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        
        if not query:
            return jsonify({'error': 'Search query (q) is required'}), 400
        
        # Simple search implementation (you might want to enhance this with full-text search)
        # For now, we'll search by URL containing the query
        try:
            result = supabase_scraper.client.table('forms').select('*').ilike('url', f'%{query}%').limit(limit).execute()
            forms = result.data
        except Exception as e:
            logger.error(f"Search query failed: {e}")
            forms = []
        
        return jsonify({
            'forms': forms,
            'query': query,
            'results_count': len(forms)
        })
        
    except Exception as e:
        logger.error(f"Error searching forms: {str(e)}")
        return jsonify({
            'error': 'Failed to search forms',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/stats', methods=['GET'])
def get_forms_stats():
    """
    Get overall forms processing statistics
    
    Response:
    {
        "total_forms": 150,
        "total_questions": 1250,
        "recent_sessions": 5,
        "scraper_config": {...}
    }
    """
    try:
        stats = {
            'scraper_available': bool(integrated_scraper),
            'database_available': bool(supabase_scraper),
            'ai_processing_enabled': bool(OPENAI_API_KEY),
            'scraper_config': integrated_scraper.get_scraper_stats() if integrated_scraper else None
        }
        
        # Get database statistics if available
        if supabase_scraper:
            try:
                # Get total forms count
                forms_result = supabase_scraper.client.table('forms').select('id', count='exact').execute()
                stats['total_forms'] = forms_result.count if hasattr(forms_result, 'count') else 0
                
                # Get total questions count
                questions_result = supabase_scraper.client.table('form_questions').select('id', count='exact').execute()
                stats['total_questions'] = questions_result.count if hasattr(questions_result, 'count') else 0
                
                # Get recent sessions count
                sessions_result = supabase_scraper.client.table('form_scrape_sessions').select('id', count='exact').execute()
                stats['total_sessions'] = sessions_result.count if hasattr(sessions_result, 'count') else 0
                
            except Exception as e:
                logger.error(f"Failed to get database statistics: {e}")
                stats['database_error'] = str(e)
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting forms stats: {str(e)}")
        return jsonify({
            'error': 'Failed to get forms statistics',
            'details': str(e)
        }), 500

@forms_bp.route('/forms/test', methods=['POST'])
def test_form_processing():
    """
    Test form processing with a single URL (for development/testing)
    
    Request body:
    {
        "url": "https://docs.google.com/forms/d/..."
    }
    
    Response:
    {
        "success": true,
        "form_data": {...},
        "processing_time_ms": 5000,
        "quality_assessment": {...}
    }
    """
    try:
        if not integrated_scraper:
            return jsonify({'error': 'Form scraper not available'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        url = data.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not validate_google_forms_url(url):
            return jsonify({'error': 'Invalid Google Forms URL'}), 400
        
        logger.info(f"Testing form processing for: {url}")
        
        # Process single form
        result = integrated_scraper.process_single_form(url)
        
        # Return result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing form processing: {str(e)}")
        return jsonify({
            'error': 'Failed to test form processing',
            'details': str(e)
        }), 500

# Error handlers
@forms_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@forms_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@forms_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Health check endpoint
@forms_bp.route('/forms/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for forms processing
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'integrated_scraper': bool(integrated_scraper),
            'firecrawl_api': bool(FIRECRAWL_API_KEY),
            'openai_api': bool(OPENAI_API_KEY),
            'supabase_db': bool(supabase_scraper)
        }
    }
    
    # Check if any critical components are missing
    if not integrated_scraper or not FIRECRAWL_API_KEY:
        health_status['status'] = 'degraded'
        health_status['message'] = 'Some components are not available'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

