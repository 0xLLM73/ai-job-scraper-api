#!/usr/bin/env python3
"""
Form Models
Data models for Google Forms processing
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class QuestionType(Enum):
    """Supported Google Forms question types"""
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    PARAGRAPH = "paragraph"
    CHECKBOXES = "checkboxes"
    DROPDOWN = "dropdown"
    LINEAR_SCALE = "linear_scale"
    DATE = "date"
    TIME = "time"
    FILE_UPLOAD = "file_upload"
    EMAIL = "email"
    URL = "url"
    NUMBER = "number"

class ProcessingStage(Enum):
    """Form processing stages"""
    SCRAPING = "scraping"
    AI_PROCESSING = "ai_processing"
    DATA_STORAGE = "data_storage"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingStatus(Enum):
    """Processing status types"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class QuestionOption:
    """Represents an option for multiple choice, checkbox, or dropdown questions"""
    option_text: str
    option_index: int
    is_other_option: bool = False
    id: Optional[str] = None

@dataclass
class ValidationRule:
    """Validation rules for form questions"""
    rule_type: str  # 'min_length', 'max_length', 'regex', 'number_range', etc.
    value: Any
    error_message: Optional[str] = None

@dataclass
class FormQuestion:
    """Represents a single question in a Google Form"""
    question_text: str
    question_type: QuestionType
    question_index: int
    description: Optional[str] = None
    is_required: bool = False
    has_other_option: bool = False
    options: List[QuestionOption] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'question_text': self.question_text,
            'question_type': self.question_type.value,
            'question_index': self.question_index,
            'description': self.description,
            'is_required': self.is_required,
            'has_other_option': self.has_other_option,
            'options': [
                {
                    'id': opt.id,
                    'option_text': opt.option_text,
                    'option_index': opt.option_index,
                    'is_other_option': opt.is_other_option
                } for opt in self.options
            ],
            'validation_rules': [
                {
                    'rule_type': rule.rule_type,
                    'value': rule.value,
                    'error_message': rule.error_message
                } for rule in self.validation_rules
            ],
            'settings': self.settings
        }

@dataclass
class FormSection:
    """Represents a section in a Google Form"""
    title: str
    section_index: int
    description: Optional[str] = None
    id: Optional[str] = None

@dataclass
class GoogleForm:
    """Represents a complete Google Form"""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    form_id: Optional[str] = None
    owner_email: Optional[str] = None
    response_count: int = 0
    is_accepting_responses: bool = True
    requires_login: bool = False
    allow_response_editing: bool = False
    collect_email: bool = False
    questions: List[FormQuestion] = field(default_factory=list)
    sections: List[FormSection] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    scraped_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'form_id': self.form_id,
            'owner_email': self.owner_email,
            'response_count': self.response_count,
            'is_accepting_responses': self.is_accepting_responses,
            'requires_login': self.requires_login,
            'allow_response_editing': self.allow_response_editing,
            'collect_email': self.collect_email,
            'questions': [q.to_dict() for q in self.questions],
            'sections': [
                {
                    'id': s.id,
                    'title': s.title,
                    'section_index': s.section_index,
                    'description': s.description
                } for s in self.sections
            ],
            'raw_data': self.raw_data,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }
    
    def get_question_count(self) -> int:
        """Get total number of questions in the form"""
        return len(self.questions)
    
    def get_required_questions_count(self) -> int:
        """Get number of required questions"""
        return sum(1 for q in self.questions if q.is_required)
    
    def get_questions_by_type(self, question_type: QuestionType) -> List[FormQuestion]:
        """Get all questions of a specific type"""
        return [q for q in self.questions if q.question_type == question_type]

@dataclass
class FormScrapeSession:
    """Represents a form scraping session"""
    urls: List[str]
    total_urls: int
    processed_urls: int = 0
    successful_forms: int = 0
    failed_forms: int = 0
    status: str = 'pending'  # 'pending', 'processing', 'completed', 'failed'
    progress_percentage: float = 0.0
    summary: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'urls': self.urls,
            'total_urls': self.total_urls,
            'processed_urls': self.processed_urls,
            'successful_forms': self.successful_forms,
            'failed_forms': self.failed_forms,
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'summary': self.summary,
            'error_details': self.error_details,
            'user_id': self.user_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

@dataclass
class FormProcessingLog:
    """Represents a processing log entry"""
    session_id: str
    url: str
    processing_stage: ProcessingStage
    status: ProcessingStatus
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: Optional[int] = None
    form_id: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class FormExtractionResult:
    """Result of AI form extraction"""
    form: GoogleForm
    confidence_score: float
    ai_confidence: float
    validation_confidence: float
    extraction_details: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'form': self.form.to_dict(),
            'confidence_score': self.confidence_score,
            'ai_confidence': self.ai_confidence,
            'validation_confidence': self.validation_confidence,
            'extraction_details': self.extraction_details,
            'processing_time_ms': self.processing_time_ms
        }

# Utility functions for form processing
def extract_form_id_from_url(url: str) -> Optional[str]:
    """Extract Google Form ID from URL"""
    import re
    
    # Pattern for Google Forms URLs
    patterns = [
        r'/forms/d/([a-zA-Z0-9-_]+)',
        r'formkey=([a-zA-Z0-9-_]+)',
        r'form/([a-zA-Z0-9-_]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def validate_google_forms_url(url: str) -> bool:
    """Validate if URL is a Google Forms URL"""
    google_forms_domains = [
        'docs.google.com/forms',
        'forms.gle',
        'forms.google.com'
    ]
    
    return any(domain in url.lower() for domain in google_forms_domains)

def estimate_form_complexity(form: GoogleForm) -> str:
    """Estimate form complexity based on questions and structure"""
    question_count = form.get_question_count()
    required_count = form.get_required_questions_count()
    section_count = len(form.sections)
    
    # Count complex question types
    complex_types = [QuestionType.LINEAR_SCALE, QuestionType.FILE_UPLOAD, QuestionType.CHECKBOXES]
    complex_questions = sum(1 for q in form.questions if q.question_type in complex_types)
    
    # Calculate complexity score
    complexity_score = (
        question_count * 1 +
        required_count * 0.5 +
        section_count * 2 +
        complex_questions * 1.5
    )
    
    if complexity_score <= 5:
        return "simple"
    elif complexity_score <= 15:
        return "moderate"
    else:
        return "complex"

