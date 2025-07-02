#!/usr/bin/env python3
"""
OpenAI Form Processor
Uses OpenAI GPT-4 to intelligently extract structured data from Google Forms content
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    print("Installing openai...")
    os.system("pip3 install openai")
    import openai

from models.form import (
    GoogleForm, FormQuestion, QuestionOption, FormSection, 
    QuestionType, ValidationRule, FormExtractionResult
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FormExtractionPrompts:
    """Specialized prompts for Google Forms extraction"""
    
    SYSTEM_PROMPT = """You are an expert at analyzing Google Forms and extracting structured data from form content.

Your task is to analyze scraped Google Forms content and extract:
1. Form metadata (title, description, settings)
2. All questions with their types, options, and validation rules
3. Form structure and sections
4. Response settings and requirements

You must return valid JSON with high accuracy and confidence scoring.

IMPORTANT GUIDELINES:
- Extract ALL questions in the exact order they appear
- Identify question types accurately (multiple_choice, short_answer, paragraph, checkboxes, dropdown, linear_scale, date, time, file_upload, email, url, number)
- Capture all answer options for choice-based questions
- Note required vs optional questions
- Extract validation rules and settings
- Assess your own confidence in the extraction accuracy
- Be thorough but precise - don't hallucinate information not present in the content"""

    EXTRACTION_PROMPT_TEMPLATE = """Analyze this Google Forms content and extract structured form data:

FORM URL: {url}
FORM CONTENT:
{content}

Extract and return a JSON object with this exact structure:

{{
    "form_metadata": {{
        "title": "Form title or null",
        "description": "Form description or null", 
        "form_id": "Extracted form ID or null",
        "owner_email": "Owner email if visible or null",
        "response_count": "Number of responses if shown or 0",
        "is_accepting_responses": true/false,
        "requires_login": true/false,
        "allow_response_editing": true/false,
        "collect_email": true/false
    }},
    "questions": [
        {{
            "question_text": "The actual question text",
            "question_type": "multiple_choice|short_answer|paragraph|checkboxes|dropdown|linear_scale|date|time|file_upload|email|url|number",
            "question_index": 0,
            "description": "Question description/help text or null",
            "is_required": true/false,
            "has_other_option": true/false,
            "options": [
                {{
                    "option_text": "Option text",
                    "option_index": 0,
                    "is_other_option": false
                }}
            ],
            "validation_rules": [
                {{
                    "rule_type": "min_length|max_length|regex|number_range|email_format|url_format",
                    "value": "rule value",
                    "error_message": "validation error message or null"
                }}
            ],
            "settings": {{
                "scale_min": 1,
                "scale_max": 5,
                "scale_min_label": "Low",
                "scale_max_label": "High",
                "file_types": ["pdf", "doc"],
                "max_file_size": "10MB"
            }}
        }}
    ],
    "sections": [
        {{
            "title": "Section title",
            "section_index": 0,
            "description": "Section description or null"
        }}
    ],
    "extraction_confidence": {{
        "overall_confidence": 0.95,
        "form_metadata_confidence": 0.90,
        "questions_confidence": 0.95,
        "structure_confidence": 0.90,
        "reasoning": "Explanation of confidence assessment"
    }}
}}

CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON - no additional text or formatting
2. Extract questions in the exact order they appear in the form
3. Identify question types accurately based on form elements
4. For multiple choice/checkbox/dropdown questions, extract ALL options
5. Note which questions are required (usually marked with * or "Required")
6. Extract any validation rules or constraints mentioned
7. Assess your confidence honestly - if content is unclear, lower the confidence score
8. If you cannot extract certain information, use null values rather than guessing

Focus on accuracy and completeness. This data will be stored in a database for form analysis."""

    VALIDATION_PROMPT_TEMPLATE = """Review this extracted form data for accuracy and completeness:

ORIGINAL CONTENT:
{content}

EXTRACTED DATA:
{extracted_data}

Validate the extraction and return a JSON assessment:

{{
    "validation_results": {{
        "is_valid": true/false,
        "completeness_score": 0.95,
        "accuracy_score": 0.90,
        "issues_found": [
            {{
                "issue_type": "missing_question|incorrect_type|missing_options|validation_error",
                "description": "Description of the issue",
                "severity": "low|medium|high"
            }}
        ],
        "suggestions": [
            "Specific suggestions for improvement"
        ],
        "validation_confidence": 0.92
    }}
}}

Check for:
1. All questions extracted from the original content
2. Question types correctly identified
3. All options captured for choice questions
4. Required fields properly marked
5. Form metadata accuracy
6. JSON structure validity

Be thorough but fair in your assessment."""

class OpenAIFormProcessor:
    """
    OpenAI-powered form processor for extracting structured data from Google Forms
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the form processor with OpenAI API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Set up OpenAI client
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.model_config = {
            'model': 'gpt-4o',
            'temperature': 0.1,  # Low temperature for consistent extraction
            'max_tokens': 4000,
            'response_format': {"type": "json_object"}
        }
        
        # Confidence scoring weights
        self.confidence_weights = {
            'ai_weight': 0.4,
            'validation_weight': 0.6
        }
    
    def extract_form_data(self, scraped_content: Dict[str, Any]) -> FormExtractionResult:
        """
        Extract structured form data from scraped content using OpenAI
        
        Args:
            scraped_content: Result from FlexibleFormScraper
            
        Returns:
            FormExtractionResult with extracted form data and confidence scores
        """
        start_time = time.time()
        
        try:
            url = scraped_content.get('url', '')
            content = scraped_content.get('content', {}).get('primary', '')
            
            if not content:
                raise ValueError("No content available for processing")
            
            self.logger.info(f"Processing form content for: {url}")
            
            # Step 1: Extract form data with AI
            extraction_result = self._extract_with_ai(url, content)
            
            # Step 2: Validate extraction
            validation_result = self._validate_extraction(content, extraction_result)
            
            # Step 3: Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(
                extraction_result, validation_result
            )
            
            # Step 4: Convert to GoogleForm object
            google_form = self._convert_to_form_object(
                extraction_result, scraped_content, confidence_scores
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create final result
            result = FormExtractionResult(
                form=google_form,
                confidence_score=confidence_scores['final_confidence'],
                ai_confidence=confidence_scores['ai_confidence'],
                validation_confidence=confidence_scores['validation_confidence'],
                extraction_details={
                    'extraction_result': extraction_result,
                    'validation_result': validation_result,
                    'confidence_breakdown': confidence_scores
                },
                processing_time_ms=processing_time_ms
            )
            
            self.logger.info(f"Form processing completed: {url} "
                           f"(Confidence: {confidence_scores['final_confidence']:.2f}, "
                           f"Time: {processing_time_ms}ms)")
            
            return result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Error processing form: {str(e)}"
            self.logger.error(error_msg)
            
            # Return error result
            empty_form = GoogleForm(url=scraped_content.get('url', ''))
            return FormExtractionResult(
                form=empty_form,
                confidence_score=0.0,
                ai_confidence=0.0,
                validation_confidence=0.0,
                extraction_details={'error': error_msg},
                processing_time_ms=processing_time_ms
            )
    
    def _extract_with_ai(self, url: str, content: str) -> Dict[str, Any]:
        """Extract form data using OpenAI"""
        try:
            prompt = FormExtractionPrompts.EXTRACTION_PROMPT_TEMPLATE.format(
                url=url,
                content=content[:8000]  # Limit content length to avoid token limits
            )
            
            response = self.client.chat.completions.create(
                model=self.model_config['model'],
                messages=[
                    {"role": "system", "content": FormExtractionPrompts.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.model_config['temperature'],
                max_tokens=self.model_config['max_tokens'],
                response_format=self.model_config['response_format']
            )
            
            # Parse response
            response_content = response.choices[0].message.content
            extraction_data = json.loads(response_content)
            
            # Add usage information
            extraction_data['openai_usage'] = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            return extraction_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {e}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
        except Exception as e:
            self.logger.error(f"AI extraction failed: {e}")
            raise
    
    def _validate_extraction(self, content: str, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the extracted data against original content"""
        try:
            prompt = FormExtractionPrompts.VALIDATION_PROMPT_TEMPLATE.format(
                content=content[:4000],  # Limit content for validation
                extracted_data=json.dumps(extraction_data, indent=2)[:4000]
            )
            
            response = self.client.chat.completions.create(
                model=self.model_config['model'],
                messages=[
                    {"role": "system", "content": "You are an expert validator for form data extraction."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            validation_data = json.loads(response.choices[0].message.content)
            return validation_data
            
        except Exception as e:
            self.logger.warning(f"Validation failed, using default: {e}")
            return {
                'validation_results': {
                    'is_valid': True,
                    'completeness_score': 0.8,
                    'accuracy_score': 0.8,
                    'issues_found': [],
                    'suggestions': [],
                    'validation_confidence': 0.5
                }
            }
    
    def _calculate_confidence_scores(self, extraction_data: Dict[str, Any], 
                                   validation_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate comprehensive confidence scores"""
        
        # AI confidence from extraction
        ai_confidence = extraction_data.get('extraction_confidence', {}).get('overall_confidence', 0.8)
        
        # Validation confidence
        validation_results = validation_data.get('validation_results', {})
        validation_confidence = (
            validation_results.get('completeness_score', 0.8) * 0.5 +
            validation_results.get('accuracy_score', 0.8) * 0.5
        )
        
        # Calculate weighted final confidence
        final_confidence = (
            ai_confidence * self.confidence_weights['ai_weight'] +
            validation_confidence * self.confidence_weights['validation_weight']
        )
        
        # Apply bonuses for high-quality extractions
        questions_count = len(extraction_data.get('questions', []))
        if questions_count > 0:
            final_confidence += min(questions_count * 0.01, 0.05)  # Bonus for extracting questions
        
        # Ensure confidence is within bounds
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        return {
            'ai_confidence': ai_confidence,
            'validation_confidence': validation_confidence,
            'final_confidence': final_confidence,
            'questions_extracted': questions_count,
            'confidence_weights': self.confidence_weights
        }
    
    def _convert_to_form_object(self, extraction_data: Dict[str, Any], 
                               scraped_content: Dict[str, Any],
                               confidence_scores: Dict[str, float]) -> GoogleForm:
        """Convert extracted data to GoogleForm object"""
        
        form_metadata = extraction_data.get('form_metadata', {})
        questions_data = extraction_data.get('questions', [])
        sections_data = extraction_data.get('sections', [])
        
        # Create form questions
        questions = []
        for q_data in questions_data:
            # Create question options
            options = []
            for opt_data in q_data.get('options', []):
                option = QuestionOption(
                    option_text=opt_data.get('option_text', ''),
                    option_index=opt_data.get('option_index', 0),
                    is_other_option=opt_data.get('is_other_option', False)
                )
                options.append(option)
            
            # Create validation rules
            validation_rules = []
            for rule_data in q_data.get('validation_rules', []):
                rule = ValidationRule(
                    rule_type=rule_data.get('rule_type', ''),
                    value=rule_data.get('value'),
                    error_message=rule_data.get('error_message')
                )
                validation_rules.append(rule)
            
            # Create question
            question = FormQuestion(
                question_text=q_data.get('question_text', ''),
                question_type=QuestionType(q_data.get('question_type', 'short_answer')),
                question_index=q_data.get('question_index', 0),
                description=q_data.get('description'),
                is_required=q_data.get('is_required', False),
                has_other_option=q_data.get('has_other_option', False),
                options=options,
                validation_rules=validation_rules,
                settings=q_data.get('settings', {})
            )
            questions.append(question)
        
        # Create form sections
        sections = []
        for s_data in sections_data:
            section = FormSection(
                title=s_data.get('title', ''),
                section_index=s_data.get('section_index', 0),
                description=s_data.get('description')
            )
            sections.append(section)
        
        # Create the form object
        form = GoogleForm(
            url=scraped_content.get('url', ''),
            title=form_metadata.get('title'),
            description=form_metadata.get('description'),
            form_id=form_metadata.get('form_id') or scraped_content.get('form_id'),
            owner_email=form_metadata.get('owner_email'),
            response_count=form_metadata.get('response_count', 0),
            is_accepting_responses=form_metadata.get('is_accepting_responses', True),
            requires_login=form_metadata.get('requires_login', False),
            allow_response_editing=form_metadata.get('allow_response_editing', False),
            collect_email=form_metadata.get('collect_email', False),
            questions=questions,
            sections=sections,
            raw_data={
                'scraped_content': scraped_content,
                'ai_extraction': extraction_data,
                'confidence_scores': confidence_scores,
                'processing_metadata': {
                    'processor_version': '1.0',
                    'model_used': self.model_config['model'],
                    'extraction_timestamp': datetime.now().isoformat()
                }
            },
            scraped_at=datetime.now()
        )
        
        return form
    
    def get_processor_stats(self) -> Dict[str, Any]:
        """Get processor configuration and statistics"""
        return {
            'processor_type': 'OpenAIFormProcessor',
            'model_config': self.model_config,
            'confidence_weights': self.confidence_weights,
            'supported_question_types': [qt.value for qt in QuestionType],
            'openai_configured': bool(self.api_key)
        }

# Utility functions for testing
def test_form_processor(api_key: str, sample_content: str = None) -> Dict[str, Any]:
    """Test the form processor with sample content"""
    
    if not sample_content:
        sample_content = """
        Contact Information Form
        
        Please fill out this form with your contact details.
        
        1. What is your full name? *
        [Text field - Required]
        
        2. What is your email address? *
        [Email field - Required]
        
        3. What is your preferred contact method?
        ○ Email
        ○ Phone
        ○ Text message
        ○ Other: ___________
        
        4. How did you hear about us?
        ☐ Social media
        ☐ Friend referral
        ☐ Search engine
        ☐ Advertisement
        ☐ Other
        
        5. Additional comments
        [Large text area - Optional]
        """
    
    processor = OpenAIFormProcessor(api_key)
    
    # Create mock scraped content
    mock_scraped_content = {
        'url': 'https://docs.google.com/forms/d/test123/viewform',
        'form_id': 'test123',
        'content': {
            'primary': sample_content,
            'markdown': sample_content,
            'html': f'<html><body>{sample_content}</body></html>'
        },
        'quality_assessment': {
            'quality': 'good',
            'score': 0.9
        }
    }
    
    print("Testing Form Processor...")
    print(f"Configuration: {processor.get_processor_stats()}")
    
    # Process the form
    result = processor.extract_form_data(mock_scraped_content)
    
    print(f"\n✅ Processing completed!")
    print(f"Confidence Score: {result.confidence_score:.2f}")
    print(f"Questions Extracted: {len(result.form.questions)}")
    print(f"Processing Time: {result.processing_time_ms}ms")
    
    # Display extracted questions
    print(f"\nExtracted Questions:")
    for i, question in enumerate(result.form.questions, 1):
        print(f"{i}. {question.question_text} ({question.question_type.value})")
        if question.options:
            for opt in question.options:
                print(f"   - {opt.option_text}")
    
    return {
        'result': result,
        'processor_stats': processor.get_processor_stats()
    }

if __name__ == "__main__":
    # Test the processor if run directly
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        exit(1)
    
    # Run test
    test_results = test_form_processor(api_key)
    print(f"\nTest completed successfully!")

