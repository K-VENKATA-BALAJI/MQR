const RECRUITER_KEY = "YourVerySecretRecruiterKey12345";
const BASE_URL = window.location.origin || "";
const SHORTLISTED_APPLICANTS = []; // Current filtered set for "Invite All"
const ALL_APPLICATIONS = []; // Full list from backend

/**
 * Calls the API, fetches filtered and scored applications, and builds the table.
 */
async function loadRecruiterDashboard() {
    const tableBody = document.getElementById('applications-table-body');
    const loadingMessage = document.getElementById('loading-message');
    const inviteAllButton = document.getElementById('invite-all-button');
    
    tableBody.innerHTML = '';
    SHORTLISTED_APPLICANTS.length = 0;
    ALL_APPLICATIONS.length = 0;
    loadingMessage.textContent = 'Loading and scoring applications...';
    inviteAllButton.disabled = true;

    try {
        const response = await fetch(`${BASE_URL}/api/scored_applications`, {
            method: 'GET',
            headers: {
                'X-Recruiter-Key': RECRUITER_KEY,
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 401) {
            loadingMessage.textContent = 'Error: Authentication failed. Check your RECRUITER_KEY.';
            return;
        }

        const data = await response.json();

        if (data.status === 'success' && Array.isArray(data.applications)) {
            // Store all applications and render with current filter (default 0)
            data.applications.forEach(a => ALL_APPLICATIONS.push(a));
            applyFilters();
            loadingMessage.textContent = `Loaded ${ALL_APPLICATIONS.length} applications.`;
            inviteAllButton.disabled = false;
        } else {
            loadingMessage.textContent = data.message || 'No applications found.';
        }
    } catch (error) {
        console.error('Fetch error:', error);
        loadingMessage.textContent = 'Error connecting to the backend server. Ensure the server is running.';
    }
}

function renderTable(applications) {
    const tableBody = document.getElementById('applications-table-body');
    tableBody.innerHTML = '';
    SHORTLISTED_APPLICANTS.length = 0;

    applications.forEach(app => {
        const row = tableBody.insertRow();

        SHORTLISTED_APPLICANTS.push(app.App_ID);

        row.insertCell().textContent = app.App_ID;
        row.insertCell().textContent = app.Job_Title;

        const scoreCell = row.insertCell();
        scoreCell.textContent = app.ATS_Score + '%';
        scoreCell.style.fontWeight = 'bold';
        scoreCell.style.color = app.ATS_Score >= 80 ? 'green' : (app.ATS_Score >= 70 ? 'orange' : '#333');
        scoreCell.classList.add('score-clickable');
        scoreCell.title = 'Click to view score breakdown';
        scoreCell.onclick = () => showScoreDetails(app.App_ID);

        const viewButtonCell = row.insertCell();
        // Create button container
        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.gap = '5px';
        buttonContainer.style.flexWrap = 'wrap';
        
        // View Resume button
        const viewButton = document.createElement('button');
        viewButton.textContent = 'View Resume 📄';
        viewButton.className = 'view-btn';
        if (!app.Resume_File) {
            viewButton.style.opacity = '0.7';
            viewButton.title = 'Resume file may not exist - will show error if not found';
        }
        viewButton.onclick = () => {
            openResumeInNewTab(app.App_ID);
        };
        buttonContainer.appendChild(viewButton);
        
        // View Highlights button
        const highlightsButton = document.createElement('button');
        highlightsButton.textContent = 'View Highlights 🔍';
        highlightsButton.className = 'highlights-btn';
        if (!app.Resume_File) {
            highlightsButton.style.opacity = '0.7';
            highlightsButton.title = 'Highlights available only for PDF resumes';
        }
        highlightsButton.onclick = () => {
            showResumeHighlightsOnly(app.App_ID);
        };
        buttonContainer.appendChild(highlightsButton);
        
        viewButtonCell.appendChild(buttonContainer);

        const inviteCell = row.insertCell();
        const inviteButton = document.createElement('button');
        inviteButton.textContent = 'Send Invite 📧';
        inviteButton.className = 'invite-btn';
        inviteButton.setAttribute('data-app-id', app.App_ID);
        inviteButton.onclick = () => sendInterviewInvite(app.App_ID, inviteButton);
        inviteCell.appendChild(inviteButton);
    });
}

function applyFilters() {
    const minScoreInput = document.getElementById('min-score');
    const searchInput = document.getElementById('search-app-id');
    const currentFilter = document.getElementById('current-filter');
    
    const minScore = Math.max(0, Math.min(100, parseInt(minScoreInput.value || '0', 10)));
    const searchTerm = (searchInput.value || '').trim().toLowerCase();
    
    let filtered = ALL_APPLICATIONS.filter(a => {
        // Apply score filter
        const scoreMatch = (a.ATS_Score || 0) >= minScore;
        
        // Apply search filter (case-insensitive partial match)
        const searchMatch = !searchTerm || (a.App_ID || '').toLowerCase().includes(searchTerm);
        
        return scoreMatch && searchMatch;
    });
    
    renderTable(filtered);
    
    // Update status message
    let statusMsg = `Showing ${filtered.length}/${ALL_APPLICATIONS.length}`;
    if (minScore > 0) {
        statusMsg += ` (Min Score: ${minScore})`;
    }
    if (searchTerm) {
        statusMsg += ` (Search: "${searchTerm}")`;
    }
    currentFilter.textContent = statusMsg;
}

function clearFilters() {
    const minScoreInput = document.getElementById('min-score');
    const searchInput = document.getElementById('search-app-id');
    minScoreInput.value = 0;
    searchInput.value = '';
    applyFilters();
}

function clearSearch() {
    const searchInput = document.getElementById('search-app-id');
    searchInput.value = '';
    applyFilters();
}

/**
 * Shows only highlights modal (without opening resume)
 */
async function showResumeHighlightsOnly(appId) {
    try {
        const highlightsRes = await fetch(`${BASE_URL}/api/resume_highlights/${appId}`, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });

        if (highlightsRes.ok) {
            const highlightsData = await highlightsRes.json();
            if (highlightsData.status === 'success') {
                showResumeHighlightsModal(appId, highlightsData);
            } else {
                alert(`Error loading highlights: ${highlightsData.message || 'Unknown error'}`);
            }
        } else {
            const errorData = await highlightsRes.json();
            alert(`Error: ${errorData.message || 'Failed to load highlights'}`);
        }
    } catch (e) {
        console.error('Error fetching highlights:', e);
        alert(`Error loading highlights: ${e.message}`);
    }
}

/**
 * Opens highlighted resume view (HTML with highlighted keywords)
 */
async function openHighlightedResume(appId) {
    const viewUrl = `${BASE_URL}/api/view_resume_highlighted/${appId}`;
    
    try {
        const res = await fetch(viewUrl, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });

        if (res.status === 401) {
            alert('Access denied. Check your recruiter key configuration.');
            return;
        }
        
        if (!res.ok) {
            let errorMsg = `Failed to load highlighted resume (Status: ${res.status}).`;
            try {
                const contentType = res.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    const errorData = await res.json();
                    if (errorData.message) {
                        errorMsg = errorData.message;
                    }
                }
            } catch (e) {
                console.error('Error parsing error response:', e);
            }
            
            alert(`Error: ${errorMsg}\n\nFalling back to regular PDF view...`);
            openResumeInNewTab(appId);
            return;
        }

        // Get HTML content
        const htmlContent = await res.text();
        
        // Create blob URL and open in new tab
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const blobUrl = URL.createObjectURL(blob);
        const newWindow = window.open(blobUrl, '_blank');
        
        if (!newWindow) {
            alert('Popup blocked. Please allow popups for this site and try again.');
            URL.revokeObjectURL(blobUrl);
            return;
        }
        
        // Revoke after a delay to allow the new tab to load
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (e) {
        console.error('Error opening highlighted resume:', e);
        alert(`Error opening highlighted resume: ${e.message}\n\nFalling back to regular PDF view...`);
        openResumeInNewTab(appId);
    }
}

/**
 * Opens resume with highlights panel showing ATS score contributors
 */
async function openResumeWithHighlights(appId) {
    // First, fetch highlights
    try {
        const highlightsRes = await fetch(`${BASE_URL}/api/resume_highlights/${appId}`, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });

        if (highlightsRes.ok) {
            const highlightsData = await highlightsRes.json();
            if (highlightsData.status === 'success') {
                showResumeHighlightsModal(appId, highlightsData);
            }
        }
    } catch (e) {
        console.error('Error fetching highlights:', e);
    }

    // Open highlighted resume in new tab
    openHighlightedResume(appId);
}

/**
 * Opens the secured resume viewing URL in a new tab.
 */
async function openResumeInNewTab(appId) {
    const viewUrl = `${BASE_URL}/api/view_resume/${appId}`;
    console.log(`Attempting to open resume for Application ID: ${appId}`);
    
    try {
        const res = await fetch(viewUrl, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });

        console.log(`Response status: ${res.status}, Content-Type: ${res.headers.get('content-type')}`);

        if (res.status === 401) {
            alert('Access denied. Check your recruiter key configuration.');
            return;
        }
        
        if (!res.ok) {
            // Try to parse error message from response
            let errorMsg = `Failed to load resume (Status: ${res.status}).`;
            try {
                // Check if response is JSON
                const contentType = res.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    const errorData = await res.json();
                    if (errorData.message) {
                        errorMsg = errorData.message;
                    }
                } else {
                    // Try to get text
                    const text = await res.text();
                    if (text && text.length < 500) {
                        errorMsg = text;
                    }
                }
            } catch (e) {
                console.error('Error parsing error response:', e);
            }
            
            if (res.status === 404) {
                alert(`Resume not found for Application ID: ${appId}.\n\nError: ${errorMsg}\n\nPlease check:\n1. Is the backend server running?\n2. Check the backend console/terminal for detailed file listing\n3. Does the resume file exist in the resumes folder?\n4. Verify the Application ID matches the filename prefix`);
            } else {
                alert(`Error loading resume: ${errorMsg}\n\nApplication ID: ${appId}`);
            }
            return;
        }

        // Success - get the blob and open it
        const blob = await res.blob();
        console.log(`Blob received: ${blob.size} bytes, type: ${blob.type}`);
        
        if (blob.size === 0) {
            alert(`Resume file is empty for Application ID: ${appId}`);
            return;
        }
        
        const blobUrl = URL.createObjectURL(blob);
        const newWindow = window.open(blobUrl, '_blank');
        
        if (!newWindow) {
            alert('Popup blocked. Please allow popups for this site and try again.');
            URL.revokeObjectURL(blobUrl);
            return;
        }
        
        console.log(`Resume opened successfully in new tab for Application ID: ${appId}`);
        
        // Revoke after a delay to allow the new tab to load
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (e) {
        console.error('Error opening resume:', e);
        alert(`Error opening resume for Application ID: ${appId}\n\nError: ${e.message}\n\nPlease ensure:\n1. The backend server is running on ${BASE_URL}\n2. Your internet connection is working\n3. Check the browser console for more details.`);
    }
}

/**
 * Handles sending an invite to a single applicant.
 */
async function sendInterviewInvite(appId, buttonElement) {
    buttonElement.disabled = true;
    const originalText = buttonElement.textContent;
    buttonElement.textContent = 'Sending...';

    const response = await fetch(`${BASE_URL}/api/invite_applicant/${appId}`, {
        method: 'POST',
        headers: {
            'X-Recruiter-Key': RECRUITER_KEY,
            'Content-Type': 'application/json'
        }
    });
    
    const data = await response.json();
    
    if (data.status === 'success') {
        buttonElement.textContent = 'Sent! ✅';
        buttonElement.style.backgroundColor = '#198754'; // Success color
    } else {
        alert('Failed to send invite: ' + data.message);
        buttonElement.textContent = 'Failed ❌';
        buttonElement.style.backgroundColor = '#dc3545'; // Error color
    }
}

/**
 * Sends an invite to ALL applicants listed in the table using the global SHORTLISTED_APPLICANTS array.
 */
async function sendInviteToAllShortlisted() {
    const inviteAllButton = document.getElementById('invite-all-button');
    const statusDiv = document.getElementById('invite-status-all');
    
    const totalCount = SHORTLISTED_APPLICANTS.length;
    
    if (totalCount === 0) {
        statusDiv.textContent = "No candidates to invite.";
        return;
    }
    
    if (!confirm(`Are you sure you want to send an interview invitation to ALL ${totalCount} shortlisted applicants?`)) {
        return;
    }

    // Disable button during process
    inviteAllButton.disabled = true;
    inviteAllButton.textContent = `Sending 0/${totalCount}...`;
    statusDiv.textContent = 'Starting batch email process...';
    
    let sentCount = 0;
    
    for (const appId of SHORTLISTED_APPLICANTS) {
        // Find the corresponding button on the table row
        const buttonElement = document.querySelector(`[data-app-id="${appId}"]`);
        
        // Use the individual invite function
        await sendInterviewInvite(appId, buttonElement);
        
        // Wait a short delay to avoid overwhelming the SMTP server
        await new Promise(resolve => setTimeout(resolve, 500)); 
        
        sentCount++;
        inviteAllButton.textContent = `Sending ${sentCount}/${totalCount}...`;
    }
    
    statusDiv.textContent = `Batch process finished. ${sentCount} invitations sent.`;
    inviteAllButton.textContent = `Batch Complete!`;
    inviteAllButton.disabled = false;
}

// Start loading the dashboard when the page is fully ready
document.addEventListener('DOMContentLoaded', loadRecruiterDashboard);

// Close modal when clicking outside
window.onclick = function(event) {
    const scoreModal = document.getElementById('scoreDetailsModal');
    const highlightsModal = document.getElementById('resumeHighlightsModal');
    if (event.target === scoreModal) {
        closeScoreModal();
    }
    if (event.target === highlightsModal) {
        closeResumeHighlightsModal();
    }
}

/**
 * Shows detailed ATS score breakdown in a modal
 */
async function showScoreDetails(appId) {
    const modal = document.getElementById('scoreDetailsModal');
    const content = document.getElementById('scoreDetailsContent');
    
    modal.style.display = 'block';
    content.innerHTML = '<p>Loading score details...</p>';

    try {
        const response = await fetch(`${BASE_URL}/api/score_details/${appId}`, {
            method: 'GET',
            headers: {
                'X-Recruiter-Key': RECRUITER_KEY,
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 401) {
            content.innerHTML = '<p style="color: red;">Access denied. Check your recruiter key.</p>';
            return;
        }

        const data = await response.json();

        if (data.status === 'success' && data.score_details) {
            const details = data.score_details;
            const breakdown = details.breakdown;
            
            let html = `
                <div style="margin-bottom: 20px;">
                    <h3 style="color: #007bff; margin: 0;">Application ID: ${details.application_id}</h3>
                    <p style="margin: 5px 0; color: #666;">Job Title: ${details.job_title}</p>
                    <div style="font-size: 2em; font-weight: bold; color: ${details.score >= 80 ? 'green' : (details.score >= 70 ? 'orange' : '#333')}; margin: 10px 0;">
                        Overall Score: ${details.score}%
                    </div>
                </div>

                <div class="score-breakdown">
                    <h3>Score Breakdown:</h3>
                    <div class="breakdown-item">
                        <strong>Base Score:</strong> ${breakdown.base_score} points
                    </div>
                    <div class="breakdown-item">
                        <strong>Seniority Bonus:</strong> ${breakdown.seniority_bonus} points
                        ${breakdown.seniority_bonus > 0 ? '<span style="color: green;">✓</span>' : '<span style="color: #999;">Role title indicates seniority level</span>'}
                    </div>
                    <div class="breakdown-item">
                        <strong>Role Family Bonus:</strong> ${breakdown.role_family_bonus} points
                        ${breakdown.role_family_bonus > 0 ? '<span style="color: green;">✓</span>' : ''}
                    </div>
                    <div class="breakdown-item">
                        <strong>Keyword Match Score:</strong> ${breakdown.keyword_match_score} points (${details.matched_keywords.length} keywords matched)
                        <div style="margin-top: 5px; font-size: 0.9em; color: #666;">
                            Max possible: 40 points (10 keywords × 4 points each)
                        </div>
                    </div>
                    <div class="breakdown-item">
                        <strong>Work Experience Score:</strong> ${breakdown.work_experience_score} points
                        <div style="margin-top: 5px; font-size: 0.9em; color: #666;">
                            ${details.work_experience_count} work experience entries (3 points each, max 15)
                        </div>
                    </div>
                    <div class="breakdown-item">
                        <strong>Education Relevance Score:</strong> ${breakdown.education_relevance_score} points
                        <div style="margin-top: 5px; font-size: 0.9em; color: #666;">
                            ${details.education_count} education entries
                        </div>
                    </div>
                    <div class="breakdown-item">
                        <strong>Resume Type Bonus:</strong> ${breakdown.resume_type_score} points
                        ${breakdown.resume_type_score > 0 ? '<span style="color: green;">✓ PDF format</span>' : '<span style="color: #999;">Consider using PDF format</span>'}
                    </div>
                    ${breakdown.jitter !== 0 ? `<div class="breakdown-item"><strong>Random Factor:</strong> ${breakdown.jitter > 0 ? '+' : ''}${breakdown.jitter} points</div>` : ''}
                    <div class="breakdown-item" style="background: #e7f3ff; border-left-color: #007bff;">
                        <strong>Total Score:</strong> ${details.score}% 
                        <span style="float: right; font-size: 1.2em; color: ${details.score >= 80 ? 'green' : (details.score >= 70 ? 'orange' : '#333')};">
                            ${details.score >= 80 ? 'Excellent' : (details.score >= 70 ? 'Good' : (details.score >= 60 ? 'Fair' : 'Needs Improvement'))}
                        </span>
                    </div>
                </div>

                <div class="keywords-section">
                    <h3>Matched Keywords (${details.matched_keywords.length}):</h3>
                    ${details.matched_keywords.length > 0 
                        ? details.matched_keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')
                        : '<p style="color: #999;">No keywords matched</p>'
                    }
                </div>

                <div class="keywords-section">
                    <h3>Missing Keywords (${details.missing_keywords.length}):</h3>
                    ${details.missing_keywords.length > 0 
                        ? details.missing_keywords.slice(0, 20).map(kw => `<span class="keyword-tag missing">${kw}</span>`).join('')
                        : '<p style="color: green;">All relevant keywords found! ✓</p>'
                    }
                    ${details.missing_keywords.length > 20 ? `<p style="color: #666; font-size: 0.9em;">...and ${details.missing_keywords.length - 20} more</p>` : ''}
                </div>

                <div class="suggestions">
                    <h3>💡 Suggestions to Improve Score:</h3>
                    ${details.suggestions.length > 0 
                        ? `<ul>${details.suggestions.map(s => `<li>${s}</li>`).join('')}</ul>`
                        : '<p>Great job! Your resume matches well with the job requirements.</p>'
                    }
                </div>
            `;
            
            content.innerHTML = html;
        } else {
            content.innerHTML = `<p style="color: red;">Error: ${data.message || 'Failed to load score details'}</p>`;
        }
    } catch (error) {
        console.error('Error loading score details:', error);
        content.innerHTML = `<p style="color: red;">Error loading score details: ${error.message}</p>`;
    }
}

function closeScoreModal() {
    document.getElementById('scoreDetailsModal').style.display = 'none';
}

/**
 * Shows resume highlights modal with ATS score contributors
 */
function showResumeHighlightsModal(appId, highlightsData) {
    const modal = document.getElementById('resumeHighlightsModal');
    const content = document.getElementById('resumeHighlightsContent');
    const controls = document.getElementById('resumeHighlightsControls');
    
    if (!modal || !content) {
        console.error('Resume highlights modal elements not found');
        return;
    }
    
    modal.style.display = 'block';
    content.innerHTML = '<p>Loading highlights...</p>';

    const highlights = highlightsData.highlights || {};
    const atsScore = highlightsData.ats_score || 0;
    const jobTitle = highlightsData.job_title || 'Unknown';
    
    // Store highlights data globally for filtering and export
    window.currentHighlightsData = { appId, highlightsData, highlights };

    // Build filter controls
    const hasSkills = highlights.skills && highlights.skills.length > 0;
    const hasExperience = highlights.experience && highlights.experience.length > 0;
    const hasEducation = highlights.education && highlights.education.length > 0;
    const hasKeywords = highlights.matched_keywords && highlights.matched_keywords.length > 0;
    const hasContext = highlights.keywords && highlights.keywords.length > 0;

    controls.innerHTML = `
        <div class="highlight-filters">
            <strong>Filter Sections:</strong>
            <div class="filter-checkbox">
                <input type="checkbox" id="filter-skills" checked>
                <label for="filter-skills">Skills</label>
            </div>
            <div class="filter-checkbox">
                <input type="checkbox" id="filter-experience" checked>
                <label for="filter-experience">Experience</label>
            </div>
            <div class="filter-checkbox">
                <input type="checkbox" id="filter-education" checked>
                <label for="filter-education">Education</label>
            </div>
            <div class="filter-checkbox">
                <input type="checkbox" id="filter-keywords" checked>
                <label for="filter-keywords">Keywords</label>
            </div>
            <div class="filter-checkbox">
                <input type="checkbox" id="filter-context" checked>
                <label for="filter-context">Context</label>
            </div>
            <button class="view-btn" onclick="openHighlightedResume('${appId}')" style="padding: 8px 15px;">📄 View Highlighted Resume</button>
        </div>
    `;
    controls.style.display = 'block';
    
    // Add event listeners for filters
    ['skills', 'experience', 'education', 'keywords', 'context'].forEach(section => {
        const checkbox = document.getElementById(`filter-${section}`);
        if (checkbox) {
            checkbox.addEventListener('change', () => toggleHighlightSection(section));
        }
    });

    let html = `
        <div style="margin-bottom: 20px;">
            <h3 style="color: #007bff; margin: 0;">Application ID: ${appId}</h3>
            <p style="margin: 5px 0; color: #666;">Job Title: ${jobTitle}</p>
            <div style="font-size: 1.5em; font-weight: bold; color: ${atsScore >= 80 ? 'green' : (atsScore >= 70 ? 'orange' : '#333')}; margin: 10px 0;">
                ATS Score: ${atsScore}%
            </div>
            <p style="color: #666; font-size: 0.9em;">These are the elements found in the resume that contributed to the ATS score:</p>
        </div>

        <div id="highlights-content" style="max-height: 70vh; overflow-y: auto;">
    `;

    // Skills Section
    if (highlights.skills && highlights.skills.length > 0) {
        html += `
            <div id="highlight-section-skills" class="highlight-section" style="margin: 20px 0; padding: 15px; background: #e7f3ff; border-left: 4px solid #007bff; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #007bff;">✅ Skills Found</h3>
        `;
        highlights.skills.forEach((skill, idx) => {
            html += `
                <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px;">
                    <strong>Skills Section:</strong>
                    <p style="margin: 5px 0; font-size: 0.9em; white-space: pre-wrap;">${skill.section}</p>
                    ${skill.highlighted_keywords && skill.highlighted_keywords.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <strong>Matched Keywords:</strong>
                            ${skill.highlighted_keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += `</div>`;
    } else {
        html += `
            <div class="highlight-section" style="margin: 20px 0; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #856404;">⚠️ Skills Section</h3>
                <p style="color: #856404;">No skills section found or no relevant keywords matched.</p>
            </div>
        `;
    }

    // Experience Section
    if (highlights.experience && highlights.experience.length > 0) {
        html += `
            <div id="highlight-section-experience" class="highlight-section" style="margin: 20px 0; padding: 15px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #28a745;">💼 Experience Found</h3>
        `;
        highlights.experience.forEach((exp, idx) => {
            html += `
                <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px;">
                    <strong>Experience Section:</strong>
                    <p style="margin: 5px 0; font-size: 0.9em; white-space: pre-wrap;">${exp.section}</p>
                    ${exp.highlighted_keywords && exp.highlighted_keywords.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <strong>Matched Keywords:</strong>
                            ${exp.highlighted_keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${exp.job_titles && exp.job_titles.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <strong>Job Titles/Companies:</strong>
                            ${exp.job_titles.map(title => `<span class="keyword-tag" style="background: #17a2b8;">${title}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += `</div>`;
    } else {
        html += `
            <div class="highlight-section" style="margin: 20px 0; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #856404;">⚠️ Experience Section</h3>
                <p style="color: #856404;">No relevant experience section found or no matching keywords.</p>
            </div>
        `;
    }

    // Education Section
    if (highlights.education && highlights.education.length > 0) {
        html += `
            <div id="highlight-section-education" class="highlight-section" style="margin: 20px 0; padding: 15px; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #dc3545;">🎓 Education Found</h3>
        `;
        highlights.education.forEach((edu, idx) => {
            html += `
                <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px;">
                    <strong>Education Section:</strong>
                    <p style="margin: 5px 0; font-size: 0.9em; white-space: pre-wrap;">${edu.section}</p>
                    ${edu.highlighted_keywords && edu.highlighted_keywords.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <strong>Relevant Fields:</strong>
                            ${edu.highlighted_keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${edu.education_terms && edu.education_terms.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <strong>Education Details:</strong>
                            ${edu.education_terms.map(term => `<span class="keyword-tag" style="background: #6c757d;">${term}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += `</div>`;
    } else {
        html += `
            <div class="highlight-section" style="margin: 20px 0; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #856404;">⚠️ Education Section</h3>
                <p style="color: #856404;">No relevant education section found or no matching keywords.</p>
            </div>
        `;
    }

    // Keywords Found
    if (highlights.matched_keywords && highlights.matched_keywords.length > 0) {
        html += `
            <div id="highlight-section-keywords" class="highlight-section" style="margin: 20px 0; padding: 15px; background: #e7f3ff; border-left: 4px solid #007bff; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #007bff;">🔑 All Matched Keywords (${highlights.matched_keywords.length})</h3>
                <div style="margin-top: 10px;">
                    ${highlights.matched_keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                </div>
            </div>
        `;
    }

    // Keywords with Context
    if (highlights.keywords && highlights.keywords.length > 0) {
        html += `
            <div id="highlight-section-context" class="highlight-section" style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #6c757d; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #495057;">📝 Keywords in Context</h3>
        `;
        highlights.keywords.slice(0, 10).forEach((kw, idx) => {
            html += `
                <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px; font-size: 0.9em;">
                    <strong style="color: #007bff;">"${kw.keyword}"</strong>
                    <p style="margin: 5px 0; color: #666;">...${kw.context}...</p>
                </div>
            `;
        });
        html += `</div>`;
    }

    html += `</div>`;

    content.innerHTML = html;
}

function closeResumeHighlightsModal() {
    document.getElementById('resumeHighlightsModal').style.display = 'none';
    window.currentHighlightsData = null;
}

/**
 * Opens resume from highlights modal
 */
async function openResumeFromHighlights(appId) {
    openResumeInNewTab(appId);
}

/**
 * Toggles visibility of highlight sections based on filter checkboxes
 */
function toggleHighlightSection(section) {
    const checkbox = document.getElementById(`filter-${section}`);
    const sectionElement = document.getElementById(`highlight-section-${section}`);
    
    if (sectionElement && checkbox) {
        if (checkbox.checked) {
            sectionElement.style.display = 'block';
        } else {
            sectionElement.style.display = 'none';
        }
    }
}
