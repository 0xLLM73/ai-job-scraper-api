#!/usr/bin/env python3
"""
Flexible Form Scraper
Uses Firecrawl to extract content from Google Forms with quality assessment
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

try:
    from firecrawl import FirecrawlApp
except ImportError:
    print("Installing firecrawl-py...")
    os.system("pip3 install firecrawl-py")
    from firecrawl import FirecrawlApp

from models.form import validate_google_forms_url, extract_form_id_from_url

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FormQualityAssessment:
    """Assesses the quality of scraped form content"""
    
    @staticmethod
    def assess_content_quality(content: str, url: str) -> Dict[str, Any]:
        """
        Assess the quality of scraped form content
        Returns quality assessment with score and category
        """
        if not content or len(content.strip()) < 50:
            return {
                'quality': 'invalid',
                'score': 0.0,
                'reason': 'Content too short or empty',
                'content_length': len(content) if content else 0,
                'indicators': []
            }
        
        content_lower = content.lower()
        
        # Check for 404 or error indicators
        error_indicators = [
            '404', 'not found', 'page not found', 'error occurred',
            'access denied', 'permission denied', 'unauthorized',
            'form not found', 'form has been deleted'
        ]
        
        if any(indicator in content_lower for indicator in error_indicators):
            return {
                'quality': '404',
                'score': 0.0,
                'reason': 'Error page or form not accessible',
                'content_length': len(content),
                'indicators': [ind for ind in error_indicators if ind in content_lower]
            }
        
        # Form-specific indicators
        form_indicators = [
            'form', 'question', 'required', 'optional', 'submit',
            'response', 'answer', 'multiple choice', 'checkbox',
            'dropdown', 'text field', 'email', 'name', 'phone',
            'google forms', 'powered by google'
        ]
        
        found_indicators = [ind for ind in form_indicators if ind in content_lower]
        indicator_score = len(found_indicators) / len(form_indicators)
        
        # Content length assessment
        content_length = len(content)
        length_score = min(content_length / 1000, 1.0)  # Normalize to 1000 chars
        
        # Form structure indicators
        structure_indicators = [
            'input', 'select', 'textarea', 'radio', 'checkbox',
            'button', 'label', 'fieldset', 'legend'
        ]
        
        structure_score = sum(1 for ind in structure_indicators if ind in content_lower) / len(structure_indicators)
        
        # Calculate overall quality score
        overall_score = (indicator_score * 0.4 + length_score * 0.3 + structure_score * 0.3)
        
        # Determine quality category
        if overall_score >= 0.7:
            quality = 'good'
        elif overall_score >= 0.4:
            quality = 'moderate'
        else:
            quality = 'poor'
        
        return {
            'quality': quality,
            'score': overall_score,
            'reason': f'Form content quality assessment: {quality}',
            'content_length': content_length,
            'indicators': found_indicators,
            'scores': {
                'indicator_score': indicator_score,
                'length_score': length_score,
                'structure_score': structure_score
            }
        }

class FlexibleFormScraper:
    """
    Flexible form scraper using Firecrawl for content extraction
    Adapted from FlexibleJobScraper for Google Forms processing
    """
    
    def __init__(self, firecrawl_api_key: str):
        """Initialize the form scraper with Firecrawl API key"""
        if not firecrawl_api_key:
            raise ValueError("Firecrawl API key is required")
        
        self.firecrawl_api_key = firecrawl_api_key
        self.app = FirecrawlApp(api_key=firecrawl_api_key)
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.scrape_config = {
            'formats': ['markdown', 'html'],
            'includeTags': ['form', 'input', 'select', 'textarea', 'button', 'label', 'fieldset', 'legend'],
            'excludeTags': ['script', 'style', 'nav', 'footer', 'header', 'aside'],
            'onlyMainContent': False,  # We want form elements which might be outside main content
            'waitFor': 2000,  # Wait for dynamic content to load
        }
    
    def scrape_form(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single Google Form URL
        Returns scraped content with quality assessment
        """
        start_time = time.time()
        
        try:
            # Validate URL
            if not validate_google_forms_url(url):
                return {
                    'success': False,
                    'error': 'Invalid Google Forms URL',
                    'url': url,
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
            
            self.logger.info(f"Scraping form: {url}")
            
            # Extract form ID
            form_id = extract_form_id_from_url(url)
            
            # Scrape with Firecrawl
            result = self.app.scrape_url(url, params=self.scrape_config)
            
            if not result or not result.get('success'):
                error_msg = result.get('error', 'Unknown scraping error') if result else 'No response from Firecrawl'
                return {
                    'success': False,
                    'error': f'Firecrawl scraping failed: {error_msg}',
                    'url': url,
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
            
            # Extract content
            markdown_content = result.get('markdown', '')
            html_content = result.get('html', '')
            metadata = result.get('metadata', {})
            
            # Assess content quality
            primary_content = markdown_content or html_content
            quality_assessment = FormQualityAssessment.assess_content_quality(primary_content, url)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Prepare result
            scrape_result = {
                'success': True,
                'url': url,
                'form_id': form_id,
                'content': {
                    'markdown': markdown_content,
                    'html': html_content,
                    'primary': primary_content
                },
                'metadata': {
                    'title': metadata.get('title', ''),
                    'description': metadata.get('description', ''),
                    'language': metadata.get('language', ''),
                    'sourceURL': metadata.get('sourceURL', url),
                    'statusCode': metadata.get('statusCode', 200)
                },
                'quality_assessment': quality_assessment,
                'processing_time_ms': processing_time_ms,
                'scraped_at': datetime.now().isoformat()
            }
            
            self.logger.info(f"Form scraped successfully: {url} (Quality: {quality_assessment['quality']}, "
                           f"Score: {quality_assessment['score']:.2f}, Time: {processing_time_ms}ms)")
            
            return scrape_result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Error scraping form {url}: {str(e)}"
            self.logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'url': url,
                'processing_time_ms': processing_time_ms
            }
    
    def scrape_multiple_forms(self, urls: List[str], callback=None) -> List[Dict[str, Any]]:
        """
        Scrape multiple Google Forms URLs
        
        Args:
            urls: List of form URLs to scrape
            callback: Optional callback function called after each URL is processed
        
        Returns:
            List of scraping results
        """
        results = []
        total_urls = len(urls)
        
        self.logger.info(f"Starting batch scraping of {total_urls} forms")
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processing form {i}/{total_urls}: {url}")
            
            result = self.scrape_form(url)
            results.append(result)
            
            # Call callback if provided
            if callback:
                try:
                    callback(result, i, total_urls)
                except Exception as e:
                    self.logger.error(f"Callback error for {url}: {str(e)}")
            
            # Brief pause between requests to be respectful
            if i < total_urls:
                time.sleep(1)
        
        # Summary statistics
        successful = sum(1 for r in results if r.get('success'))
        failed = total_urls - successful
        
        quality_counts = {}
        for result in results:
            if result.get('success') and 'quality_assessment' in result:
                quality = result['quality_assessment']['quality']
                quality_counts[quality] = quality_counts.get(quality, 0) + 1
        
        self.logger.info(f"Batch scraping completed: {successful} successful, {failed} failed")
        self.logger.info(f"Quality distribution: {quality_counts}")
        
        return results
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get scraper configuration and status"""
        return {
            'scraper_type': 'FlexibleFormScraper',
            'firecrawl_configured': bool(self.firecrawl_api_key),
            'scrape_config': self.scrape_config,
            'supported_formats': ['markdown', 'html'],
            'quality_categories': ['good', 'moderate', 'poor', 'invalid', '404']
        }

# Utility functions
def test_form_scraper(api_key: str, test_urls: List[str] = None) -> Dict[str, Any]:
    """
    Test the form scraper with sample URLs
    """
    if not test_urls:
        test_urls = [
            "https://docs.google.com/forms/d/e/1FAIpQLSf_example/viewform",  # Replace with actual test URL
        ]
    
    scraper = FlexibleFormScraper(api_key)
    
    print("Testing Form Scraper...")
    print(f"Configuration: {scraper.get_scraper_stats()}")
    
    results = []
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        result = scraper.scrape_form(url)
        results.append(result)
        
        if result.get('success'):
            quality = result['quality_assessment']
            print(f"✅ Success - Quality: {quality['quality']} (Score: {quality['score']:.2f})")
            print(f"   Content length: {quality['content_length']} chars")
            print(f"   Processing time: {result['processing_time_ms']}ms")
        else:
            print(f"❌ Failed - Error: {result.get('error')}")
    
    return {
        'test_results': results,
        'scraper_stats': scraper.get_scraper_stats()
    }

if __name__ == "__main__":
    # Test the scraper if run directly
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        print("Please set FIRECRAWL_API_KEY environment variable")
        exit(1)
    
    # Run test
    test_results = test_form_scraper(api_key)
    print(f"\nTest completed. Results: {len(test_results['test_results'])} forms processed")

