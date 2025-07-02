#!/usr/bin/env python3
"""
Integration Tests for Google Forms Processing
Tests the complete forms processing pipeline
"""

import os
import sys
import json
import time
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.form import (
    GoogleForm, FormQuestion, QuestionOption, QuestionType, 
    validate_google_forms_url, extract_form_id_from_url,
    estimate_form_complexity
)
from flexible_form_scraper import FlexibleFormScraper, FormQualityAssessment
from openai_form_processor import OpenAIFormProcessor
from integrated_form_scraper import IntegratedFormScraper

class TestFormModels(unittest.TestCase):
    """Test form data models"""
    
    def test_question_type_enum(self):
        """Test QuestionType enum values"""
        self.assertEqual(QuestionType.MULTIPLE_CHOICE.value, "multiple_choice")
        self.assertEqual(QuestionType.SHORT_ANSWER.value, "short_answer")
        self.assertEqual(QuestionType.PARAGRAPH.value, "paragraph")
    
    def test_google_forms_url_validation(self):
        """Test Google Forms URL validation"""
        valid_urls = [
            "https://docs.google.com/forms/d/1ABC123/viewform",
            "https://forms.gle/XYZ789",
            "https://forms.google.com/forms/d/1ABC123/viewform"
        ]
        
        invalid_urls = [
            "https://example.com/form",
            "https://google.com",
            "not-a-url",
            ""
        ]
        
        for url in valid_urls:
            self.assertTrue(validate_google_forms_url(url), f"Should be valid: {url}")
        
        for url in invalid_urls:
            self.assertFalse(validate_google_forms_url(url), f"Should be invalid: {url}")
    
    def test_form_id_extraction(self):
        """Test form ID extraction from URLs"""
        test_cases = [
            ("https://docs.google.com/forms/d/1ABC123DEF/viewform", "1ABC123DEF"),
            ("https://forms.gle/XYZ789", None),  # Short URLs don't contain extractable IDs
            ("https://docs.google.com/forms/d/e/1FAIpQLSf_example/viewform", "1FAIpQLSf_example"),
        ]
        
        for url, expected_id in test_cases:
            result = extract_form_id_from_url(url)
            if expected_id:
                self.assertEqual(result, expected_id, f"Failed to extract ID from {url}")
    
    def test_form_complexity_estimation(self):
        """Test form complexity estimation"""
        # Simple form
        simple_form = GoogleForm(
            url="https://example.com",
            questions=[
                FormQuestion("Name?", QuestionType.SHORT_ANSWER, 0),
                FormQuestion("Email?", QuestionType.EMAIL, 1)
            ]
        )
        self.assertEqual(estimate_form_complexity(simple_form), "simple")
        
        # Complex form
        complex_form = GoogleForm(
            url="https://example.com",
            questions=[
                FormQuestion(f"Question {i}", QuestionType.MULTIPLE_CHOICE, i, is_required=True)
                for i in range(20)
            ],
            sections=[{"title": f"Section {i}", "section_index": i} for i in range(5)]
        )
        self.assertEqual(estimate_form_complexity(complex_form), "complex")
    
    def test_form_serialization(self):
        """Test form object serialization"""
        question = FormQuestion(
            question_text="Test question",
            question_type=QuestionType.MULTIPLE_CHOICE,
            question_index=0,
            is_required=True,
            options=[
                QuestionOption("Option 1", 0),
                QuestionOption("Option 2", 1)
            ]
        )
        
        form = GoogleForm(
            url="https://example.com",
            title="Test Form",
            questions=[question]
        )
        
        # Test serialization
        form_dict = form.to_dict()
        self.assertIsInstance(form_dict, dict)
        self.assertEqual(form_dict['title'], "Test Form")
        self.assertEqual(len(form_dict['questions']), 1)
        self.assertEqual(form_dict['questions'][0]['question_text'], "Test question")

class TestFormQualityAssessment(unittest.TestCase):
    """Test form content quality assessment"""
    
    def test_quality_assessment_good_content(self):
        """Test quality assessment with good form content"""
        good_content = """
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
        
        Submit button
        """
        
        assessment = FormQualityAssessment.assess_content_quality(good_content, "https://example.com")
        
        self.assertEqual(assessment['quality'], 'good')
        self.assertGreater(assessment['score'], 0.7)
        self.assertGreater(len(assessment['indicators']), 0)
    
    def test_quality_assessment_poor_content(self):
        """Test quality assessment with poor content"""
        poor_content = "This is not a form"
        
        assessment = FormQualityAssessment.assess_content_quality(poor_content, "https://example.com")
        
        self.assertEqual(assessment['quality'], 'poor')
        self.assertLess(assessment['score'], 0.4)
    
    def test_quality_assessment_404_content(self):
        """Test quality assessment with 404 content"""
        error_content = "404 - Page not found. The form you're looking for doesn't exist."
        
        assessment = FormQualityAssessment.assess_content_quality(error_content, "https://example.com")
        
        self.assertEqual(assessment['quality'], '404')
        self.assertEqual(assessment['score'], 0.0)

class TestFormScraper(unittest.TestCase):
    """Test form scraper functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.api_key = "test-api-key"
    
    @patch('flexible_form_scraper.FirecrawlApp')
    def test_form_scraper_initialization(self, mock_firecrawl):
        """Test form scraper initialization"""
        scraper = FlexibleFormScraper(self.api_key)
        
        self.assertEqual(scraper.firecrawl_api_key, self.api_key)
        self.assertIsNotNone(scraper.app)
        mock_firecrawl.assert_called_once_with(api_key=self.api_key)
    
    @patch('flexible_form_scraper.FirecrawlApp')
    def test_form_scraper_invalid_url(self, mock_firecrawl):
        """Test form scraper with invalid URL"""
        scraper = FlexibleFormScraper(self.api_key)
        
        result = scraper.scrape_form("https://invalid-url.com")
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid Google Forms URL', result['error'])
    
    @patch('flexible_form_scraper.FirecrawlApp')
    def test_form_scraper_successful_scrape(self, mock_firecrawl):
        """Test successful form scraping"""
        # Mock Firecrawl response
        mock_app = Mock()
        mock_app.scrape_url.return_value = {
            'success': True,
            'markdown': 'Form content here with questions and form elements',
            'html': '<html>Form HTML</html>',
            'metadata': {
                'title': 'Test Form',
                'description': 'A test form',
                'statusCode': 200
            }
        }
        mock_firecrawl.return_value = mock_app
        
        scraper = FlexibleFormScraper(self.api_key)
        result = scraper.scrape_form("https://docs.google.com/forms/d/1ABC123/viewform")
        
        self.assertTrue(result['success'])
        self.assertIn('content', result)
        self.assertIn('quality_assessment', result)
        self.assertIn('processing_time_ms', result)

class TestOpenAIFormProcessor(unittest.TestCase):
    """Test OpenAI form processor"""
    
    def setUp(self):
        """Set up test environment"""
        self.api_key = "test-openai-key"
    
    @patch('openai_form_processor.openai')
    def test_processor_initialization(self, mock_openai):
        """Test processor initialization"""
        processor = OpenAIFormProcessor(self.api_key)
        
        self.assertEqual(processor.api_key, self.api_key)
        self.assertIsNotNone(processor.client)
    
    def test_processor_stats(self):
        """Test processor statistics"""
        processor = OpenAIFormProcessor(self.api_key)
        stats = processor.get_processor_stats()
        
        self.assertIn('processor_type', stats)
        self.assertIn('model_config', stats)
        self.assertIn('supported_question_types', stats)
        self.assertEqual(stats['processor_type'], 'OpenAIFormProcessor')

class TestIntegratedFormScraper(unittest.TestCase):
    """Test integrated form scraper"""
    
    def setUp(self):
        """Set up test environment"""
        self.firecrawl_key = "test-firecrawl-key"
        self.openai_key = "test-openai-key"
        self.mock_supabase = Mock()
    
    @patch('integrated_form_scraper.OpenAIFormProcessor')
    @patch('integrated_form_scraper.FlexibleFormScraper')
    def test_integrated_scraper_initialization(self, mock_form_scraper, mock_ai_processor):
        """Test integrated scraper initialization"""
        scraper = IntegratedFormScraper(
            self.firecrawl_key, 
            self.mock_supabase, 
            self.openai_key
        )
        
        self.assertEqual(scraper.firecrawl_api_key, self.firecrawl_key)
        self.assertEqual(scraper.openai_api_key, self.openai_key)
        self.assertEqual(scraper.supabase, self.mock_supabase)
        
        mock_form_scraper.assert_called_once_with(self.firecrawl_key)
        mock_ai_processor.assert_called_once_with(self.openai_key)
    
    def test_scraper_stats(self):
        """Test scraper statistics"""
        with patch('integrated_form_scraper.OpenAIFormProcessor'), \
             patch('integrated_form_scraper.FlexibleFormScraper'):
            
            scraper = IntegratedFormScraper(
                self.firecrawl_key, 
                self.mock_supabase, 
                self.openai_key
            )
            
            stats = scraper.get_scraper_stats()
            
            self.assertIn('scraper_type', stats)
            self.assertIn('configuration', stats)
            self.assertIn('components', stats)
            self.assertIn('capabilities', stats)
            self.assertEqual(stats['scraper_type'], 'IntegratedFormScraper')

def run_integration_tests():
    """Run all integration tests"""
    print("🧪 Running Google Forms Integration Tests...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestFormModels,
        TestFormQualityAssessment,
        TestFormScraper,
        TestOpenAIFormProcessor,
        TestIntegratedFormScraper
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n📊 Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback}")
    
    if result.errors:
        print(f"\n🚨 Errors:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    
    return success

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)

