import os
import logging
import time
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from firecrawl import FirecrawlApp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RawJobData:
    """Data class for raw scraped job information"""
    url: str
    scraped_at: datetime
    title: Optional[str] = None
    raw_markdown: str = ""
    raw_html: str = ""
    metadata: Dict[str, Any] = None
    ats_platform: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    content_quality: str = "unknown"  # good, poor, invalid, 404
    quality_reason: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class FlexibleJobScraper:
    """
    Flexible job scraper that captures raw content for AI processing.
    This follows your original plan: scrape everything, store raw data,
    then use AI models to extract structured information.
    """
    
    def __init__(self, firecrawl_api_key: str):
        self.app = FirecrawlApp(api_key=firecrawl_api_key)
        
    def detect_ats_platform(self, url: str) -> str:
        """Detect the ATS platform from URL"""
        if "greenhouse.io" in url:
            return "greenhouse"
        elif "lever.co" in url:
            return "lever"
        elif "ashbyhq.com" in url:
            return "ashby"
        elif "workday.com" in url:
            return "workday"
        elif "successfactors.com" in url:
            return "successfactors"
        elif "icims.com" in url:
            return "icims"
        elif "bamboohr.com" in url:
            return "bamboohr"
        return "unknown"
    
    def validate_content_quality(self, content: str, title: str, metadata: Dict[str, Any]) -> tuple[str, str]:
        """
        Validate content quality and detect common issues early.
        Returns (quality_level, reason)
        """
        if not content or len(content.strip()) < 50:
            return "invalid", "Content too short (less than 50 characters)"
        
        # Check for 404 errors
        error_404_patterns = [
            r"404.*error",
            r"page.*not.*found",
            r"sorry.*couldn't.*find",
            r"job.*posting.*might.*have.*closed",
            r"job.*posting.*removed",
            r"not found.*404",
            r"the.*job.*you're.*looking.*for.*might.*have.*closed"
        ]
        
        content_lower = content.lower()
        title_lower = title.lower() if title else ""
        
        for pattern in error_404_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                return "404", f"Detected 404 error pattern: {pattern}"
        
        # Check title for 404 indicators
        if any(indicator in title_lower for indicator in ["404", "not found", "error"]):
            return "404", f"404 detected in title: {title}"
        
        # Check HTTP status code from metadata
        if metadata.get('statusCode') == 404:
            return "404", "HTTP 404 status code returned"
        
        # Check for other error pages
        error_patterns = [
            r"access.*denied",
            r"unauthorized",
            r"forbidden",
            r"server.*error",
            r"temporarily.*unavailable",
            r"maintenance.*mode"
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return "invalid", f"Detected error pattern: {pattern}"
        
        # Check for minimum job posting indicators
        job_indicators = [
            r"responsibilities",
            r"requirements",
            r"qualifications",
            r"experience",
            r"skills",
            r"job.*description",
            r"role.*description",
            r"position.*description",
            r"what.*you.*will.*do",
            r"what.*we.*offer",
            r"benefits",
            r"salary",
            r"apply.*now",
            r"submit.*application"
        ]
        
        indicator_count = sum(1 for pattern in job_indicators 
                             if re.search(pattern, content_lower, re.IGNORECASE))
        
        if indicator_count == 0:
            return "poor", "No job posting indicators found"
        elif indicator_count < 3:
            return "poor", f"Only {indicator_count} job indicators found"
        elif len(content) < 500:
            return "poor", "Content too short for typical job posting"
        else:
            return "good", f"Found {indicator_count} job indicators, good content length"
    
    def scrape_job_raw(self, url: str) -> RawJobData:
        """
        Scrape job posting and return raw content for AI processing.
        This is the flexible approach you originally planned.
        """
        logger.info(f"Scraping raw job data from: {url}")
        
        job_data = RawJobData(
            url=url,
            scraped_at=datetime.utcnow(),
            ats_platform=self.detect_ats_platform(url)
        )
        
        try:
            # Scrape with Firecrawl - get both markdown and HTML
            result = self.app.scrape_url(url)
            
            # Extract raw content
            job_data.raw_markdown = result.markdown or ""
            job_data.raw_html = result.html or ""
            job_data.title = result.metadata.get('title', '') if result.metadata else ""
            job_data.metadata = result.metadata or {}
            job_data.success = True
            
            # Validate content quality early
            quality, reason = self.validate_content_quality(
                job_data.raw_markdown, 
                job_data.title, 
                job_data.metadata
            )
            job_data.content_quality = quality
            job_data.quality_reason = reason
            
            # Log quality assessment
            if quality == "404":
                logger.warning(f"404 error detected for {url}: {reason}")
            elif quality == "invalid":
                logger.warning(f"Invalid content detected for {url}: {reason}")
            elif quality == "poor":
                logger.warning(f"Poor quality content for {url}: {reason}")
            else:
                logger.info(f"Good quality content for {url}: {reason}")
            
            logger.info(f"Successfully scraped {len(job_data.raw_markdown)} chars of content (quality: {quality})")
            return job_data
            
        except Exception as e:
            error_msg = f"Error scraping {url}: {str(e)}"
            logger.error(error_msg)
            job_data.error_message = error_msg
            job_data.success = False
            job_data.content_quality = "invalid"
            job_data.quality_reason = f"Scraping failed: {str(e)}"
            return job_data
    
    def scrape_multiple_jobs_raw(self, urls: List[str]) -> List[RawJobData]:
        """Scrape multiple job postings with rate limiting"""
        results = []
        
        for i, url in enumerate(urls):
            logger.info(f"Scraping job {i+1}/{len(urls)}: {url}")
            
            result = self.scrape_job_raw(url)
            results.append(result)
            
            # Rate limiting - wait between requests
            if i < len(urls) - 1:
                time.sleep(2)  # 2 second delay between requests
        
        successful = sum(1 for r in results if r.success)
        good_quality = sum(1 for r in results if r.content_quality == "good")
        logger.info(f"Completed scraping {successful}/{len(urls)} jobs successfully ({good_quality} good quality)")
        return results

def test_flexible_scraper():
    """Test the flexible scraper with various job sites"""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY not found")
        return
    
    scraper = FlexibleJobScraper(api_key)
    
    # Test URLs from different platforms including the 404 one
    test_urls = [
        "https://boards.greenhouse.io/stripe/jobs/6241615",  # Should work
        "https://jobs.lever.co/netflix/f5a75bf8-5b38-4fb4-86f3-e67e5b1c8956",  # 404 error
    ]
    
    print("Testing flexible job scraper with quality detection...")
    results = scraper.scrape_multiple_jobs_raw(test_urls)
    
    for result in results:
        print(f"\n=== {result.url} ===")
        print(f"Success: {result.success}")
        print(f"Platform: {result.ats_platform}")
        print(f"Title: {result.title}")
        print(f"Content Quality: {result.content_quality}")
        print(f"Quality Reason: {result.quality_reason}")
        print(f"Content length: {len(result.raw_markdown)} chars")
        if result.error_message:
            print(f"Error: {result.error_message}")
        else:
            print(f"First 200 chars: {result.raw_markdown[:200]}...")

if __name__ == "__main__":
    test_flexible_scraper() 