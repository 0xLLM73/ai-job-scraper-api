// Job Scraper Frontend Application
class JobScraperApp {
    constructor() {
        this.apiBase = '/api';
        this.currentJobs = [];
        this.currentSession = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadConfiguration();
        this.loadJobs();
    }

    bindEvents() {
        // Scraping buttons
        document.getElementById('scrape-flexible-btn').addEventListener('click', () => this.startFlexibleScraping());
        document.getElementById('scrape-btn').addEventListener('click', () => this.startScraping());
        document.getElementById('demo-scrape-btn').addEventListener('click', () => this.demoScrape());
        
        // Modal events
        document.getElementById('close-modal').addEventListener('click', () => this.closeJobModal());
        document.getElementById('job-modal').addEventListener('click', (e) => {
            if (e.target.id === 'job-modal') this.closeJobModal();
        });
        
        // Config modal events
        document.getElementById('config-btn').addEventListener('click', () => this.openConfigModal());
        document.getElementById('close-config-modal').addEventListener('click', () => this.closeConfigModal());
        document.getElementById('config-modal').addEventListener('click', (e) => {
            if (e.target.id === 'config-modal') this.closeConfigModal();
        });
        
        // Search and refresh
        document.getElementById('search-input').addEventListener('input', (e) => this.searchJobs(e.target.value));
        document.getElementById('refresh-btn').addEventListener('click', () => this.loadJobs());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeJobModal();
                this.closeConfigModal();
            }
        });
    }

    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            this.showNotification('API call failed: ' + error.message, 'error');
            throw error;
        }
    }

    async loadConfiguration() {
        try {
            const config = await this.apiCall('/config');
            this.updateStatusIndicator(config);
        } catch (error) {
            console.error('Failed to load configuration:', error);
        }
    }

    updateStatusIndicator(config) {
        const indicator = document.getElementById('status-indicator');
        
        if (config.firecrawl_configured && config.supabase_configured && config.supabase_connected) {
            indicator.textContent = 'Ready';
            indicator.className = 'px-3 py-1 rounded-full text-sm bg-green-500';
        } else if (config.firecrawl_configured) {
            indicator.textContent = 'Demo Mode';
            indicator.className = 'px-3 py-1 rounded-full text-sm bg-yellow-500';
        } else {
            indicator.textContent = 'Not Configured';
            indicator.className = 'px-3 py-1 rounded-full text-sm bg-red-500';
        }
    }

    async startFlexibleScraping() {
        const urls = this.getJobUrls();
        if (urls.length === 0) {
            this.showNotification('Please enter at least one job URL', 'warning');
            return;
        }

        try {
            const response = await this.apiCall('/scrape/flexible', {
                method: 'POST',
                body: JSON.stringify({ urls })
            });

            this.currentSession = response.session_id;
            this.showProgressSection();
            this.monitorScrapingProgress();
            this.showNotification(`Started AI-powered flexible scraping of ${urls.length} job postings`, 'success');
        } catch (error) {
            this.showNotification('Failed to start AI scraping', 'error');
        }
    }

    async startScraping() {
        const urls = this.getJobUrls();
        if (urls.length === 0) {
            this.showNotification('Please enter at least one job URL', 'warning');
            return;
        }

        try {
            const response = await this.apiCall('/scrape', {
                method: 'POST',
                body: JSON.stringify({ urls })
            });

            this.currentSession = response.session_id;
            this.showProgressSection();
            this.monitorScrapingProgress();
            this.showNotification(`Started legacy scraping of ${urls.length} job postings`, 'success');
        } catch (error) {
            this.showNotification('Failed to start scraping', 'error');
        }
    }

    async demoScrape() {
        const urls = this.getJobUrls();
        if (urls.length === 0) {
            this.showNotification('Please enter at least one job URL', 'warning');
            return;
        }

        this.showLoading('Scraping jobs...');

        try {
            const response = await this.apiCall('/demo/scrape', {
                method: 'POST',
                body: JSON.stringify({ urls })
            });

            this.hideLoading();
            this.displayDemoResults(response.results);
            this.showNotification(`Successfully scraped ${response.count} jobs`, 'success');
        } catch (error) {
            this.hideLoading();
            this.showNotification('Demo scraping failed', 'error');
        }
    }

    getJobUrls() {
        const textarea = document.getElementById('job-urls');
        return textarea.value
            .split('\n')
            .map(url => url.trim())
            .filter(url => url.length > 0);
    }

    showProgressSection() {
        document.getElementById('progress-section').classList.remove('hidden');
    }

    hideProgressSection() {
        document.getElementById('progress-section').classList.add('hidden');
    }

    async monitorScrapingProgress() {
        if (!this.currentSession) return;

        const checkProgress = async () => {
            try {
                const status = await this.apiCall(`/scrape/status/${this.currentSession}`);
                this.updateProgress(status);

                if (status.status === 'running') {
                    setTimeout(checkProgress, 2000); // Check every 2 seconds
                } else {
                    this.hideProgressSection();
                    if (status.status === 'completed') {
                        this.loadJobs(); // Refresh jobs list
                        this.showNotification('Scraping completed successfully', 'success');
                    } else {
                        this.showNotification('Scraping failed', 'error');
                    }
                }
            } catch (error) {
                console.error('Failed to check progress:', error);
                this.hideProgressSection();
            }
        };

        checkProgress();
    }

    updateProgress(status) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressDetails = document.getElementById('progress-details');

        const percentage = status.total_urls > 0 ? (status.completed / status.total_urls) * 100 : 0;
        
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${status.completed}/${status.total_urls}`;
        progressDetails.textContent = `Success: ${status.success_count}, Errors: ${status.error_count}`;
    }

    async loadJobs() {
        try {
            const response = await this.apiCall('/jobs?limit=50');
            this.currentJobs = response.jobs;
            this.displayJobs(this.currentJobs);
        } catch (error) {
            console.error('Failed to load jobs:', error);
            this.displayJobs([]);
        }
    }

    displayJobs(jobs) {
        const grid = document.getElementById('jobs-grid');
        const emptyState = document.getElementById('empty-state');

        if (jobs.length === 0) {
            grid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        grid.innerHTML = jobs.map(job => this.createJobCard(job)).join('');
    }

    displayDemoResults(results) {
        const demoJobs = results.map(result => result.job_posting);
        this.displayJobs(demoJobs);
    }

    createJobCard(job) {
        const salary = this.formatSalary(job);
        const location = job.location || 'Remote';
        const company = job.company_name || 'Unknown Company';
        const title = job.job_title || 'Untitled Position';

        return `
            <div class="job-card bg-white border border-gray-200 rounded-lg p-6 cursor-pointer" onclick="app.openJobModal('${job.id}')">
                <div class="flex items-start justify-between mb-4">
                    <div class="flex-1">
                        <h3 class="text-lg font-semibold text-gray-900 mb-1">${this.escapeHtml(title)}</h3>
                        <p class="text-blue-600 font-medium">${this.escapeHtml(company)}</p>
                    </div>
                    ${job.company_logo_url ? `<img src="${job.company_logo_url}" alt="${company} logo" class="w-12 h-12 rounded-lg object-contain">` : ''}
                </div>
                
                <div class="space-y-2 mb-4">
                    <div class="flex items-center text-sm text-gray-600">
                        <i class="fas fa-map-marker-alt mr-2"></i>
                        ${this.escapeHtml(location)}
                    </div>
                    ${salary ? `
                        <div class="flex items-center text-sm text-gray-600">
                            <i class="fas fa-dollar-sign mr-2"></i>
                            ${this.escapeHtml(salary)}
                        </div>
                    ` : ''}
                    <div class="flex items-center text-sm text-gray-600">
                        <i class="fas fa-building mr-2"></i>
                        ${this.escapeHtml(job.employment_type || 'Full-time')}
                    </div>
                </div>
                
                <div class="flex items-center justify-between">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        ${this.escapeHtml(job.ats_platform || 'Unknown ATS')}
                    </span>
                    <span class="text-xs text-gray-500">
                        ${this.formatDate(job.scraped_at)}
                    </span>
                </div>
            </div>
        `;
    }

    async openJobModal(jobId) {
        try {
            this.showLoading('Loading job details...');
            const jobData = await this.apiCall(`/jobs/${jobId}`);
            this.hideLoading();
            
            this.displayJobModal(jobData);
            this.logInteraction(jobId, 'view');
        } catch (error) {
            this.hideLoading();
            this.showNotification('Failed to load job details', 'error');
        }
    }

    displayJobModal(jobData) {
        const modal = document.getElementById('job-modal');
        const title = document.getElementById('modal-title');
        const content = document.getElementById('modal-content');

        const job = jobData.job_posting;
        const form = jobData.application_form;
        const fields = jobData.form_fields;
        const questions = jobData.competency_questions;

        title.textContent = job.job_title;

        content.innerHTML = `
            <div class="space-y-6">
                <!-- Job Header -->
                <div class="border-b pb-6">
                    <div class="flex items-start justify-between mb-4">
                        <div>
                            <h2 class="text-2xl font-bold text-gray-900">${this.escapeHtml(job.job_title)}</h2>
                            <p class="text-xl text-blue-600 font-medium">${this.escapeHtml(job.company_name)}</p>
                        </div>
                        ${job.company_logo_url ? `<img src="${job.company_logo_url}" alt="${job.company_name} logo" class="w-16 h-16 rounded-lg object-contain">` : ''}
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                        <div class="flex items-center">
                            <i class="fas fa-map-marker-alt mr-2 text-gray-400"></i>
                            ${this.escapeHtml(job.location || 'Remote')}
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-briefcase mr-2 text-gray-400"></i>
                            ${this.escapeHtml(job.employment_type || 'Full-time')}
                        </div>
                        <div class="flex items-center">
                            <i class="fas fa-dollar-sign mr-2 text-gray-400"></i>
                            ${this.escapeHtml(this.formatSalary(job) || 'Not specified')}
                        </div>
                    </div>
                </div>

                <!-- Job Description -->
                <div>
                    <h3 class="text-lg font-semibold mb-3">Job Description</h3>
                    <div class="prose max-w-none">
                        ${job.job_description ? `<p class="text-gray-700">${this.escapeHtml(job.job_description)}</p>` : '<p class="text-gray-500">No description available</p>'}
                    </div>
                </div>

                <!-- Responsibilities -->
                ${job.responsibilities && job.responsibilities.length > 0 ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-3">Responsibilities</h3>
                        <ul class="list-disc list-inside space-y-1 text-gray-700">
                            ${job.responsibilities.map(resp => `<li>${this.escapeHtml(resp)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                <!-- Qualifications -->
                ${job.qualifications && job.qualifications.length > 0 ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-3">Qualifications</h3>
                        <ul class="list-disc list-inside space-y-1 text-gray-700">
                            ${job.qualifications.map(qual => `<li>${this.escapeHtml(qual)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                <!-- Application Form Structure -->
                ${form ? `
                    <div class="border-t pt-6">
                        <h3 class="text-lg font-semibold mb-3">Application Form Structure</h3>
                        <div class="bg-gray-50 rounded-lg p-4 mb-4">
                            <div class="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <span class="font-medium">Form URL:</span>
                                    <a href="${form.form_url}" target="_blank" class="text-blue-600 hover:underline ml-2">
                                        Open Application <i class="fas fa-external-link-alt"></i>
                                    </a>
                                </div>
                                <div>
                                    <span class="font-medium">Has CAPTCHA:</span>
                                    <span class="ml-2">${form.has_captcha ? 'Yes' : 'No'}</span>
                                </div>
                                <div>
                                    <span class="font-medium">Autofill Available:</span>
                                    <span class="ml-2">${form.autofill_available ? 'Yes' : 'No'}</span>
                                </div>
                                <div>
                                    <span class="font-medium">Total Fields:</span>
                                    <span class="ml-2">${fields.length}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Form Fields -->
                        ${fields.length > 0 ? `
                            <div class="mb-4">
                                <h4 class="font-medium mb-2">Form Fields:</h4>
                                <div class="space-y-2">
                                    ${fields.map(field => `
                                        <div class="flex items-center justify-between p-2 bg-white rounded border">
                                            <div>
                                                <span class="font-medium">${this.escapeHtml(field.field_label || field.field_name)}</span>
                                                <span class="text-sm text-gray-500 ml-2">(${field.field_type})</span>
                                                ${field.is_required ? '<span class="text-red-500 ml-1">*</span>' : ''}
                                            </div>
                                            ${field.help_text ? `<span class="text-xs text-gray-400">${this.escapeHtml(field.help_text)}</span>` : ''}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        <!-- Competency Questions -->
                        ${questions.length > 0 ? `
                            <div>
                                <h4 class="font-medium mb-2">Competency Questions:</h4>
                                <div class="space-y-3">
                                    ${questions.map((q, index) => `
                                        <div class="p-3 bg-white rounded border">
                                            <div class="flex items-start justify-between">
                                                <span class="font-medium text-sm">${index + 1}. ${this.escapeHtml(q.question_text)}</span>
                                                ${q.is_required ? '<span class="text-red-500 ml-1">*</span>' : ''}
                                            </div>
                                            <div class="text-xs text-gray-500 mt-1">
                                                Type: ${q.question_type}
                                                ${q.word_limit ? ` | Word limit: ${q.word_limit}` : ''}
                                                ${q.character_limit ? ` | Character limit: ${q.character_limit}` : ''}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}

                <!-- Actions -->
                <div class="border-t pt-6 flex space-x-4">
                    <a href="${job.application_url || job.url}" target="_blank" 
                       class="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors flex items-center"
                       onclick="app.logInteraction('${job.id}', 'apply')">
                        <i class="fas fa-external-link-alt mr-2"></i>
                        Apply Now
                    </a>
                    <button onclick="app.logInteraction('${job.id}', 'save')" 
                            class="bg-gray-500 hover:bg-gray-600 text-white px-6 py-2 rounded-lg transition-colors flex items-center">
                        <i class="fas fa-bookmark mr-2"></i>
                        Save Job
                    </button>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
        modal.classList.add('modal-enter');
        setTimeout(() => modal.classList.remove('modal-enter'), 10);
    }

    closeJobModal() {
        const modal = document.getElementById('job-modal');
        modal.classList.add('modal-leave');
        setTimeout(() => {
            modal.classList.add('hidden');
            modal.classList.remove('modal-leave');
        }, 250);
    }

    async openConfigModal() {
        try {
            const config = await this.apiCall('/config');
            this.displayConfigModal(config);
        } catch (error) {
            this.showNotification('Failed to load configuration', 'error');
        }
    }

    displayConfigModal(config) {
        const modal = document.getElementById('config-modal');
        const status = document.getElementById('config-status');

        status.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <span class="font-medium">Firecrawl API</span>
                    <span class="px-2 py-1 rounded text-sm ${config.firecrawl_configured ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${config.firecrawl_configured ? 'Configured' : 'Not Configured'}
                    </span>
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <span class="font-medium">Supabase Database</span>
                    <span class="px-2 py-1 rounded text-sm ${config.supabase_configured ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${config.supabase_configured ? 'Configured' : 'Not Configured'}
                    </span>
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <span class="font-medium">Database Connection</span>
                    <span class="px-2 py-1 rounded text-sm ${config.supabase_connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${config.supabase_connected ? 'Connected' : 'Disconnected'}
                    </span>
                </div>
            </div>
            
            <div class="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 class="font-medium text-blue-900 mb-2">Configuration Notes:</h4>
                <ul class="text-sm text-blue-800 space-y-1">
                    <li>• Firecrawl API is required for scraping job postings</li>
                    <li>• Supabase is required for storing and managing job data</li>
                    <li>• Demo mode works without Supabase for testing</li>
                </ul>
            </div>
        `;

        modal.classList.remove('hidden');
    }

    closeConfigModal() {
        const modal = document.getElementById('config-modal');
        modal.classList.add('hidden');
    }

    searchJobs(query) {
        if (!query.trim()) {
            this.displayJobs(this.currentJobs);
            return;
        }

        const filtered = this.currentJobs.filter(job => 
            job.job_title.toLowerCase().includes(query.toLowerCase()) ||
            job.company_name.toLowerCase().includes(query.toLowerCase()) ||
            (job.location && job.location.toLowerCase().includes(query.toLowerCase()))
        );

        this.displayJobs(filtered);
    }

    async logInteraction(jobId, type) {
        try {
            await this.apiCall(`/jobs/${jobId}/interact`, {
                method: 'POST',
                body: JSON.stringify({
                    user_id: this.getUserId(),
                    interaction_type: type,
                    interaction_data: { timestamp: new Date().toISOString() }
                })
            });
        } catch (error) {
            console.error('Failed to log interaction:', error);
        }
    }

    getUserId() {
        let userId = localStorage.getItem('job_scraper_user_id');
        if (!userId) {
            userId = 'user_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('job_scraper_user_id', userId);
        }
        return userId;
    }

    formatSalary(job) {
        if (job.salary_text) return job.salary_text;
        if (job.salary_min && job.salary_max) {
            const currency = job.salary_currency || 'USD';
            const symbol = currency === 'USD' ? '$' : currency;
            return `${symbol}${job.salary_min.toLocaleString()} - ${symbol}${job.salary_max.toLocaleString()}`;
        }
        if (job.salary_min) {
            const currency = job.salary_currency || 'USD';
            const symbol = currency === 'USD' ? '$' : currency;
            return `${symbol}${job.salary_min.toLocaleString()}+`;
        }
        return null;
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showLoading(message = 'Loading...') {
        // Simple loading implementation
        const existing = document.getElementById('loading-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center';
        overlay.innerHTML = `
            <div class="bg-white rounded-lg p-6 flex items-center space-x-3">
                <div class="loading-spinner"></div>
                <span class="text-gray-700">${message}</span>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.remove();
    }

    showNotification(message, type = 'info') {
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };

        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 transform transition-transform duration-300 translate-x-full`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => notification.classList.remove('translate-x-full'), 10);

        // Auto remove
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Initialize the application
const app = new JobScraperApp();

