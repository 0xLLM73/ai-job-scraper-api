import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class ProcessedJobData:
    """Structured job data extracted by AI from raw content"""
    # Core job information
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    employment_type: str = ""  # full-time, part-time, contract, etc.
    remote_policy: str = ""   # remote, hybrid, on-site, etc.
    
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
    application_questions: List[str] = None  # NEW: Application form questions
    application_url: str = ""  # NEW: Direct application URL
    
    # Experience and education
    experience_required: str = ""
    education_required: str = ""
    
    # Skills and technologies
    required_skills: List[str] = None
    preferred_skills: List[str] = None
    
    # Metadata
    processed_at: datetime = None
    confidence_score: float = 0.0
    ai_confidence: float = 0.0  # AI's self-assessment
    validation_confidence: float = 0.0  # Objective validation score
    extraction_notes: List[str] = None
    
    # NEW: OpenAI conversation log for transparency
    openai_conversation: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.responsibilities is None:
            self.responsibilities = []
        if self.requirements is None:
            self.requirements = []
        if self.preferred_qualifications is None:
            self.preferred_qualifications = []
        if self.benefits is None:
            self.benefits = []
        if self.required_skills is None:
            self.required_skills = []
        if self.preferred_skills is None:
            self.preferred_skills = []
        if self.extraction_notes is None:
            self.extraction_notes = []
        if self.application_questions is None:
            self.application_questions = []
        if self.openai_conversation is None:
            self.openai_conversation = {}
        if self.processed_at is None:
            self.processed_at = datetime.utcnow()

class OpenAIJobProcessor:
    """
    Production-ready AI job processor using OpenAI GPT-4.
    Extracts structured job data from raw scraped content with high accuracy.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Enhanced system prompt for better confidence scoring
        self.system_prompt = """You are an expert job posting analyzer. Your task is to extract structured information from job posting content and return it as valid JSON.

CRITICAL RULES:
1. Return ONLY valid JSON - no explanations, no markdown, no extra text
2. If information is not found, use empty string "" or empty array []
3. For salary, try to extract numeric values even from text like "$100k-150k" → min: 100000, max: 150000
4. Split lists properly - if you see "Python, JavaScript, React" → ["Python", "JavaScript", "React"]
5. Be thorough in extraction - capture all available information
6. IMPORTANT: Look for application questions/forms - extract any questions candidates need to answer

CONFIDENCE SCORING GUIDELINES:
- 0.9-1.0: All core fields (title, company, description, requirements) clearly present with detailed information
- 0.7-0.8: Most core fields present, some minor gaps in details
- 0.5-0.6: Basic information present but missing several important details
- 0.3-0.4: Limited information available, significant gaps
- 0.0-0.2: Very sparse content or mostly irrelevant information

EXTRACTION PRIORITIES:
- Job title and company name are most important
- Look for salary information in any format (ranges, annual, hourly, etc.)
- Separate required vs preferred qualifications carefully
- Extract all skills/technologies mentioned
- Identify remote work policies (remote, hybrid, on-site)
- Extract years of experience required
- Capture benefits and company culture information
- FIND APPLICATION QUESTIONS: Look for forms, questionnaires, or specific questions candidates must answer
- Extract application URLs and instructions

Return this exact JSON structure:"""

        # Enhanced JSON schema for the response
        self.response_schema = {
            "job_title": "string",
            "company_name": "string", 
            "location": "string",
            "employment_type": "string",
            "remote_policy": "string",
            "job_description": "string (first 500 words summary)",
            "responsibilities": ["array of strings"],
            "requirements": ["array of required qualifications"],
            "preferred_qualifications": ["array of preferred qualifications"],
            "benefits": ["array of benefits"],
            "salary_min": "number or null",
            "salary_max": "number or null", 
            "salary_currency": "string (USD, EUR, etc.)",
            "salary_text": "string (original text)",
            "company_description": "string",
            "company_size": "string",
            "industry": "string",
            "application_deadline": "string or null",
            "application_instructions": "string",
            "application_questions": ["array of specific questions candidates must answer when applying"],
            "application_url": "string (direct application URL if found)",
            "experience_required": "string (e.g., '3-5 years')",
            "education_required": "string",
            "required_skills": ["array of required technical skills"],
            "preferred_skills": ["array of preferred skills"],
            "confidence_score": "number between 0 and 1 based on information completeness and clarity"
        }
    
    def extract_job_data(self, raw_markdown: str, url: str = "") -> ProcessedJobData:
        """
        Extract structured job data using OpenAI GPT-4
        """
        logger.info(f"Processing job content with OpenAI ({len(raw_markdown)} chars)")
        
        try:
            # Prepare the content (truncate if too long to avoid token limits)
            content = self._prepare_content(raw_markdown, url)
            
            # Create the extraction prompt
            user_prompt = f"""Extract job posting information from this content:

URL: {url}

CONTENT:
{content}

Return the JSON structure with all available information. Be thorough in extraction and provide an accurate confidence score based on the completeness and clarity of the extracted information:"""

            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt + "\n" + json.dumps(self.response_schema, indent=2)},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use latest GPT-4 variant
                messages=messages,
                response_format={"type": "json_object"},  # Ensure JSON response
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000  # Sufficient for structured response
            )
            
            # Parse the response
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Save the full OpenAI conversation for transparency and debugging
            conversation_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "model": "gpt-4o",
                "messages": messages,
                "response": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "response_metadata": {
                    "finish_reason": response.choices[0].finish_reason,
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
            }
            
            # Add conversation to extracted data
            extracted_data["openai_conversation"] = conversation_log
            
            # Convert to our data structure
            processed_data = self._convert_to_processed_data(extracted_data, raw_markdown)
            
            logger.info(f"Successfully extracted job data - AI confidence: {processed_data.ai_confidence:.2f}, Validation: {processed_data.validation_confidence:.2f}, Final: {processed_data.confidence_score:.2f}")
            return processed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_data(raw_markdown, f"JSON parsing failed: {e}")
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {e}")
            return self._create_fallback_data(raw_markdown, f"OpenAI API error: {e}")
    
    def _prepare_content(self, raw_markdown: str, url: str) -> str:
        """Prepare content for OpenAI processing with improved prioritization"""
        # Limit content to avoid token limits (roughly 8000 tokens = 32000 characters)
        max_content_length = 25000
        
        if len(raw_markdown) > max_content_length:
            # Enhanced priority keywords for better content preservation
            lines = raw_markdown.split('\n')
            important_content = []
            current_length = 0
            
            # High-priority keywords that indicate core job information
            high_priority_keywords = [
                'responsibilities', 'requirements', 'qualifications', 'experience',
                'salary', 'benefits', 'compensation', 'what you', 'we are looking',
                'we offer', 'skills', 'must have', 'required', 'preferred'
            ]
            
            # Medium-priority keywords for additional context
            medium_priority_keywords = [
                'about', 'role', 'position', 'job', 'company', 'team', 'culture',
                'remote', 'hybrid', 'location', 'apply', 'join', 'opportunity'
            ]
            
            # First pass: add high-priority lines
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in high_priority_keywords):
                    if current_length + len(line) < max_content_length * 0.7:  # Reserve 30% for other content
                        important_content.append(line)
                        current_length += len(line)
            
            # Second pass: add medium-priority lines
            for line in lines:
                if line not in important_content:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in medium_priority_keywords):
                        if current_length + len(line) < max_content_length * 0.9:  # Reserve 10% for any remaining content
                            important_content.append(line)
                            current_length += len(line)
            
            # Third pass: fill remaining space with other content
            for line in lines:
                if line not in important_content:
                    if current_length + len(line) < max_content_length:
                        important_content.append(line)
                        current_length += len(line)
                    else:
                        break
            
            content = '\n'.join(important_content)
            logger.info(f"Truncated content from {len(raw_markdown)} to {len(content)} chars")
        else:
            content = raw_markdown
        
        return content
    
    def _calculate_validation_confidence(self, extracted: Dict[str, Any], raw_content: str) -> float:
        """
        Calculate objective confidence score based on data completeness and validation
        """
        score = 0.0
        max_score = 105.0  # Updated to include application information bonus
        
        # Core fields validation (40 points)
        if extracted.get('job_title', '').strip():
            score += 15
        if extracted.get('company_name', '').strip():
            score += 15
        if extracted.get('job_description', '').strip() and len(extracted.get('job_description', '')) > 50:
            score += 10
        
        # Requirements and responsibilities (25 points)
        responsibilities = extracted.get('responsibilities', [])
        requirements = extracted.get('requirements', [])
        if responsibilities and len(responsibilities) > 0:
            score += 10
        if requirements and len(requirements) > 0:
            score += 10
        if len(responsibilities) + len(requirements) > 5:
            score += 5  # Bonus for detailed lists
        
        # Skills extraction (15 points)
        required_skills = extracted.get('required_skills', [])
        preferred_skills = extracted.get('preferred_skills', [])
        if required_skills and len(required_skills) > 0:
            score += 8
        if preferred_skills and len(preferred_skills) > 0:
            score += 4
        if len(required_skills) + len(preferred_skills) > 3:
            score += 3  # Bonus for comprehensive skills
        
        # Location and work arrangement (10 points)
        if extracted.get('location', '').strip():
            score += 5
        if extracted.get('remote_policy', '').strip():
            score += 5
        
        # Compensation information (10 points)
        salary_text = extracted.get('salary_text', '').strip()
        salary_min = extracted.get('salary_min')
        salary_max = extracted.get('salary_max')
        benefits = extracted.get('benefits', [])
        
        if salary_text or salary_min or salary_max:
            score += 5
        if benefits and len(benefits) > 0:
            score += 5
        
        # Application information bonus (5 points)
        application_questions = extracted.get('application_questions', [])
        application_url = extracted.get('application_url', '').strip()
        
        if application_questions and len(application_questions) > 0:
            score += 3  # Bonus for finding application questions
        if application_url:
            score += 2  # Bonus for finding application URL
        
        # Content quality validation
        content_length = len(raw_content)
        if content_length < 500:
            score *= 0.5  # Penalty for very short content
        elif content_length > 10000:
            score *= 1.1  # Bonus for comprehensive content (capped at max_score)
        
        # Normalize to 0-1 range
        confidence = min(score / max_score, 1.0)
        
        return confidence
    
    def _combine_confidence_scores(self, ai_confidence: float, validation_confidence: float) -> float:
        """
        Combine AI self-assessment with objective validation for final confidence score
        """
        # Weighted average: 40% AI assessment, 60% objective validation
        # This gives more weight to objective metrics while still considering AI assessment
        final_confidence = (0.4 * ai_confidence) + (0.6 * validation_confidence)
        
        # Apply penalties for extreme mismatches
        confidence_diff = abs(ai_confidence - validation_confidence)
        if confidence_diff > 0.5:
            # Large mismatch suggests uncertainty
            final_confidence *= 0.8
        
        return min(final_confidence, 1.0)
    
    def _convert_to_processed_data(self, extracted: Dict[str, Any], raw_content: str) -> ProcessedJobData:
        """Convert OpenAI response to ProcessedJobData with enhanced confidence scoring"""
        
        # Get AI's confidence assessment
        ai_confidence = extracted.get('confidence_score', 0.0)
        
        # Calculate objective validation confidence
        validation_confidence = self._calculate_validation_confidence(extracted, raw_content)
        
        # Combine scores for final confidence
        final_confidence = self._combine_confidence_scores(ai_confidence, validation_confidence)
        
        # Generate extraction notes
        notes = ['Extracted using OpenAI GPT-4o with enhanced confidence scoring']
        if abs(ai_confidence - validation_confidence) > 0.3:
            notes.append(f"Confidence mismatch detected: AI={ai_confidence:.2f}, Validation={validation_confidence:.2f}")
        if final_confidence < 0.3:
            notes.append("Low confidence extraction - manual review recommended")
        
        return ProcessedJobData(
            job_title=extracted.get('job_title', ''),
            company_name=extracted.get('company_name', ''),
            location=extracted.get('location', ''),
            employment_type=extracted.get('employment_type', ''),
            remote_policy=extracted.get('remote_policy', ''),
            job_description=extracted.get('job_description', ''),
            responsibilities=extracted.get('responsibilities', []),
            requirements=extracted.get('requirements', []),
            preferred_qualifications=extracted.get('preferred_qualifications', []),
            benefits=extracted.get('benefits', []),
            salary_min=extracted.get('salary_min'),
            salary_max=extracted.get('salary_max'),
            salary_currency=extracted.get('salary_currency', 'USD'),
            salary_text=extracted.get('salary_text', ''),
            company_description=extracted.get('company_description', ''),
            company_size=extracted.get('company_size', ''),
            industry=extracted.get('industry', ''),
            application_deadline=extracted.get('application_deadline'),
            application_instructions=extracted.get('application_instructions', ''),
            experience_required=extracted.get('experience_required', ''),
            education_required=extracted.get('education_required', ''),
            required_skills=extracted.get('required_skills', []),
            preferred_skills=extracted.get('preferred_skills', []),
            confidence_score=final_confidence,
            ai_confidence=ai_confidence,
            validation_confidence=validation_confidence,
            extraction_notes=notes,
            application_questions=extracted.get('application_questions', []),
            application_url=extracted.get('application_url', ''),
            openai_conversation=extracted.get('openai_conversation', {})
        )
    
    def _create_fallback_data(self, raw_markdown: str, error_msg: str) -> ProcessedJobData:
        """Create fallback data when OpenAI processing fails"""
        return ProcessedJobData(
            job_title="Extraction Failed",
            company_name="Unknown",
            job_description=raw_markdown[:500] + "..." if len(raw_markdown) > 500 else raw_markdown,
            confidence_score=0.0,
            ai_confidence=0.0,
            validation_confidence=0.0,
            extraction_notes=[f"OpenAI extraction failed: {error_msg}"],
            application_questions=[],
            application_url="",
            openai_conversation={}
        )

def test_openai_processor():
    """Test the OpenAI processor with sample content"""
    # Check if API key is available
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment variables")
        print("Add your OpenAI API key to .env file: OPENAI_API_KEY=sk-...")
        return
    
    processor = OpenAIJobProcessor(api_key)
    
    # Sample job posting content
    sample_content = """
# Senior Software Engineer - Full Stack

## About Stripe
Stripe is building economic infrastructure for the internet. Businesses of every size—from new startups to public companies—use our software to accept payments.

## The Role
We're looking for a Senior Software Engineer to join our Payments team. You'll work on core payment processing systems that handle billions of dollars in transactions.

## What you'll do
- Build and maintain high-performance payment processing systems
- Design APIs used by millions of developers worldwide  
- Collaborate with product, design, and infrastructure teams
- Mentor junior engineers and lead technical discussions

## Who you are
- 5+ years of experience in software engineering
- Strong proficiency in Ruby, Python, or Go
- Experience with distributed systems and databases
- Bachelor's degree in Computer Science or equivalent experience

## Nice to have
- Experience with payment systems or fintech
- Knowledge of React and TypeScript
- Previous startup experience

## What we offer
- Competitive salary: $180,000 - $250,000 base
- Equity package
- Health, dental, and vision insurance
- Unlimited PTO
- $3,000 annual learning budget

Location: San Francisco, CA (Hybrid - 3 days in office)
"""
    
    print("=== TESTING OPENAI JOB PROCESSOR ===")
    result = processor.extract_job_data(sample_content, "https://stripe.com/jobs/example")
    
    print(f"✅ Extraction completed!")
    print(f"📋 Title: {result.job_title}")
    print(f"🏢 Company: {result.company_name}")
    print(f"📍 Location: {result.location}")
    print(f"🏠 Remote Policy: {result.remote_policy}")
    print(f"💰 Salary: ${result.salary_min:,} - ${result.salary_max:,} {result.salary_currency}" if result.salary_min else f"💰 Salary: {result.salary_text}")
    print(f"⚡ Required Skills: {', '.join(result.required_skills[:3])}..." if result.required_skills else "⚡ Required Skills: None extracted")
    print(f"📊 Confidence: {result.confidence_score:.2f}")
    print(f"🔧 Responsibilities: {len(result.responsibilities)} items")
    print(f"✅ Requirements: {len(result.requirements)} items")

if __name__ == "__main__":
    test_openai_processor() 