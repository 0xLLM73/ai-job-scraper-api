import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from flexible_job_scraper import FlexibleJobScraper, RawJobData
from openai_job_processor import OpenAIJobProcessor, ProcessedJobData
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class IntegratedFlexibleScraper:
    """
    Integrated scraper that combines:
    1. Flexible raw content scraping (Firecrawl)
    2. AI-powered data extraction 
    3. Supabase storage integration
    
    This implements your original flexible approach.
    """
    
    def __init__(self, firecrawl_api_key: str, supabase_scraper=None):
        self.flexible_scraper = FlexibleJobScraper(firecrawl_api_key)
        self.ai_processor = OpenAIJobProcessor()
        self.supabase_scraper = supabase_scraper
        
    def scrape_and_process_job(self, url: str, session_id: str = None) -> Dict[str, Any]:
        """
        Complete flexible job scraping pipeline:
        1. Scrape raw content with Firecrawl
        2. Validate content quality 
        3. Process with AI to extract structured data (if quality is good enough)
        4. Store in Supabase
        """
        logger.info(f"Starting flexible scraping pipeline for: {url}")
        
        try:
            # Step 1: Scrape raw content
            raw_data = self.flexible_scraper.scrape_job_raw(url)
            
            if not raw_data.success:
                logger.error(f"Failed to scrape raw content: {raw_data.error_message}")
                return {
                    'success': False,
                    'error': raw_data.error_message,
                    'stage': 'scraping'
                }
            
            # Step 2: Check content quality before expensive AI processing
            if raw_data.content_quality == "404":
                logger.warning(f"Skipping AI processing for 404 error: {raw_data.quality_reason}")
                # Create minimal processed data for 404 errors
                processed_data = ProcessedJobData(
                    confidence_score=0.0,
                    ai_confidence=0.0,
                    validation_confidence=0.0,
                    extraction_notes=[f"404 Error: {raw_data.quality_reason}", "Skipped AI processing"]
                )
            elif raw_data.content_quality == "invalid":
                logger.warning(f"Skipping AI processing for invalid content: {raw_data.quality_reason}")
                # Create minimal processed data for invalid content
                processed_data = ProcessedJobData(
                    confidence_score=0.0,
                    ai_confidence=0.0,
                    validation_confidence=0.0,
                    extraction_notes=[f"Invalid Content: {raw_data.quality_reason}", "Skipped AI processing"]
                )
            else:
                # Step 3: Process with AI (only for good/poor quality content)
                if raw_data.content_quality == "poor":
                    logger.warning(f"Processing poor quality content: {raw_data.quality_reason}")
                
                processed_data = self.ai_processor.extract_job_data(raw_data.raw_markdown, url)
                
                # Adjust confidence based on content quality
                if raw_data.content_quality == "poor":
                    # Reduce confidence for poor quality content
                    processed_data.confidence_score *= 0.5
                    processed_data.validation_confidence *= 0.5
                    processed_data.extraction_notes.append(f"Confidence reduced due to poor content quality: {raw_data.quality_reason}")
            
            # Step 4: Combine data for storage
            combined_data = self._combine_data(raw_data, processed_data)
            
            # Step 5: Store in Supabase (if available)
            job_id = None
            if self.supabase_scraper:
                try:
                    job_id = self.supabase_scraper.save_job_posting(combined_data, session_id)
                    if job_id:
                        logger.info(f"Saved job to Supabase with ID: {job_id}")
                    else:
                        logger.warning("Failed to save to Supabase")
                except Exception as e:
                    logger.error(f"Supabase storage error: {e}")
            
            return {
                'success': True,
                'job_id': job_id,
                'raw_data': asdict(raw_data),
                'processed_data': asdict(processed_data),
                'combined_data': combined_data,
                'confidence_score': processed_data.confidence_score,
                'content_quality': raw_data.content_quality,
                'quality_reason': raw_data.quality_reason
            }
            
        except Exception as e:
            logger.error(f"Error in flexible scraping pipeline: {e}")
            return {
                'success': False,
                'error': str(e),
                'stage': 'processing'
            }
    
    def _combine_data(self, raw_data: RawJobData, processed_data: ProcessedJobData) -> Dict[str, Any]:
        """Combine raw and processed data into format expected by Supabase storage"""
        
        # Format salary range from min/max or text
        salary_range = ""
        if processed_data.salary_min and processed_data.salary_max:
            currency = processed_data.salary_currency or "USD"
            salary_range = f"{currency} ${processed_data.salary_min:,} - ${processed_data.salary_max:,}"
        elif processed_data.salary_text:
            salary_range = processed_data.salary_text
        
        # Create job posting in the format expected by Supabase save_job_posting method
        combined_job_data = {
            'url': raw_data.url,
            'title': processed_data.job_title or 'Unknown Title',
            'company': processed_data.company_name or 'Unknown Company',
            'location': processed_data.location or 'Unknown Location',
            'job_type': processed_data.employment_type or 'full-time',
            'salary_range': salary_range,
            'experience_level': processed_data.experience_required,
            'description': processed_data.job_description or '',
            'requirements': processed_data.requirements or [],
            'benefits': processed_data.benefits or [],
            'skills': processed_data.required_skills + processed_data.preferred_skills,  # Combine skills
            'application_url': raw_data.url,  # For now, same as job URL
            'application_email': None,  # Could extract with better AI
            'application_form_structure': {},  # Placeholder
            'source_platform': raw_data.ats_platform,
                         'raw_data': {
                 # Store the original processed data for reference (with date serialization)
                 'ai_extracted': self._serialize_datetime_fields(asdict(processed_data)),
                 'raw_scraped': self._serialize_datetime_fields(asdict(raw_data)),
                 'confidence_score': processed_data.confidence_score,
                 'ai_confidence': processed_data.ai_confidence,
                 'validation_confidence': processed_data.validation_confidence,
                 'extraction_notes': processed_data.extraction_notes,
                 'scraping_method': 'flexible_ai',
                 'content_length': len(raw_data.raw_markdown),
                 # Store truncated raw content for future reprocessing
                 'raw_markdown_sample': raw_data.raw_markdown[:5000] if raw_data.raw_markdown else '',
             }
        }
        
        return combined_job_data
    
    def _serialize_datetime_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(data, dict):
            return {k: self._serialize_datetime_fields(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_datetime_fields(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def scrape_multiple_jobs_flexible(self, urls: List[str], session_id: str = None) -> List[Dict[str, Any]]:
        """Scrape multiple jobs using the flexible approach"""
        results = []
        
        for i, url in enumerate(urls):
            logger.info(f"Processing job {i+1}/{len(urls)}: {url}")
            
            # Log progress if session tracking is available
            if self.supabase_scraper and session_id:
                try:
                    self.supabase_scraper.update_session_progress(session_id, i, url)
                    self.supabase_scraper.log_scrape_info(session_id, url, f"Starting flexible scrape {i+1}/{len(urls)}")
                except Exception as e:
                    logger.warning(f"Failed to log progress: {e}")
            
            result = self.scrape_and_process_job(url, session_id)
            results.append(result)
            
            # Log result with quality information
            if self.supabase_scraper and session_id:
                try:
                    if result['success']:
                        quality = result.get('content_quality', 'unknown')
                        confidence = result.get('confidence_score', 0)
                        if quality == "404":
                            self.supabase_scraper.log_scrape_info(session_id, url, f"404 Error detected - {result.get('quality_reason', 'Page not found')}")
                        elif quality == "invalid":
                            self.supabase_scraper.log_scrape_info(session_id, url, f"Invalid content - {result.get('quality_reason', 'Content validation failed')}")
                        elif quality == "poor":
                            self.supabase_scraper.log_scrape_info(session_id, url, f"Poor quality content processed with reduced confidence {confidence:.2f}")
                        else:
                            self.supabase_scraper.log_scrape_info(session_id, url, f"Successfully processed with confidence {confidence:.2f}")
                    else:
                        self.supabase_scraper.log_scrape_error(session_id, url, result.get('error', 'Unknown error'), {'stage': result.get('stage', 'unknown')})
                except Exception as e:
                    logger.warning(f"Failed to log result: {e}")
        
        successful = sum(1 for r in results if r['success'])
        good_quality = sum(1 for r in results if r.get('content_quality') == 'good')
        poor_quality = sum(1 for r in results if r.get('content_quality') == 'poor')
        errors_404 = sum(1 for r in results if r.get('content_quality') == '404')
        invalid = sum(1 for r in results if r.get('content_quality') == 'invalid')
        
        logger.info(f"Flexible scraping completed: {successful}/{len(urls)} successful")
        logger.info(f"Quality breakdown: {good_quality} good, {poor_quality} poor, {errors_404} 404 errors, {invalid} invalid")
        return results

def demo_integrated_flexible():
    """Demo the complete flexible pipeline"""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY not found")
        return
    
    # Initialize integrated scraper (without Supabase for demo)
    scraper = IntegratedFlexibleScraper(api_key)
    
    # Test with a working job URL
    test_url = "https://boards.greenhouse.io/stripe/jobs/6241615"
    
    print("=== INTEGRATED FLEXIBLE SCRAPING DEMO ===")
    result = scraper.scrape_and_process_job(test_url)
    
    print(f"Success: {result['success']}")
    if result['success']:
        job_data = result['combined_data']['job_posting']
        print(f"Title: {job_data['job_title']}")
        print(f"Company: {job_data['company_name']}")
        print(f"Location: {job_data['location']}")
        print(f"Responsibilities: {len(job_data['responsibilities'])} items")
        print(f"Requirements: {len(job_data['qualifications'])} items")
        print(f"Confidence: {result['confidence_score']:.2f}")
        print(f"Content Length: {job_data['metadata']['content_length']} chars")
    else:
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    demo_integrated_flexible() 