#!/usr/bin/env python3
"""
Integrated Form Scraper
Orchestrates the complete Google Forms processing pipeline:
Form Scraping → AI Processing → Quality Assessment → Database Storage
"""

import os
import json
import logging
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dotenv import load_dotenv

from flexible_form_scraper import FlexibleFormScraper
from openai_form_processor import OpenAIFormProcessor
from models.form import FormScrapeSession, FormProcessingLog, ProcessingStage, ProcessingStatus

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegratedFormScraper:
    """
    Integrated form scraper that orchestrates the complete pipeline
    """
    
    def __init__(self, firecrawl_api_key: str, supabase_integration, openai_api_key: Optional[str] = None):
        """
        Initialize the integrated form scraper
        
        Args:
            firecrawl_api_key: Firecrawl API key for web scraping
            supabase_integration: Supabase integration instance for data storage
            openai_api_key: OpenAI API key for AI processing (optional, will use env var)
        """
        self.firecrawl_api_key = firecrawl_api_key
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.supabase = supabase_integration
        
        # Initialize components
        self.form_scraper = FlexibleFormScraper(firecrawl_api_key)
        self.ai_processor = OpenAIFormProcessor(self.openai_api_key) if self.openai_api_key else None
        
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = {
            'min_quality_score': 0.3,  # Minimum quality score to process with AI
            'max_retries': 2,
            'retry_delay': 5,  # seconds
            'batch_delay': 1,  # seconds between forms in batch processing
            'enable_ai_processing': bool(self.openai_api_key),
            'store_raw_content': True,
            'detailed_logging': True
        }
        
        self.logger.info(f"IntegratedFormScraper initialized - AI Processing: {self.config['enable_ai_processing']}")
    
    def process_single_form(self, url: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a single Google Form through the complete pipeline
        
        Args:
            url: Google Form URL to process
            session_id: Optional session ID for tracking
            
        Returns:
            Processing result with form data and metadata
        """
        start_time = time.time()
        processing_logs = []
        
        try:
            self.logger.info(f"Starting form processing: {url}")
            
            # Step 1: Scrape form content
            self._log_processing_step(processing_logs, session_id, url, 
                                    ProcessingStage.SCRAPING, ProcessingStatus.SUCCESS,
                                    "Starting form scraping")
            
            scrape_result = self.form_scraper.scrape_form(url)
            
            if not scrape_result.get('success'):
                error_msg = scrape_result.get('error', 'Unknown scraping error')
                self._log_processing_step(processing_logs, session_id, url,
                                        ProcessingStage.SCRAPING, ProcessingStatus.ERROR,
                                        f"Scraping failed: {error_msg}")
                
                return {
                    'success': False,
                    'url': url,
                    'error': error_msg,
                    'stage': 'scraping',
                    'processing_time_ms': int((time.time() - start_time) * 1000),
                    'processing_logs': processing_logs
                }
            
            # Check content quality
            quality_assessment = scrape_result.get('quality_assessment', {})
            quality_score = quality_assessment.get('score', 0.0)
            quality_category = quality_assessment.get('quality', 'unknown')
            
            self._log_processing_step(processing_logs, session_id, url,
                                    ProcessingStage.SCRAPING, ProcessingStatus.SUCCESS,
                                    f"Scraping completed - Quality: {quality_category} (Score: {quality_score:.2f})")
            
            # Step 2: AI Processing (if enabled and quality is sufficient)
            form_data = None
            ai_result = None
            
            if self.config['enable_ai_processing'] and quality_score >= self.config['min_quality_score']:
                self._log_processing_step(processing_logs, session_id, url,
                                        ProcessingStage.AI_PROCESSING, ProcessingStatus.SUCCESS,
                                        "Starting AI processing")
                
                try:
                    ai_result = self.ai_processor.extract_form_data(scrape_result)
                    form_data = ai_result.form
                    
                    self._log_processing_step(processing_logs, session_id, url,
                                            ProcessingStage.AI_PROCESSING, ProcessingStatus.SUCCESS,
                                            f"AI processing completed - Confidence: {ai_result.confidence_score:.2f}, "
                                            f"Questions: {len(form_data.questions)}")
                    
                except Exception as e:
                    error_msg = f"AI processing failed: {str(e)}"
                    self.logger.error(error_msg)
                    self._log_processing_step(processing_logs, session_id, url,
                                            ProcessingStage.AI_PROCESSING, ProcessingStatus.ERROR,
                                            error_msg)
                    
                    # Continue without AI processing
                    ai_result = None
            else:
                reason = "AI processing disabled" if not self.config['enable_ai_processing'] else f"Quality too low ({quality_score:.2f} < {self.config['min_quality_score']})"
                self._log_processing_step(processing_logs, session_id, url,
                                        ProcessingStage.AI_PROCESSING, ProcessingStatus.WARNING,
                                        f"Skipping AI processing: {reason}")
            
            # Step 3: Data Storage
            self._log_processing_step(processing_logs, session_id, url,
                                    ProcessingStage.DATA_STORAGE, ProcessingStatus.SUCCESS,
                                    "Starting data storage")
            
            storage_result = None
            if form_data and hasattr(self.supabase, 'store_form_data'):
                try:
                    storage_result = self.supabase.store_form_data(form_data, ai_result)
                    self._log_processing_step(processing_logs, session_id, url,
                                            ProcessingStage.DATA_STORAGE, ProcessingStatus.SUCCESS,
                                            f"Form data stored successfully - ID: {storage_result.get('form_id', 'unknown')}")
                except Exception as e:
                    error_msg = f"Data storage failed: {str(e)}"
                    self.logger.error(error_msg)
                    self._log_processing_step(processing_logs, session_id, url,
                                            ProcessingStage.DATA_STORAGE, ProcessingStatus.ERROR,
                                            error_msg)
            else:
                self._log_processing_step(processing_logs, session_id, url,
                                        ProcessingStage.DATA_STORAGE, ProcessingStatus.WARNING,
                                        "Data storage skipped - no form data or storage not available")
            
            # Step 4: Complete processing
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            self._log_processing_step(processing_logs, session_id, url,
                                    ProcessingStage.COMPLETED, ProcessingStatus.SUCCESS,
                                    f"Processing completed in {processing_time_ms}ms")
            
            # Store processing logs if session exists
            if session_id and hasattr(self.supabase, 'store_processing_logs'):
                try:
                    self.supabase.store_processing_logs(processing_logs)
                except Exception as e:
                    self.logger.error(f"Failed to store processing logs: {e}")
            
            # Prepare final result
            result = {
                'success': True,
                'url': url,
                'form_data': form_data.to_dict() if form_data else None,
                'scrape_result': scrape_result,
                'ai_result': ai_result.to_dict() if ai_result else None,
                'storage_result': storage_result,
                'quality_assessment': quality_assessment,
                'processing_time_ms': processing_time_ms,
                'processing_logs': processing_logs,
                'session_id': session_id
            }
            
            self.logger.info(f"Form processing completed successfully: {url} "
                           f"(Quality: {quality_category}, Time: {processing_time_ms}ms)")
            
            return result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error processing form {url}: {str(e)}"
            self.logger.error(error_msg)
            
            self._log_processing_step(processing_logs, session_id, url,
                                    ProcessingStage.FAILED, ProcessingStatus.ERROR,
                                    error_msg)
            
            return {
                'success': False,
                'url': url,
                'error': error_msg,
                'stage': 'unexpected_error',
                'processing_time_ms': processing_time_ms,
                'processing_logs': processing_logs,
                'session_id': session_id
            }
    
    def process_multiple_forms(self, urls: List[str], user_id: Optional[str] = None,
                              progress_callback: Optional[Callable] = None) -> str:
        """
        Process multiple Google Forms in a session
        
        Args:
            urls: List of Google Form URLs to process
            user_id: Optional user ID for session tracking
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Session ID for tracking progress
        """
        # Create session
        session = FormScrapeSession(
            urls=urls,
            total_urls=len(urls),
            user_id=user_id,
            started_at=datetime.now()
        )
        
        # Store session in database
        session_id = None
        if hasattr(self.supabase, 'create_form_scrape_session'):
            try:
                session_id = self.supabase.create_form_scrape_session(session)
                session.id = session_id
            except Exception as e:
                self.logger.error(f"Failed to create session: {e}")
                session_id = f"local_{int(time.time())}"
        else:
            session_id = f"local_{int(time.time())}"
        
        self.logger.info(f"Starting batch processing session {session_id}: {len(urls)} forms")
        
        # Process forms in background thread
        def process_batch():
            try:
                results = []
                successful_forms = 0
                failed_forms = 0
                
                for i, url in enumerate(urls, 1):
                    self.logger.info(f"Processing form {i}/{len(urls)}: {url}")
                    
                    # Update session status
                    if hasattr(self.supabase, 'update_session_progress'):
                        try:
                            progress_percentage = (i - 1) / len(urls) * 100
                            self.supabase.update_session_progress(
                                session_id, 'processing', progress_percentage, i - 1
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to update session progress: {e}")
                    
                    # Process single form
                    result = self.process_single_form(url, session_id)
                    results.append(result)
                    
                    if result.get('success'):
                        successful_forms += 1
                    else:
                        failed_forms += 1
                    
                    # Call progress callback
                    if progress_callback:
                        try:
                            progress_callback(result, i, len(urls), session_id)
                        except Exception as e:
                            self.logger.error(f"Progress callback error: {e}")
                    
                    # Brief pause between forms
                    if i < len(urls):
                        time.sleep(self.config['batch_delay'])
                
                # Complete session
                session.status = 'completed'
                session.processed_urls = len(urls)
                session.successful_forms = successful_forms
                session.failed_forms = failed_forms
                session.progress_percentage = 100.0
                session.completed_at = datetime.now()
                session.summary = f"{successful_forms} successful, {failed_forms} failed"
                
                # Update session in database
                if hasattr(self.supabase, 'complete_form_scrape_session'):
                    try:
                        self.supabase.complete_form_scrape_session(session)
                    except Exception as e:
                        self.logger.error(f"Failed to complete session: {e}")
                
                self.logger.info(f"Batch processing completed: {session_id} - "
                               f"{successful_forms} successful, {failed_forms} failed")
                
            except Exception as e:
                error_msg = f"Batch processing failed: {str(e)}"
                self.logger.error(error_msg)
                
                # Mark session as failed
                if hasattr(self.supabase, 'fail_form_scrape_session'):
                    try:
                        self.supabase.fail_form_scrape_session(session_id, error_msg)
                    except Exception as e:
                        self.logger.error(f"Failed to mark session as failed: {e}")
        
        # Start processing in background
        thread = threading.Thread(target=process_batch)
        thread.daemon = True
        thread.start()
        
        return session_id
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a processing session"""
        if hasattr(self.supabase, 'get_form_scrape_session'):
            try:
                return self.supabase.get_form_scrape_session(session_id)
            except Exception as e:
                self.logger.error(f"Failed to get session status: {e}")
                return None
        return None
    
    def _log_processing_step(self, logs: List[Dict], session_id: Optional[str], url: str,
                           stage: ProcessingStage, status: ProcessingStatus, message: str,
                           details: Optional[Dict] = None):
        """Add a processing step to the logs"""
        log_entry = {
            'session_id': session_id,
            'url': url,
            'processing_stage': stage.value,
            'status': status.value,
            'message': message,
            'details': details or {},
            'created_at': datetime.now().isoformat()
        }
        logs.append(log_entry)
        
        # Log to console based on status
        if status == ProcessingStatus.ERROR:
            self.logger.error(f"[{stage.value}] {message}")
        elif status == ProcessingStatus.WARNING:
            self.logger.warning(f"[{stage.value}] {message}")
        else:
            self.logger.info(f"[{stage.value}] {message}")
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics and configuration"""
        stats = {
            'scraper_type': 'IntegratedFormScraper',
            'configuration': self.config,
            'components': {
                'form_scraper': self.form_scraper.get_scraper_stats() if self.form_scraper else None,
                'ai_processor': self.ai_processor.get_processor_stats() if self.ai_processor else None,
                'supabase_integration': bool(self.supabase)
            },
            'capabilities': {
                'web_scraping': bool(self.firecrawl_api_key),
                'ai_processing': self.config['enable_ai_processing'],
                'database_storage': bool(self.supabase),
                'session_tracking': bool(self.supabase),
                'quality_assessment': True,
                'batch_processing': True
            }
        }
        return stats

# Utility functions for testing
def test_integrated_scraper(firecrawl_key: str, openai_key: str, test_urls: List[str] = None) -> Dict[str, Any]:
    """Test the integrated form scraper"""
    
    if not test_urls:
        test_urls = [
            "https://docs.google.com/forms/d/e/1FAIpQLSf_example/viewform",  # Replace with actual test URLs
        ]
    
    # Mock Supabase integration for testing
    class MockSupabaseIntegration:
        def create_form_scrape_session(self, session):
            return f"test_session_{int(time.time())}"
        
        def update_session_progress(self, session_id, status, progress, processed):
            print(f"Session {session_id}: {status} - {progress:.1f}% ({processed} processed)")
        
        def complete_form_scrape_session(self, session):
            print(f"Session completed: {session.summary}")
        
        def store_form_data(self, form_data, ai_result):
            return {'form_id': f"test_form_{int(time.time())}"}
    
    mock_supabase = MockSupabaseIntegration()
    scraper = IntegratedFormScraper(firecrawl_key, mock_supabase, openai_key)
    
    print("Testing Integrated Form Scraper...")
    print(f"Configuration: {json.dumps(scraper.get_scraper_stats(), indent=2)}")
    
    # Test single form processing
    if test_urls:
        print(f"\nTesting single form processing: {test_urls[0]}")
        result = scraper.process_single_form(test_urls[0])
        
        if result.get('success'):
            print(f"✅ Single form processing successful!")
            print(f"   Processing time: {result['processing_time_ms']}ms")
            if result.get('form_data'):
                print(f"   Questions extracted: {len(result['form_data']['questions'])}")
        else:
            print(f"❌ Single form processing failed: {result.get('error')}")
    
    # Test batch processing
    if len(test_urls) > 1:
        print(f"\nTesting batch processing: {len(test_urls)} forms")
        session_id = scraper.process_multiple_forms(test_urls[:2])  # Test with first 2 URLs
        print(f"Batch processing started - Session ID: {session_id}")
        
        # Wait a bit and check status
        time.sleep(5)
        status = scraper.get_session_status(session_id)
        if status:
            print(f"Session status: {status}")
    
    return {
        'scraper_stats': scraper.get_scraper_stats(),
        'test_completed': True
    }

if __name__ == "__main__":
    # Test the integrated scraper if run directly
    firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not firecrawl_key:
        print("Please set FIRECRAWL_API_KEY environment variable")
        exit(1)
    
    if not openai_key:
        print("Warning: OPENAI_API_KEY not set - AI processing will be disabled")
    
    # Run test
    test_results = test_integrated_scraper(firecrawl_key, openai_key)
    print(f"\nIntegrated scraper test completed!")

