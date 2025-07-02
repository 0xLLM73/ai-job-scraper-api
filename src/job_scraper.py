#!/usr/bin/env python3
"""
Job Posting Scraper using Firecrawl API
Extracts job details and application form structures from job posting URLs
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class JobPosting:
    """Data class for job posting information"""
    url: str
    job_title: str
    company_name: str
    company_description: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    department: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_text: Optional[str] = None
    job_description: Optional[str] = None
    responsibilities: List[str] = None
    qualifications: List[str] = None
    benefits: List[str] = None
    ats_platform: Optional[str] = None
    application_url: Optional[str] = None
    company_logo_url: Optional[str] = None
    posted_date: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.responsibilities is None:
            self.responsibilities = []
        if self.qualifications is None:
            self.qualifications = []
        if self.benefits is None:
            self.benefits = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ApplicationForm:
    """Data class for application form information"""
    form_url: Optional[str] = None
    form_method: str = "POST"
    form_action: Optional[str] = None
    requires_auth: bool = False
    has_captcha: bool = False
    autofill_available: bool = False

@dataclass
class FormField:
    """Data class for form field information"""
    field_name: str
    field_label: Optional[str] = None
    field_type: str = "text"
    field_placeholder: Optional[str] = None
    is_required: bool = False
    field_order: int = 0
    validation_rules: Dict[str, Any] = None
    options: List[str] = None
    default_value: Optional[str] = None
    help_text: Optional[str] = None
    section_name: Optional[str] = None
    visibility: str = "public"
    conditional_logic: Dict[str, Any] = None

    def __post_init__(self):
        if self.validation_rules is None:
            self.validation_rules = {}
        if self.options is None:
            self.options = []
        if self.conditional_logic is None:
            self.conditional_logic = {}

@dataclass
class CompetencyQuestion:
    """Data class for competency-based questions"""
    question_text: str
    question_type: str = "behavioral"
    is_required: bool = False
    word_limit: Optional[int] = None
    character_limit: Optional[int] = None
    question_order: int = 0
    section_name: Optional[str] = None
    help_text: Optional[str] = None

class JobScraper:
    """Main job scraper class using Firecrawl API"""
    
    def __init__(self, firecrawl_api_key: str):
        self.api_key = firecrawl_api_key
        self.base_url = "https://api.firecrawl.dev/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
    def detect_ats_platform(self, url: str) -> str:
        """Detect the ATS platform from the URL"""
        url_lower = url.lower()
        
        if "ashbyhq.com" in url_lower:
            return "ashby"
        elif "greenhouse.io" in url_lower or "boards.greenhouse.io" in url_lower:
            return "greenhouse"
        elif "lever.co" in url_lower:
            return "lever"
        elif "workable.com" in url_lower:
            return "workable"
        elif "smartrecruiters.com" in url_lower:
            return "smartrecruiters"
        elif "bamboohr.com" in url_lower:
            return "bamboohr"
        elif "icims.com" in url_lower:
            return "icims"
        elif "jobvite.com" in url_lower:
            return "jobvite"
        else:
            return "unknown"
    
    def scrape_job_overview(self, url: str) -> Dict[str, Any]:
        """Scrape job overview information using Firecrawl"""
        logger.info(f"Scraping job overview from: {url}")
        
        # Define schema for job overview extraction
        job_schema = {
            "type": "object",
            "properties": {
                "job_title": {"type": "string"},
                "company_name": {"type": "string"},
                "company_description": {"type": "string"},
                "location": {"type": "string"},
                "employment_type": {"type": "string"},
                "department": {"type": "string"},
                "salary_range": {"type": "string"},
                "job_description": {"type": "string"},
                "responsibilities": {"type": "array", "items": {"type": "string"}},
                "qualifications": {"type": "array", "items": {"type": "string"}},
                "benefits": {"type": "array", "items": {"type": "string"}},
                "application_url": {"type": "string"},
                "company_logo_url": {"type": "string"},
                "posted_date": {"type": "string"}
            },
            "required": ["job_title", "company_name"]
        }
        
        payload = {
            "url": url,
            "formats": ["extract", "markdown"],
            "extract": {
                "schema": job_schema
            }
        }
        
        try:
            response = requests.post(f"{self.base_url}/scrape", headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                return result['data']
            else:
                logger.error(f"Failed to scrape job overview: {result}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping job overview: {e}")
            return {}
    
    def scrape_application_form(self, url: str) -> Dict[str, Any]:
        """Scrape application form structure using Firecrawl Actions"""
        logger.info(f"Scraping application form from: {url}")
        
        # Try to navigate to application page
        application_url = url
        if "/application" not in url:
            application_url = url.rstrip('/') + "/application"
        
        # Define actions to interact with the application form
        actions = [
            {"type": "wait", "milliseconds": 2000},
            {"type": "scrape"}
        ]
        
        # Schema for form field extraction
        form_schema = {
            "type": "object",
            "properties": {
                "form_fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field_name": {"type": "string"},
                            "field_label": {"type": "string"},
                            "field_type": {"type": "string"},
                            "field_placeholder": {"type": "string"},
                            "is_required": {"type": "boolean"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "help_text": {"type": "string"}
                        }
                    }
                },
                "form_action": {"type": "string"},
                "form_method": {"type": "string"},
                "has_captcha": {"type": "boolean"},
                "autofill_available": {"type": "boolean"},
                "competency_questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_text": {"type": "string"},
                            "question_type": {"type": "string"},
                            "is_required": {"type": "boolean"},
                            "word_limit": {"type": "number"},
                            "character_limit": {"type": "number"}
                        }
                    }
                }
            }
        }
        
        payload = {
            "url": application_url,
            "formats": ["extract", "markdown"],
            "actions": actions,
            "extract": {
                "schema": form_schema
            }
        }
        
        try:
            response = requests.post(f"{self.base_url}/scrape", headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                return result['data']
            else:
                logger.error(f"Failed to scrape application form: {result}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping application form: {e}")
            return {}
    
    def parse_salary(self, salary_text: str) -> Dict[str, Any]:
        """Parse salary information from text"""
        if not salary_text:
            return {"salary_min": None, "salary_max": None, "salary_currency": "USD", "salary_text": None}
        
        # Remove common prefixes and clean up
        cleaned = re.sub(r'[^\d\-–—$€£¥,K\s]', '', salary_text.upper())
        
        # Extract currency
        currency = "USD"
        if "€" in salary_text:
            currency = "EUR"
        elif "£" in salary_text:
            currency = "GBP"
        elif "¥" in salary_text:
            currency = "JPY"
        
        # Extract numbers
        numbers = re.findall(r'[\d,]+', cleaned)
        if not numbers:
            return {"salary_min": None, "salary_max": None, "salary_currency": currency, "salary_text": salary_text}
        
        # Convert to integers, handling K suffix
        parsed_numbers = []
        for num in numbers:
            clean_num = num.replace(',', '')
            if 'K' in cleaned and len(clean_num) <= 3:
                parsed_numbers.append(int(clean_num) * 1000)
            else:
                parsed_numbers.append(int(clean_num))
        
        if len(parsed_numbers) == 1:
            return {"salary_min": parsed_numbers[0], "salary_max": parsed_numbers[0], "salary_currency": currency, "salary_text": salary_text}
        elif len(parsed_numbers) >= 2:
            return {"salary_min": min(parsed_numbers), "salary_max": max(parsed_numbers), "salary_currency": currency, "salary_text": salary_text}
        
        return {"salary_min": None, "salary_max": None, "salary_currency": currency, "salary_text": salary_text}
    
    def process_job_data(self, url: str, overview_data: Dict[str, Any], form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and structure the scraped data"""
        logger.info("Processing scraped job data")
        
        # Extract job overview data
        extract_data = overview_data.get('extract', {})
        
        # Parse salary information
        salary_info = self.parse_salary(extract_data.get('salary_range', ''))
        
        # Create job posting object
        job_posting = JobPosting(
            url=url,
            job_title=extract_data.get('job_title', ''),
            company_name=extract_data.get('company_name', ''),
            company_description=extract_data.get('company_description'),
            location=extract_data.get('location'),
            employment_type=extract_data.get('employment_type'),
            department=extract_data.get('department'),
            salary_min=salary_info['salary_min'],
            salary_max=salary_info['salary_max'],
            salary_currency=salary_info['salary_currency'],
            salary_text=salary_info['salary_text'],
            job_description=extract_data.get('job_description'),
            responsibilities=extract_data.get('responsibilities', []),
            qualifications=extract_data.get('qualifications', []),
            benefits=extract_data.get('benefits', []),
            ats_platform=self.detect_ats_platform(url),
            application_url=extract_data.get('application_url'),
            company_logo_url=extract_data.get('company_logo_url'),
            metadata={
                'scraped_markdown': overview_data.get('markdown', ''),
                'original_extract': extract_data
            }
        )
        
        # Process form data
        form_extract = form_data.get('extract', {})
        
        application_form = ApplicationForm(
            form_url=url if "/application" in url else url.rstrip('/') + "/application",
            form_method=form_extract.get('form_method', 'POST'),
            form_action=form_extract.get('form_action'),
            has_captcha=form_extract.get('has_captcha', False),
            autofill_available=form_extract.get('autofill_available', False)
        )
        
        # Process form fields
        form_fields = []
        for i, field_data in enumerate(form_extract.get('form_fields', [])):
            field = FormField(
                field_name=field_data.get('field_name', f'field_{i}'),
                field_label=field_data.get('field_label'),
                field_type=field_data.get('field_type', 'text'),
                field_placeholder=field_data.get('field_placeholder'),
                is_required=field_data.get('is_required', False),
                field_order=i,
                options=field_data.get('options', []),
                help_text=field_data.get('help_text')
            )
            form_fields.append(field)
        
        # Process competency questions
        competency_questions = []
        for i, question_data in enumerate(form_extract.get('competency_questions', [])):
            question = CompetencyQuestion(
                question_text=question_data.get('question_text', ''),
                question_type=question_data.get('question_type', 'behavioral'),
                is_required=question_data.get('is_required', False),
                word_limit=question_data.get('word_limit'),
                character_limit=question_data.get('character_limit'),
                question_order=i
            )
            competency_questions.append(question)
        
        return {
            'job_posting': asdict(job_posting),
            'application_form': asdict(application_form),
            'form_fields': [asdict(field) for field in form_fields],
            'competency_questions': [asdict(question) for question in competency_questions]
        }
    
    def scrape_job(self, url: str) -> Dict[str, Any]:
        """Main method to scrape a complete job posting"""
        logger.info(f"Starting complete job scrape for: {url}")
        
        try:
            # Scrape job overview
            overview_data = self.scrape_job_overview(url)
            if not overview_data:
                logger.error(f"Failed to scrape job overview for {url}")
                return {}
            
            # Scrape application form
            form_data = self.scrape_application_form(url)
            
            # Process and structure the data
            processed_data = self.process_job_data(url, overview_data, form_data)
            
            logger.info(f"Successfully scraped job: {processed_data['job_posting']['job_title']} at {processed_data['job_posting']['company_name']}")
            return processed_data
            
        except Exception as e:
            logger.error(f"Error scraping job {url}: {e}")
            return {}
    
    def scrape_multiple_jobs(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape multiple job postings with rate limiting"""
        results = []
        
        for i, url in enumerate(urls):
            logger.info(f"Scraping job {i+1}/{len(urls)}: {url}")
            
            result = self.scrape_job(url)
            if result:
                results.append(result)
            
            # Rate limiting - wait between requests
            if i < len(urls) - 1:
                time.sleep(2)  # 2 second delay between requests
        
        logger.info(f"Completed scraping {len(results)}/{len(urls)} jobs successfully")
        return results

def main():
    """Example usage of the job scraper"""
    # Initialize scraper with API key from environment
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY not found in environment variables")
        print("Please set your Firecrawl API key in a .env file")
        return
    
    scraper = JobScraper(api_key)
    
    # Example job URLs
    test_urls = [
        "https://jobs.ashbyhq.com/Paradigm/8920e2ac-4bc7-4daf-b540-117ab4801b4a"
    ]
    
    # Scrape jobs
    results = scraper.scrape_multiple_jobs(test_urls)
    
    # Save results to file
    output_file = 'scraped_jobs.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Scraped {len(results)} jobs. Results saved to {output_file}")

if __name__ == "__main__":
    main()

