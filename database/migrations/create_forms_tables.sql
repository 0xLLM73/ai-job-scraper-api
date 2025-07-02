-- Google Forms Database Schema
-- This schema supports storing Google Forms questions, options, and metadata

-- Forms table - stores basic form information
CREATE TABLE IF NOT EXISTS forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    form_id TEXT, -- Google Form ID extracted from URL
    owner_email TEXT,
    response_count INTEGER DEFAULT 0,
    is_accepting_responses BOOLEAN DEFAULT true,
    requires_login BOOLEAN DEFAULT false,
    allow_response_editing BOOLEAN DEFAULT false,
    collect_email BOOLEAN DEFAULT false,
    raw_data JSONB, -- Complete AI extraction data
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Questions table - stores individual form questions
CREATE TABLE IF NOT EXISTS form_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES forms(id) ON DELETE CASCADE,
    question_index INTEGER NOT NULL, -- Order in the form
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL, -- 'multiple_choice', 'short_answer', 'paragraph', 'checkboxes', 'dropdown', 'linear_scale', 'date', 'time', 'file_upload'
    description TEXT,
    is_required BOOLEAN DEFAULT false,
    has_other_option BOOLEAN DEFAULT false,
    validation_rules JSONB, -- Validation settings (min/max length, regex, etc.)
    settings JSONB, -- Question-specific settings (scale range, file types, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(form_id, question_index)
);

-- Question options table - stores options for multiple choice, checkboxes, dropdown questions
CREATE TABLE IF NOT EXISTS question_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID REFERENCES form_questions(id) ON DELETE CASCADE,
    option_index INTEGER NOT NULL, -- Order of the option
    option_text TEXT NOT NULL,
    is_other_option BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(question_id, option_index)
);

-- Form sections table - for forms with multiple sections
CREATE TABLE IF NOT EXISTS form_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES forms(id) ON DELETE CASCADE,
    section_index INTEGER NOT NULL,
    title TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(form_id, section_index)
);

-- Form scraping sessions table - tracks scraping progress
CREATE TABLE IF NOT EXISTS form_scrape_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    urls TEXT[] NOT NULL,
    total_urls INTEGER NOT NULL,
    processed_urls INTEGER DEFAULT 0,
    successful_forms INTEGER DEFAULT 0,
    failed_forms INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,
    summary TEXT,
    error_details JSONB,
    user_id TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Form processing logs table - detailed logging for debugging
CREATE TABLE IF NOT EXISTS form_processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES form_scrape_sessions(id) ON DELETE CASCADE,
    form_id UUID REFERENCES forms(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    processing_stage TEXT NOT NULL, -- 'scraping', 'ai_processing', 'data_storage', 'completed', 'failed'
    status TEXT NOT NULL, -- 'success', 'warning', 'error'
    message TEXT,
    details JSONB,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_forms_url ON forms(url);
CREATE INDEX IF NOT EXISTS idx_forms_form_id ON forms(form_id);
CREATE INDEX IF NOT EXISTS idx_forms_scraped_at ON forms(scraped_at);
CREATE INDEX IF NOT EXISTS idx_form_questions_form_id ON form_questions(form_id);
CREATE INDEX IF NOT EXISTS idx_form_questions_type ON form_questions(question_type);
CREATE INDEX IF NOT EXISTS idx_question_options_question_id ON question_options(question_id);
CREATE INDEX IF NOT EXISTS idx_form_scrape_sessions_status ON form_scrape_sessions(status);
CREATE INDEX IF NOT EXISTS idx_form_scrape_sessions_created_at ON form_scrape_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_form_processing_logs_session_id ON form_processing_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_form_processing_logs_status ON form_processing_logs(status);

-- Views for common queries
CREATE OR REPLACE VIEW form_summary AS
SELECT 
    f.id,
    f.url,
    f.title,
    f.description,
    f.response_count,
    f.is_accepting_responses,
    COUNT(fq.id) as question_count,
    f.scraped_at,
    f.last_updated
FROM forms f
LEFT JOIN form_questions fq ON f.id = fq.form_id
GROUP BY f.id, f.url, f.title, f.description, f.response_count, f.is_accepting_responses, f.scraped_at, f.last_updated;

CREATE OR REPLACE VIEW session_progress AS
SELECT 
    s.id,
    s.status,
    s.progress_percentage,
    s.total_urls,
    s.processed_urls,
    s.successful_forms,
    s.failed_forms,
    s.summary,
    s.started_at,
    s.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(s.completed_at, NOW()) - s.started_at)) as duration_seconds
FROM form_scrape_sessions s;

-- Function to update form last_updated timestamp
CREATE OR REPLACE FUNCTION update_form_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE forms SET last_updated = NOW() WHERE id = NEW.form_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update timestamps
CREATE TRIGGER update_form_on_question_change
    AFTER INSERT OR UPDATE OR DELETE ON form_questions
    FOR EACH ROW EXECUTE FUNCTION update_form_timestamp();

CREATE TRIGGER update_form_on_option_change
    AFTER INSERT OR UPDATE OR DELETE ON question_options
    FOR EACH ROW EXECUTE FUNCTION update_form_timestamp();

