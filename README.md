# 🚀 AI-Powered Job Scraper API

A flexible, production-ready job scraper that uses **Firecrawl** for content extraction and **OpenAI GPT-4** for intelligent data processing. Unlike traditional scrapers with rigid schemas, this system adapts to any job posting format.

## ✨ Features

### 🤖 **AI-Powered Extraction**
- **Flexible Content Scraping**: Uses Firecrawl to extract readable content from any job site
- **OpenAI GPT-4 Processing**: Intelligently extracts structured data without rigid schemas
- **Dual Confidence Scoring**: AI self-assessment + objective validation (96% confidence achieved!)
- **Application Questions Capture**: Extracts application forms and requirements
- **Full Conversation Logging**: Complete OpenAI interaction transparency for debugging

### 🛡️ **Production-Ready Features**
- **Smart 404 Detection**: Avoids expensive AI processing on invalid content
- **Quality Assessment**: Categorizes content as good, poor, invalid, or 404
- **Cost Optimization**: Only processes high-quality content
- **Robust Error Handling**: Graceful failure with detailed logging
- **Session Tracking**: Real-time progress monitoring via Supabase

### 🗄️ **Data Management**
- **Supabase Integration**: Modern PostgreSQL cloud database
- **Complete Metadata Storage**: Raw content, AI responses, confidence scores
- **Session Management**: Track scraping sessions with progress and statistics
- **Comprehensive Logging**: Error tracking and performance monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Firecrawl     │ -> │   OpenAI GPT-4   │ -> │    Supabase     │
│  Content Scraper│    │  Data Extractor  │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

1. **`FlexibleJobScraper`** - Firecrawl-powered content extraction with quality assessment
2. **`OpenAIJobProcessor`** - GPT-4 intelligent data extraction with confidence scoring  
3. **`IntegratedFlexibleScraper`** - Orchestrates the complete pipeline
4. **`SupabaseIntegration`** - Handles database operations and session management

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- Firecrawl API Key ([get one here](https://firecrawl.dev))
- OpenAI API Key ([get one here](https://platform.openai.com))
- Supabase account ([get one here](https://supabase.com))

### 2. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd job-scraper-api

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file with your credentials:

```env
# Required API Keys
FIRECRAWL_API_KEY=fc-your-firecrawl-key
OPENAI_API_KEY=sk-your-openai-key

# Supabase Configuration  
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Flask Configuration
SECRET_KEY=your-super-secret-flask-key
FLASK_PORT=5005
FLASK_HOST=0.0.0.0
FLASK_DEBUG=True
```

### 4. Run the Application

```bash
python3 src/main.py
```

Visit `http://localhost:5005` to access the web interface.

## 📊 API Endpoints

### **Flexible AI Scraping** (Recommended)
```http
POST /api/scrape/flexible
Content-Type: application/json

{
  "urls": ["https://example-job-site.com/job/123"]
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "message": "Scraping started",
  "total_urls": 1
}
```

### **Session Status**
```http
GET /api/scrape/status/{session_id}
```

**Response:**
```json
{
  "id": "uuid-here",
  "status": "completed",
  "progress_percentage": 100,
  "scraped_jobs_count": 1,
  "summary": "1 good, 0 poor, 0 404 errors, 0 invalid"
}
```

### **Legacy Scraping** (Basic)
```http  
POST /api/scrape
Content-Type: application/json

{
  "urls": ["https://example-job-site.com/job/123"]
}
```

## 📈 Performance Results

### Real-World Testing Results:
- **Solana/Raydium Job**: 96% confidence score ✅
- **Content Quality**: 5,778 characters of rich job data
- **Application Questions**: Successfully captured
- **Processing Time**: ~30 seconds end-to-end
- **Token Usage**: 2,876 total tokens (cost-optimized)

### Confidence Scoring Breakdown:
- **AI Confidence**: 90% (GPT-4 self-assessment)
- **Validation Confidence**: 100% (objective data completeness)
- **Final Score**: 96% (weighted average with bonuses)

## 🔧 Configuration Options

### Confidence Scoring Weights
```python
# In openai_job_processor.py
CONFIDENCE_WEIGHTS = {
    'ai_weight': 0.4,      # AI self-assessment
    'validation_weight': 0.6  # Objective validation
}
```

### Quality Assessment Thresholds
```python
# In flexible_job_scraper.py  
QUALITY_THRESHOLDS = {
    'min_length': 500,     # Minimum content length
    'job_indicators': 2    # Required job-related keywords
}
```

### OpenAI Model Configuration
```python
# In openai_job_processor.py
MODEL_CONFIG = {
    'model': 'gpt-4o',
    'temperature': 0.1,    # Low for consistent extraction
    'max_tokens': 4000     # Response limit
}
```

## 💾 Database Schema

### Job Postings Table
```sql
job_postings (
  id UUID PRIMARY KEY,
  url TEXT UNIQUE,
  title TEXT,
  company TEXT,
  location TEXT,
  job_type TEXT,
  salary_range TEXT,
  experience_level TEXT,
  application_url TEXT,
  application_email TEXT,
  raw_data JSONB,        -- Complete AI extraction data
  scraped_at TIMESTAMP,
  last_updated TIMESTAMP
)
```

### Raw Data Structure (JSONB)
```json
{
  "ai_extracted": {
    "title": "Head of Marketing",
    "company": "Raydium", 
    "requirements": ["4+ years marketing experience", "..."],
    "responsibilities": ["Lead marketing strategy", "..."],
    "benefits": ["Competitive salary", "Token allocation"],
    "application_questions": ["Tell us why you're a good fit"],
    "confidence_score": 0.96,
    "ai_confidence": 0.90,
    "validation_confidence": 1.00
  },
  "openai_conversation": {
    "system_prompt": "You are an expert...",
    "user_prompt": "Extract job data from...",
    "response": "...",
    "usage": {
      "prompt_tokens": 2100,
      "completion_tokens": 776,
      "total_tokens": 2876
    }
  },
  "scraped_content": "Full markdown content...",
  "content_quality": "good"
}
```

## 🐛 Troubleshooting

### Common Issues

**1. "Address already in use" Error**
```bash
# Use a different port
FLASK_PORT=5006 python3 src/main.py
```

**2. Missing API Keys**
- Ensure all required keys are in `.env`
- Check key format (Firecrawl: `fc-...`, OpenAI: `sk-...`)

**3. Import Errors**
```bash
# Ensure you're in the project root
pwd  # Should show .../job-scraper-api
python3 src/main.py
```

**4. Low Confidence Scores**
- Check content quality in scrape logs
- Verify job posting is still active (not 404)
- Review OpenAI conversation logs for debugging

## 🔍 Monitoring & Debugging

### View Recent Sessions
```bash
# Check latest scraping sessions
curl http://localhost:5005/api/scrape/status/recent
```

### Database Debugging
Use Supabase dashboard or direct SQL:
```sql
-- Check recent job postings
SELECT title, company, raw_data->'ai_extracted'->'confidence_score' 
FROM job_postings 
ORDER BY scraped_at DESC LIMIT 5;

-- View session performance
SELECT status, summary, completed_at-started_at as duration 
FROM scrape_sessions 
ORDER BY created_at DESC LIMIT 10;
```

## 🚀 Deployment

### Production Considerations
- Use environment variables for all secrets
- Set `FLASK_DEBUG=False` in production
- Configure proper logging levels
- Set up monitoring for API rate limits
- Consider Redis for session caching

### Recommended Stack
- **Server**: Ubuntu 22.04+ (4GB+ RAM)
- **Process Manager**: PM2 or Gunicorn
- **Reverse Proxy**: Nginx
- **SSL**: Let's Encrypt
- **Monitoring**: Prometheus + Grafana

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly
4. Update documentation as needed
5. Submit a pull request

## 📜 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Firecrawl** - Excellent web scraping API
- **OpenAI** - Powerful AI model for data extraction  
- **Supabase** - Modern database platform
- **Flask** - Lightweight web framework

---

**Built with ❤️ for flexible, AI-powered job scraping** 