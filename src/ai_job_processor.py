import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ProcessedJobData:
    """Structured job data extracted by AI from raw content"""
    # Core job information
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    employment_type: str = ""  # full-time, part-time, contract, etc.
    
    # Job details
    job_description: str = ""
    responsibilities: List[str] = None
    requirements: List[str] = None
    preferred_qualifications: List[str] = None
    benefits: List[str] = None
    
    # Compensation
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_text: str = ""
    
    # Company info
    company_description: str = ""
    company_size: str = ""
    industry: str = ""
    
    # Application info
    application_deadline: Optional[str] = None
    application_instructions: str = ""
    
    # Metadata
    processed_at: datetime = None
    confidence_score: float = 0.0
    extraction_notes: List[str] = None
    
    def __post_init__(self):
        if self.responsibilities is None:
            self.responsibilities = []
        if self.requirements is None:
            self.requirements = []
        if self.preferred_qualifications is None:
            self.preferred_qualifications = []
        if self.benefits is None:
            self.benefits = []
        if self.extraction_notes is None:
            self.extraction_notes = []
        if self.processed_at is None:
            self.processed_at = datetime.utcnow()

class AIJobProcessor:
    """
    Processes raw job content with AI to extract structured information.
    This is the second step of your original plan: take raw scraped content
    and have an AI model extract the needed information flexibly.
    """
    
    def __init__(self):
        # In a real implementation, you would initialize your AI model here
        # For now, we'll use simple text processing as a demonstration
        pass
    
    def extract_job_data(self, raw_markdown: str, url: str = "") -> ProcessedJobData:
        """
        Extract structured job data from raw markdown content.
        In production, this would use an AI model (OpenAI, Claude, etc.)
        """
        logger.info(f"Processing job content ({len(raw_markdown)} chars)")
        
        # This is a simplified demonstration - in production you'd use:
        # - OpenAI GPT-4 with structured outputs
        # - Claude with function calling
        # - Local LLM with custom training
        # - Custom NLP pipeline
        
        processed_data = ProcessedJobData()
        
        # Simple text extraction (replace with AI model)
        processed_data.extraction_notes.append("Using simple text processing (demo)")
        
        # Extract title from common patterns
        title = self._extract_title(raw_markdown)
        if title:
            processed_data.job_title = title
            processed_data.confidence_score += 0.2
        
        # Extract company from common patterns
        company = self._extract_company(raw_markdown)
        if company:
            processed_data.company_name = company
            processed_data.confidence_score += 0.2
        
        # Extract location
        location = self._extract_location(raw_markdown)
        if location:
            processed_data.location = location
            processed_data.confidence_score += 0.1
        
        # Extract salary information
        salary_info = self._extract_salary(raw_markdown)
        if salary_info:
            processed_data.salary_text = salary_info
            processed_data.confidence_score += 0.1
        
        # Store raw description (first 500 words as summary)
        words = raw_markdown.split()[:500]
        processed_data.job_description = " ".join(words)
        
        # Extract sections
        sections = self._extract_sections(raw_markdown)
        if sections.get('responsibilities'):
            processed_data.responsibilities = sections['responsibilities']
            processed_data.confidence_score += 0.2
        if sections.get('requirements'):
            processed_data.requirements = sections['requirements']
            processed_data.confidence_score += 0.2
        
        logger.info(f"Extracted data with confidence: {processed_data.confidence_score:.2f}")
        return processed_data
    
    def _extract_title(self, text: str) -> str:
        """Extract job title using simple pattern matching"""
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                # Look for title patterns
                if any(word in line.lower() for word in ['engineer', 'developer', 'manager', 'analyst', 'designer', 'director']):
                    return line.replace('#', '').strip()
        return ""
    
    def _extract_company(self, text: str) -> str:
        """Extract company name using simple pattern matching"""
        # Look for "at [Company]" or "Company Name" patterns
        lines = text.split('\n')
        for line in lines[:20]:
            if 'at ' in line.lower() and len(line) < 100:
                parts = line.split(' at ')
                if len(parts) > 1:
                    return parts[-1].strip()
        return ""
    
    def _extract_location(self, text: str) -> str:
        """Extract location information"""
        location_indicators = ['location:', 'based in', 'remote', 'san francisco', 'new york', 'london', 'berlin']
        lines = text.split('\n')
        for line in lines[:30]:
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in location_indicators):
                return line.strip()
        return ""
    
    def _extract_salary(self, text: str) -> str:
        """Extract salary information"""
        salary_indicators = ['salary', '$', 'compensation', 'pay', 'usd', 'eur', 'gbp']
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in salary_indicators):
                if any(char.isdigit() for char in line):
                    return line.strip()
        return ""
    
    def _extract_sections(self, text: str) -> Dict[str, List[str]]:
        """Extract different sections from the job posting"""
        sections = {'responsibilities': [], 'requirements': []}
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect section headers
            line_lower = line.lower()
            if any(word in line_lower for word in ['responsibilities', 'duties', 'what you']):
                current_section = 'responsibilities'
                continue
            elif any(word in line_lower for word in ['requirements', 'qualifications', 'must have']):
                current_section = 'requirements'
                continue
            elif line.startswith('#') or len(line) < 10:
                current_section = None
                continue
            
            # Add to current section
            if current_section and line.startswith('-') or line.startswith('*'):
                sections[current_section].append(line[1:].strip())
        
        return sections

# Example of how this would work with the flexible scraper
def demo_ai_processing():
    """Demonstrate how AI processing works with raw scraped content"""
    
    # Example raw markdown content (what Firecrawl would return)
    sample_markdown = """
# Senior Software Engineer at TechCorp

## About the Role
We're looking for a Senior Software Engineer to join our growing team in San Francisco, CA.

## Responsibilities
- Design and implement scalable web applications
- Collaborate with cross-functional teams
- Mentor junior developers
- Lead technical architecture decisions

## Requirements
- 5+ years of experience in software development
- Proficiency in Python, JavaScript, and React
- Experience with cloud platforms (AWS, GCP)
- Strong problem-solving skills

## Compensation
$150,000 - $200,000 USD annually, plus equity and benefits.

Apply now to join our innovative team!
"""
    
    processor = AIJobProcessor()
    result = processor.extract_job_data(sample_markdown)
    
    print("=== AI PROCESSING DEMO ===")
    print(f"Title: {result.job_title}")
    print(f"Company: {result.company_name}")
    print(f"Location: {result.location}")
    print(f"Salary: {result.salary_text}")
    print(f"Responsibilities: {len(result.responsibilities)} items")
    print(f"Requirements: {len(result.requirements)} items")
    print(f"Confidence: {result.confidence_score:.2f}")
    print(f"Notes: {result.extraction_notes}")

if __name__ == "__main__":
    demo_ai_processing() 