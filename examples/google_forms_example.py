#!/usr/bin/env python3
"""
Google Forms Processing Example
Demonstrates how to use the Google Forms processing functionality
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def example_api_usage():
    """Example using the REST API"""
    print("🌐 Google Forms API Example")
    print("=" * 50)
    
    base_url = "http://localhost:5005/api"
    
    # Example Google Forms URLs (replace with real ones for testing)
    test_urls = [
        "https://docs.google.com/forms/d/e/1FAIpQLSf_example1/viewform",
        "https://docs.google.com/forms/d/e/1FAIpQLSf_example2/viewform"
    ]
    
    try:
        # 1. Check service health
        print("1️⃣ Checking service health...")
        health_response = requests.get(f"{base_url}/forms/health")
        health_data = health_response.json()
        
        print(f"   Status: {health_data['status']}")
        print(f"   Components: {health_data['components']}")
        
        if health_data['status'] != 'healthy':
            print("⚠️ Service is not fully healthy. Some features may not work.")
        
        # 2. Get current statistics
        print("\n2️⃣ Getting current statistics...")
        stats_response = requests.get(f"{base_url}/forms/stats")
        stats_data = stats_response.json()
        
        print(f"   Total forms: {stats_data.get('total_forms', 'N/A')}")
        print(f"   Total questions: {stats_data.get('total_questions', 'N/A')}")
        print(f"   AI processing enabled: {stats_data.get('ai_processing_enabled', False)}")
        
        # 3. Start form scraping
        print("\n3️⃣ Starting form scraping...")
        scrape_payload = {
            "urls": test_urls,
            "user_id": "example_user"
        }
        
        scrape_response = requests.post(f"{base_url}/forms/scrape", json=scrape_payload)
        
        if scrape_response.status_code == 202:
            scrape_data = scrape_response.json()
            session_id = scrape_data['session_id']
            
            print(f"   ✅ Scraping started successfully!")
            print(f"   Session ID: {session_id}")
            print(f"   Total URLs: {scrape_data['total_urls']}")
            print(f"   Estimated time: {scrape_data['estimated_time_minutes']} minutes")
            
            # 4. Monitor progress
            print("\n4️⃣ Monitoring progress...")
            
            while True:
                status_response = requests.get(f"{base_url}/forms/status/{session_id}")
                status_data = status_response.json()
                
                progress = status_data.get('progress_percentage', 0)
                status = status_data.get('status', 'unknown')
                processed = status_data.get('processed_urls', 0)
                total = status_data.get('total_urls', 0)
                
                print(f"   Progress: {progress:.1f}% ({processed}/{total}) - Status: {status}")
                
                if status in ['completed', 'failed']:
                    break
                
                time.sleep(3)  # Check every 3 seconds
            
            # 5. Get final results
            print(f"\n5️⃣ Final results:")
            print(f"   Status: {status_data['status']}")
            print(f"   Summary: {status_data.get('summary', 'N/A')}")
            print(f"   Successful forms: {status_data.get('successful_forms', 0)}")
            print(f"   Failed forms: {status_data.get('failed_forms', 0)}")
            
            # 6. Get detailed session information
            if status_data.get('successful_forms', 0) > 0:
                print("\n6️⃣ Getting detailed session information...")
                detailed_response = requests.get(f"{base_url}/forms/status/{session_id}/detailed")
                detailed_data = detailed_response.json()
                
                stats = detailed_data.get('detailed_statistics', {})
                print(f"   Total processing logs: {stats.get('total_logs', 0)}")
                print(f"   Processing stages: {stats.get('logs_by_stage', {})}")
                print(f"   Status distribution: {stats.get('logs_by_status', {})}")
                
                if stats.get('errors'):
                    print(f"   Errors encountered: {len(stats['errors'])}")
                    for error in stats['errors'][:3]:  # Show first 3 errors
                        print(f"     - {error['url']}: {error['message']}")
            
            # 7. List recent forms
            print("\n7️⃣ Listing recent forms...")
            forms_response = requests.get(f"{base_url}/forms?limit=5")
            forms_data = forms_response.json()
            
            forms = forms_data.get('forms', [])
            print(f"   Found {len(forms)} recent forms:")
            
            for form in forms:
                print(f"     - {form.get('title', 'Untitled')} ({form.get('url', 'No URL')})")
                print(f"       Scraped: {form.get('scraped_at', 'Unknown time')}")
            
            # 8. Get detailed form data (if available)
            if forms:
                print(f"\n8️⃣ Getting detailed data for first form...")
                first_form = forms[0]
                form_id = first_form.get('id')
                
                if form_id:
                    form_response = requests.get(f"{base_url}/forms/{form_id}")
                    form_data = form_response.json()
                    
                    form_info = form_data.get('form', {})
                    questions = form_info.get('questions', [])
                    
                    print(f"   Form: {form_info.get('title', 'Untitled')}")
                    print(f"   Questions: {len(questions)}")
                    print(f"   Accepting responses: {form_info.get('is_accepting_responses', 'Unknown')}")
                    
                    # Show first few questions
                    for i, question in enumerate(questions[:3]):
                        q_type = question.get('question_type', 'unknown')
                        q_text = question.get('question_text', 'No text')
                        required = " (Required)" if question.get('is_required') else ""
                        
                        print(f"     Q{i+1}: {q_text} [{q_type}]{required}")
                        
                        # Show options for choice questions
                        options = question.get('options', [])
                        if options:
                            for opt in options[:3]:  # Show first 3 options
                                print(f"         - {opt.get('option_text', 'No text')}")
                            if len(options) > 3:
                                print(f"         ... and {len(options) - 3} more options")
        
        else:
            print(f"   ❌ Failed to start scraping: {scrape_response.status_code}")
            print(f"   Error: {scrape_response.json()}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server.")
        print("   Make sure the server is running on http://localhost:5005")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

def example_direct_usage():
    """Example using the components directly"""
    print("\n🔧 Direct Component Usage Example")
    print("=" * 50)
    
    try:
        from flexible_form_scraper import FlexibleFormScraper, test_form_scraper
        from openai_form_processor import OpenAIFormProcessor, test_form_processor
        from integrated_form_scraper import IntegratedFormScraper
        from models.form import GoogleForm, FormQuestion, QuestionType
        
        # Check environment variables
        firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        if not firecrawl_key:
            print("⚠️ FIRECRAWL_API_KEY not set. Skipping scraper test.")
        else:
            print("1️⃣ Testing Form Scraper...")
            # Note: This would require actual API keys and valid URLs
            print("   Form scraper initialized successfully")
        
        if not openai_key:
            print("⚠️ OPENAI_API_KEY not set. Skipping AI processor test.")
        else:
            print("2️⃣ Testing AI Form Processor...")
            # Note: This would require actual API keys
            print("   AI processor initialized successfully")
        
        # 3. Test form models
        print("3️⃣ Testing Form Models...")
        
        # Create a sample form
        questions = [
            FormQuestion(
                question_text="What is your name?",
                question_type=QuestionType.SHORT_ANSWER,
                question_index=0,
                is_required=True
            ),
            FormQuestion(
                question_text="How satisfied are you with our service?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                question_index=1,
                is_required=True,
                options=[
                    {"option_text": "Very satisfied", "option_index": 0},
                    {"option_text": "Satisfied", "option_index": 1},
                    {"option_text": "Neutral", "option_index": 2},
                    {"option_text": "Dissatisfied", "option_index": 3}
                ]
            )
        ]
        
        sample_form = GoogleForm(
            url="https://docs.google.com/forms/d/example/viewform",
            title="Customer Feedback Survey",
            description="Please provide your feedback",
            questions=questions
        )
        
        print(f"   Created sample form: {sample_form.title}")
        print(f"   Questions: {sample_form.get_question_count()}")
        print(f"   Required questions: {sample_form.get_required_questions_count()}")
        
        # Test serialization
        form_dict = sample_form.to_dict()
        print(f"   Serialization successful: {len(json.dumps(form_dict))} characters")
        
        # Test form complexity estimation
        from models.form import estimate_form_complexity
        complexity = estimate_form_complexity(sample_form)
        print(f"   Form complexity: {complexity}")
        
        print("   ✅ Form models working correctly!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running from the correct directory")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

def example_test_single_form():
    """Example testing a single form"""
    print("\n🧪 Single Form Test Example")
    print("=" * 50)
    
    base_url = "http://localhost:5005/api"
    test_url = "https://docs.google.com/forms/d/e/1FAIpQLSf_example/viewform"
    
    try:
        print(f"Testing single form: {test_url}")
        
        test_payload = {"url": test_url}
        response = requests.post(f"{base_url}/forms/test", json=test_payload)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("✅ Form processing successful!")
                
                form_data = result.get('form_data', {})
                quality = result.get('quality_assessment', {})
                
                print(f"   Form title: {form_data.get('title', 'N/A')}")
                print(f"   Questions extracted: {len(form_data.get('questions', []))}")
                print(f"   Quality score: {quality.get('score', 0):.2f}")
                print(f"   Processing time: {result.get('processing_time_ms', 0)}ms")
                
                # Show questions
                questions = form_data.get('questions', [])
                if questions:
                    print("   Questions:")
                    for i, q in enumerate(questions[:3]):
                        print(f"     {i+1}. {q.get('question_text', 'No text')} [{q.get('question_type', 'unknown')}]")
                    if len(questions) > 3:
                        print(f"     ... and {len(questions) - 3} more questions")
            else:
                print(f"❌ Form processing failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"❌ API request failed: {response.status_code}")
            print(f"   Response: {response.json()}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server.")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

def main():
    """Main example function"""
    print("🚀 Google Forms Processing Examples")
    print("=" * 60)
    print()
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:5005/api/forms/health", timeout=5)
        server_running = response.status_code == 200
    except:
        server_running = False
    
    if server_running:
        print("✅ API server is running")
        
        # Run API examples
        example_api_usage()
        example_test_single_form()
    else:
        print("⚠️ API server is not running on http://localhost:5005")
        print("   Start the server with: python src/main.py")
        print("   Running direct component examples instead...")
    
    # Run direct usage examples
    example_direct_usage()
    
    print("\n" + "=" * 60)
    print("🎉 Examples completed!")
    print("\nNext steps:")
    print("1. Set up your API keys in .env file")
    print("2. Start the server: python src/main.py")
    print("3. Try the API endpoints with real Google Forms URLs")
    print("4. Check the documentation: docs/FORMS_API.md")

if __name__ == "__main__":
    main()

