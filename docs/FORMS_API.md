# 📋 Google Forms API Documentation

This document describes the Google Forms processing functionality that has been added to the AI-powered scraper API.

## 🎯 Overview

The Forms API allows you to:
- Extract questions and structure from Google Forms
- Store form data in Supabase with proper schema
- Use AI to intelligently process form content
- Track processing sessions with real-time progress
- Maintain the same production-ready quality and confidence scoring as the job scraper

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Firecrawl     │ -> │   OpenAI GPT-4   │ -> │    Supabase     │
│  Form Scraper   │    │  Form Processor  │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

1. **`FlexibleFormScraper`** - Firecrawl-powered form content extraction with quality assessment
2. **`OpenAIFormProcessor`** - GPT-4 intelligent form question extraction with confidence scoring  
3. **`IntegratedFormScraper`** - Orchestrates the complete pipeline
4. **`SupabaseIntegration`** - Handles database operations and session management for forms

## 📊 API Endpoints

### **Start Form Scraping**
```http
POST /api/forms/scrape
Content-Type: application/json

{
  "urls": [
    "https://docs.google.com/forms/d/1ABC123/viewform",
    "https://forms.gle/XYZ789"
  ],
  "user_id": "optional_user_id"
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "message": "Form scraping started successfully",
  "total_urls": 2,
  "estimated_time_minutes": 1.5,
  "status_endpoint": "/api/forms/status/uuid-here"
}
```

### **Get Session Status**
```http
GET /api/forms/status/{session_id}
```

**Response:**
```json
{
  "id": "uuid-here",
  "status": "processing",
  "progress_percentage": 75.0,
  "processed_urls": 3,
  "total_urls": 4,
  "successful_forms": 2,
  "failed_forms": 1,
  "summary": "2 successful, 1 failed",
  "started_at": "2024-01-01T12:00:00Z",
  "completed_at": null,
  "estimated_remaining_minutes": 0.8
}
```

### **Get Detailed Session Status**
```http
GET /api/forms/status/{session_id}/detailed
```

**Response:**
```json
{
  "session_info": {
    "id": "uuid-here",
    "status": "completed",
    "progress_percentage": 100.0,
    "summary": "3 successful, 1 failed"
  },
  "detailed_statistics": {
    "total_logs": 12,
    "logs_by_stage": {
      "scraping": 4,
      "ai_processing": 4,
      "data_storage": 3,
      "completed": 3
    },
    "logs_by_status": {
      "success": 10,
      "error": 2
    },
    "processing_times": [2500, 3200, 1800],
    "errors": [
      {
        "url": "https://...",
        "stage": "scraping",
        "message": "Form not accessible",
        "details": {}
      }
    ]
  }
}
```

### **Get Form Data**
```http
GET /api/forms/{form_id}
```

**Response:**
```json
{
  "form": {
    "id": "uuid-here",
    "url": "https://docs.google.com/forms/d/1ABC123/viewform",
    "title": "Customer Feedback Survey",
    "description": "Please share your feedback",
    "form_id": "1ABC123",
    "response_count": 45,
    "is_accepting_responses": true,
    "questions": [
      {
        "id": "q-uuid-1",
        "question_text": "What is your name?",
        "question_type": "short_answer",
        "question_index": 0,
        "is_required": true,
        "options": [],
        "validation_rules": [
          {
            "rule_type": "min_length",
            "value": 2,
            "error_message": "Name must be at least 2 characters"
          }
        ]
      },
      {
        "id": "q-uuid-2",
        "question_text": "How satisfied are you?",
        "question_type": "multiple_choice",
        "question_index": 1,
        "is_required": true,
        "options": [
          {
            "id": "opt-uuid-1",
            "option_text": "Very satisfied",
            "option_index": 0
          },
          {
            "id": "opt-uuid-2",
            "option_text": "Satisfied",
            "option_index": 1
          },
          {
            "id": "opt-uuid-3",
            "option_text": "Neutral",
            "option_index": 2
          }
        ]
      }
    ],
    "sections": [],
    "scraped_at": "2024-01-01T12:00:00Z"
  }
}
```

### **List Forms**
```http
GET /api/forms?limit=10&offset=0
```

**Response:**
```json
{
  "forms": [
    {
      "id": "uuid-1",
      "url": "https://...",
      "title": "Form Title",
      "scraped_at": "2024-01-01T12:00:00Z"
    }
  ],
  "limit": 10,
  "offset": 0,
  "returned_count": 5
}
```

### **Search Forms**
```http
GET /api/forms/search?q=feedback&limit=10
```

**Response:**
```json
{
  "forms": [
    {
      "id": "uuid-1",
      "url": "https://docs.google.com/forms/d/feedback123/viewform",
      "title": "Customer Feedback Survey"
    }
  ],
  "query": "feedback",
  "results_count": 1
}
```

### **Get Statistics**
```http
GET /api/forms/stats
```

**Response:**
```json
{
  "scraper_available": true,
  "database_available": true,
  "ai_processing_enabled": true,
  "total_forms": 150,
  "total_questions": 1250,
  "total_sessions": 25,
  "scraper_config": {
    "scraper_type": "IntegratedFormScraper",
    "configuration": {
      "min_quality_score": 0.3,
      "enable_ai_processing": true
    }
  }
}
```

### **Test Form Processing**
```http
POST /api/forms/test
Content-Type: application/json

{
  "url": "https://docs.google.com/forms/d/1ABC123/viewform"
}
```

**Response:**
```json
{
  "success": true,
  "url": "https://docs.google.com/forms/d/1ABC123/viewform",
  "form_data": {
    "title": "Test Form",
    "questions": [...]
  },
  "quality_assessment": {
    "quality": "good",
    "score": 0.85
  },
  "processing_time_ms": 3500
}
```

### **Health Check**
```http
GET /api/forms/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "components": {
    "integrated_scraper": true,
    "firecrawl_api": true,
    "openai_api": true,
    "supabase_db": true
  }
}
```

## 🗄️ Database Schema

### Forms Table
```sql
forms (
  id UUID PRIMARY KEY,
  url TEXT UNIQUE,
  title TEXT,
  description TEXT,
  form_id TEXT,
  owner_email TEXT,
  response_count INTEGER,
  is_accepting_responses BOOLEAN,
  requires_login BOOLEAN,
  allow_response_editing BOOLEAN,
  collect_email BOOLEAN,
  raw_data JSONB,
  scraped_at TIMESTAMP,
  last_updated TIMESTAMP
)
```

### Form Questions Table
```sql
form_questions (
  id UUID PRIMARY KEY,
  form_id UUID REFERENCES forms(id),
  question_index INTEGER,
  question_text TEXT,
  question_type TEXT,
  description TEXT,
  is_required BOOLEAN,
  has_other_option BOOLEAN,
  validation_rules JSONB,
  settings JSONB
)
```

### Question Options Table
```sql
question_options (
  id UUID PRIMARY KEY,
  question_id UUID REFERENCES form_questions(id),
  option_index INTEGER,
  option_text TEXT,
  is_other_option BOOLEAN
)
```

### Form Scrape Sessions Table
```sql
form_scrape_sessions (
  id UUID PRIMARY KEY,
  urls TEXT[],
  total_urls INTEGER,
  processed_urls INTEGER,
  successful_forms INTEGER,
  failed_forms INTEGER,
  status TEXT,
  progress_percentage DECIMAL,
  summary TEXT,
  error_details JSONB,
  user_id TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP
)
```

## 🔧 Configuration

### Environment Variables
```env
# Required for form scraping
FIRECRAWL_API_KEY=fc-your-firecrawl-key

# Required for AI processing
OPENAI_API_KEY=sk-your-openai-key

# Required for data storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Flask configuration
SECRET_KEY=your-super-secret-flask-key
FLASK_PORT=5005
FLASK_HOST=0.0.0.0
FLASK_DEBUG=True
```

### Supported Question Types
- `multiple_choice` - Single selection from options
- `checkboxes` - Multiple selections from options
- `dropdown` - Single selection from dropdown
- `short_answer` - Short text input
- `paragraph` - Long text input
- `linear_scale` - Rating scale (1-5, 1-10, etc.)
- `date` - Date picker
- `time` - Time picker
- `file_upload` - File upload field
- `email` - Email address input
- `url` - URL input
- `number` - Numeric input

## 📈 Quality Assessment

Forms are automatically assessed for quality:

- **Good** (0.7+): Complete form with clear questions and structure
- **Moderate** (0.4-0.7): Partial form data or some missing elements
- **Poor** (0.0-0.4): Minimal form data or unclear structure
- **Invalid**: Empty or corrupted content
- **404**: Form not accessible or deleted

## 🚀 Usage Examples

### Python Client Example
```python
import requests
import time

# Start form scraping
response = requests.post('http://localhost:5005/api/forms/scrape', json={
    'urls': [
        'https://docs.google.com/forms/d/1ABC123/viewform',
        'https://forms.gle/XYZ789'
    ],
    'user_id': 'user123'
})

session_id = response.json()['session_id']
print(f"Started scraping session: {session_id}")

# Poll for completion
while True:
    status_response = requests.get(f'http://localhost:5005/api/forms/status/{session_id}')
    status = status_response.json()
    
    print(f"Progress: {status['progress_percentage']:.1f}%")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(5)

print(f"Scraping completed: {status['summary']}")

# Get form data
if status['successful_forms'] > 0:
    forms_response = requests.get('http://localhost:5005/api/forms?limit=5')
    forms = forms_response.json()['forms']
    
    for form in forms:
        print(f"Form: {form['title']} - {len(form.get('questions', []))} questions")
```

### JavaScript/Node.js Example
```javascript
const axios = require('axios');

async function scrapeGoogleForms() {
    try {
        // Start scraping
        const scrapeResponse = await axios.post('http://localhost:5005/api/forms/scrape', {
            urls: [
                'https://docs.google.com/forms/d/1ABC123/viewform'
            ],
            user_id: 'user123'
        });
        
        const sessionId = scrapeResponse.data.session_id;
        console.log(`Started scraping session: ${sessionId}`);
        
        // Poll for completion
        let status;
        do {
            await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
            
            const statusResponse = await axios.get(`http://localhost:5005/api/forms/status/${sessionId}`);
            status = statusResponse.data;
            
            console.log(`Progress: ${status.progress_percentage.toFixed(1)}%`);
        } while (!['completed', 'failed'].includes(status.status));
        
        console.log(`Scraping completed: ${status.summary}`);
        
        // Get form data
        if (status.successful_forms > 0) {
            const formsResponse = await axios.get('http://localhost:5005/api/forms?limit=5');
            const forms = formsResponse.data.forms;
            
            forms.forEach(form => {
                console.log(`Form: ${form.title} - ${form.questions?.length || 0} questions`);
            });
        }
        
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

scrapeGoogleForms();
```

## 🐛 Error Handling

### Common Error Responses

**Invalid URL:**
```json
{
  "error": "Invalid URLs provided",
  "invalid_urls": ["Not a valid Google Forms URL: https://example.com"],
  "valid_urls_count": 0
}
```

**Service Unavailable:**
```json
{
  "error": "Form scraper not available. Please check API key configuration.",
  "details": "FIRECRAWL_API_KEY is required for form scraping"
}
```

**Session Not Found:**
```json
{
  "error": "Session not found"
}
```

**Rate Limiting:**
```json
{
  "error": "Too many URLs. Maximum allowed: 50",
  "provided_count": 75
}
```

## 🔍 Monitoring & Debugging

### Check Service Health
```bash
curl http://localhost:5005/api/forms/health
```

### View Processing Logs
```bash
# Get detailed session information
curl http://localhost:5005/api/forms/status/{session_id}/detailed
```

### Database Queries
```sql
-- Check recent forms
SELECT title, url, scraped_at, 
       (SELECT COUNT(*) FROM form_questions WHERE form_id = forms.id) as question_count
FROM forms 
ORDER BY scraped_at DESC 
LIMIT 10;

-- View session performance
SELECT status, summary, 
       EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds
FROM form_scrape_sessions 
ORDER BY started_at DESC 
LIMIT 10;

-- Find forms with most questions
SELECT f.title, f.url, COUNT(fq.id) as question_count
FROM forms f
LEFT JOIN form_questions fq ON f.id = fq.form_id
GROUP BY f.id, f.title, f.url
ORDER BY question_count DESC
LIMIT 10;
```

## 🚀 Deployment Considerations

### Production Settings
- Set `FLASK_DEBUG=False`
- Use environment variables for all secrets
- Configure proper logging levels
- Set up monitoring for API rate limits
- Consider Redis for session caching
- Implement request rate limiting

### Scaling Recommendations
- Use a queue system (Redis/Celery) for background processing
- Implement database connection pooling
- Add caching for frequently accessed forms
- Monitor OpenAI API usage and costs
- Set up alerts for failed processing sessions

---

**Built with ❤️ for flexible, AI-powered Google Forms processing**

