let BASE_URL = window.location.origin || "";
const RECRUITER_KEY = "YourVerySecretRecruiterKey12345";

const STATUS_OPTIONS = ["Go", "Pending", "No go"];

document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-button');
    if (refreshBtn) refreshBtn.addEventListener('click', loadSchedule);
    const recruiterFilter = document.getElementById('recruiter-filter');
    if (recruiterFilter) recruiterFilter.remove();
    const debouncedRender = debounce(render, 150);
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) statusFilter.addEventListener('change', debouncedRender);
    const processFilter = document.getElementById('process-filter');
    if (processFilter) processFilter.addEventListener('change', debouncedRender);
    const searchInput = document.getElementById('search-app');
    if (searchInput) searchInput.addEventListener('input', debouncedRender);
    loadSchedule();
});

let SCHEDULE = [];
let IS_LOADING_SCHEDULE = false;
let RESOLVED_BASE = null;

async function resolveBackendBaseUrl() {
    // Return memoized result if already resolved
    if (RESOLVED_BASE) return RESOLVED_BASE;
    // Try current BASE_URL first, then fall back to localhost if needed
    const candidates = [BASE_URL, "http://localhost:5000"]; 
    for (const url of candidates) {
        try {
            const res = await fetch(`${url}/api/score_details/health-check`, {
                method: 'OPTIONS'
            });
            // If no exception, assume server reachable on this base
            BASE_URL = url;
            RESOLVED_BASE = url;
            return url;
        } catch (_) {
            // try next
        }
    }
    RESOLVED_BASE = BASE_URL;
    return BASE_URL; // keep existing (will likely fail if none reachable)
}

async function loadSchedule() {
    if (IS_LOADING_SCHEDULE) return;
    IS_LOADING_SCHEDULE = true;
    const refreshBtn = document.getElementById('refresh-button');
    if (refreshBtn) refreshBtn.disabled = true;
    try {
        await resolveBackendBaseUrl();
        const res = await fetch(`${BASE_URL}/api/schedule`, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });
        if (res.status === 401) {
            alert('Access denied. Check your recruiter key.');
            return;
        }
        const data = await res.json();
        if (data.status !== 'success') {
            alert(data.message || 'Failed to load schedule');
            return;
        }
        SCHEDULE = (data.schedule || []).map((item, idx) => ({ ...item, _order: idx }));
        hydrateRecruiterFilter(SCHEDULE);
        render();
    } catch (e) {
        console.error(e);
        alert(`Failed to load schedule. Ensure backend is running on 127.0.0.1:5000 or localhost:5000.\n\nError: ${e?.message || e}`);
    } finally {
        IS_LOADING_SCHEDULE = false;
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function hydrateRecruiterFilter(items) {
    const select = document.getElementById('recruiter-filter');
    if (!select) return; // recruiter filter removed from UI
    const values = Array.from(new Set(items.map(i => i.Recruiter).filter(Boolean)));
    // keep first option
    select.querySelectorAll('option:not(:first-child)').forEach(o => o.remove());
    values.forEach(v => {
        const op = document.createElement('option');
        op.value = v; op.textContent = v; select.appendChild(op);
    });
}

function statusClass(s) {
    const val = (s || 'Pending').toLowerCase();
    if (val === 'go') return 'pill-go';
    if (val === 'no go' || val === 'nogo' || val === 'no-go') return 'pill-nogo';
    return 'pill-pending';
}

function render() {
    const body = document.getElementById('schedule-body');
    body.innerHTML = '';

    // recruiter filter removed
    const statusFilter = document.getElementById('status-filter').value;
    const processFilter = document.getElementById('process-filter').value;
    const search = (document.getElementById('search-app').value || '').toLowerCase();

    let rows = SCHEDULE.slice();
    if (search) rows = rows.filter(r => (r.App_ID || '').toLowerCase().includes(search));

    if (processFilter !== 'all') {
        rows = rows.filter(r => (r.Application_Status || 'Open').toLowerCase() === processFilter);
    }

    if (statusFilter !== 'all') {
        rows = rows.filter(r => {
            const phone = norm(r.Phone_Status);
            const inperson = norm(r.Inperson_Status);
            if (statusFilter === 'new') return phone === 'pending' && inperson === 'pending';
            if (statusFilter === 'inprogress') return phone !== 'pending' && inperson === 'pending';
            if (statusFilter === 'hired') return phone === 'go' && inperson === 'go';
            if (statusFilter === 'rejected') return [phone, inperson].includes('no go');
            return true;
        });
    }

    // Keep original stable order even after filtering
    rows.sort((a, b) => (a._order ?? 0) - (b._order ?? 0));
    rows.forEach((item, idx) => {
        const tr = body.insertRow();
        tr.insertCell().textContent = String(idx + 1);
        
        // Application ID - clickable link to open details
        const appCell = tr.insertCell();
        const appLink = document.createElement('span');
        appLink.className = 'app-id-link';
        appLink.textContent = item.App_ID;
        appLink.title = 'View applicant details';
        appLink.onclick = () => openApplicantSplit(item);
        appCell.appendChild(appLink);
        
        tr.appendChild(editableTextCell(item, 'Interviewer', 'interviewer'));
        tr.insertCell().textContent = item.Job_Title || '';
        tr.appendChild(editableSourceCell(item, 'Source', 'source'));
        tr.appendChild(editableStatusCell(item, 'Phone_Status', 'phone_status'));
        tr.appendChild(editableStatusCell(item, 'Inperson_Status', 'inperson_status'));
        const actions = tr.insertCell();
        actions.className = 'table-actions';
        
        const btnMail = document.createElement('button');
        btnMail.className = 'btn btn-mail';
        btnMail.textContent = '📧 Send Mail';
        btnMail.onclick = () => openMailModal(item.App_ID);
        actions.appendChild(btnMail);
        
        const btnView = document.createElement('button');
        btnView.className = 'btn btn-link';
        btnView.textContent = 'View Resume';
        btnView.onclick = () => openResume(item.App_ID);
        actions.appendChild(btnView);

        const btnClose = document.createElement('button');
        btnClose.className = 'btn btn-secondary';
        btnClose.textContent = (item.Application_Status || 'Open') === 'Closed' ? 'Closed' : 'Close Application';
        btnClose.disabled = (item.Application_Status || 'Open') === 'Closed';
        btnClose.onclick = async () => {
            if (!confirm(`Close application ${item.App_ID}?`)) return;
            await saveField(item.App_ID, { application_status: 'Closed' });
            item.Application_Status = 'Closed';
            render();
        };
        actions.appendChild(btnClose);
    });

    document.getElementById('count-label').textContent = `Showing ${rows.length}/${SCHEDULE.length}`;
}

function norm(v) { return (v || 'Pending').toLowerCase(); }

// Simple debounce helper
function debounce(fn, wait) {
    let t;
    return function(...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}

function editableSourceCell(item, prop, keyForApi) {
    const td = document.createElement('td');
    const select = document.createElement('select');
    const sourceOptions = ['', 'LinkedIn', 'Indeed', 'Naukri'];
    sourceOptions.forEach(opt => {
        const op = document.createElement('option');
        op.value = opt;
        op.textContent = opt || 'Select Source';
        select.appendChild(op);
    });
    select.value = item[prop] || '';
    select.style.padding = '6px 8px';
    select.onchange = async () => {
        await saveField(item.App_ID, { [keyForApi]: select.value });
        item[prop] = select.value;
    };
    td.appendChild(select);
    return td;
}

function editableTextCell(item, prop, keyForApi) {
    const td = document.createElement('td');
    const input = document.createElement('input');
    input.type = 'text';
    input.value = item[prop] || '';
    input.style.padding = '6px 8px';
    if (keyForApi === 'interviewer') input.setAttribute('list', 'interviewers-list');
    input.onchange = async () => {
        await saveField(item.App_ID, { [keyForApi]: input.value });
        item[prop] = input.value;
    };
    td.appendChild(input);
    return td;
}

function editableStatusCell(item, prop, keyForApi) {
    const td = document.createElement('td');
    const select = document.createElement('select');
    STATUS_OPTIONS.forEach(s => {
        const op = document.createElement('option');
        op.value = s; op.textContent = s; select.appendChild(op);
    });
    select.value = normalizeDisplay(item[prop]);
    select.onchange = async () => {
        await saveField(item.App_ID, { [keyForApi]: select.value });
        item[prop] = select.value;
        badge.textContent = select.value;
        badge.className = `status-pill ${statusClass(select.value)}`;
        // Do not re-render entire table to preserve row position
    };

    const badge = document.createElement('span');
    badge.className = `status-pill ${statusClass(item[prop])}`;
    badge.textContent = normalizeDisplay(item[prop]);

    td.appendChild(select);
    td.appendChild(document.createTextNode(' '));
    td.appendChild(badge);
    return td;
}

function normalizeDisplay(v) {
    const t = (v || '').toLowerCase();
    if (t === 'nogo' || t === 'no-go') return 'No go';
    if (t === 'go') return 'Go';
    if (t === 'no go') return 'No go';
    return 'Pending';
}

async function saveField(appId, payload) {
    async function attempt() {
        const res = await fetch(`${BASE_URL}/api/schedule/${encodeURIComponent(appId)}`, {
            method: 'PATCH',
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json',
                'X-Recruiter-Key': RECRUITER_KEY
            },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const msg = await safeText(res);
            throw new Error(msg || `HTTP ${res.status}`);
        }
    }

    try {
        await attempt();
    } catch (e1) {
        // Retry once after brief delay (handles transient CORS/preflight races)
        await new Promise(r => setTimeout(r, 400));
        try {
            await attempt();
        } catch (e2) {
            console.error('Save failed:', e2);
            alert(`Network error while saving. ${e2?.message ? '\\n' + e2.message : ''}`);
        }
    }
}

async function safeText(res) {
    try { return await res.text(); } catch { return `${res.status}`; }
}

async function openResume(appId) {
    try {
        const res = await fetch(`${BASE_URL}/api/view_resume/${appId}`, { headers: { 'X-Recruiter-Key': RECRUITER_KEY } });
        if (!res.ok) {
            alert('Failed to fetch resume');
            return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const win = window.open(url, '_blank');
        if (!win) alert('Popup blocked. Please allow popups.');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
        console.error(e);
        alert('Error opening resume');
    }
}

let currentMailAppId = null;

function openMailModal(appId) {
    currentMailAppId = appId;
    const modal = document.getElementById('mailModal');
    const form = document.getElementById('mail-form');
    form.reset();
    // Set default date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById('interview-date').value = tomorrow.toISOString().split('T')[0];
    // Set default time to 10:00 AM
    document.getElementById('interview-time').value = '10:00';
    modal.style.display = 'block';
}

function closeMailModal() {
    const modal = document.getElementById('mailModal');
    modal.style.display = 'none';
    currentMailAppId = null;
}

async function sendStatusEmail() {
    if (!currentMailAppId) {
        alert('Error: No application selected');
        return;
    }

    const interviewDate = document.getElementById('interview-date').value;
    const interviewTime = document.getElementById('interview-time').value;
    const processStatus = document.getElementById('process-status').value;
    const additionalNotes = document.getElementById('additional-notes').value;

    if (!interviewDate || !interviewTime || !processStatus) {
        alert('Please fill in all required fields');
        return;
    }

    const submitBtn = document.querySelector('#mail-form button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';

    try {
        const response = await fetch(`${BASE_URL}/api/send_status_email/${currentMailAppId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Recruiter-Key': RECRUITER_KEY
            },
            body: JSON.stringify({
                interview_date: interviewDate,
                interview_time: interviewTime,
                process_status: processStatus,
                additional_notes: additionalNotes
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            alert(`Email sent successfully to ${data.applicant_name || 'applicant'}!`);
            closeMailModal();
        } else {
            alert(`Failed to send email: ${data.message || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert(`Error sending email: ${e.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

async function openReplyEmail(appId) {
    try {
        // Get applicant email from backend
        const response = await fetch(`${BASE_URL}/api/get_applicant_email/${appId}`, {
            method: 'GET',
            headers: {
                'X-Recruiter-Key': RECRUITER_KEY
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success' && data.email) {
                // Create mailto link with subject
                const subject = encodeURIComponent(`Re: Application ${appId} - Interview Confirmation`);
                const mailtoLink = `mailto:${data.email}?subject=${subject}`;
                try {
                    // Prefer direct navigation for mailto to avoid popup blockers
                    window.location.href = mailtoLink;
                } catch (_) {
                    // Fallback: programmatically click a temporary anchor
                    const a = document.createElement('a');
                    a.href = mailtoLink;
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => a.remove(), 0);
                }
            } else {
                alert('Could not retrieve applicant email address');
            }
        } else {
            alert('Failed to retrieve applicant information');
        }
    } catch (e) {
        console.error(e);
        alert(`Error: ${e.message}`);
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('mailModal');
    if (event.target === modal) {
        closeMailModal();
    }
}

/**
 * Applicant details popup
 */
async function openApplicantDetails(appId) {
    const modal = document.getElementById('applicantDetailsModal');
    const body = document.getElementById('applicantDetailsBody');
    if (!modal || !body) return;
    modal.style.display = 'block';
    body.innerHTML = '<p>Loading...</p>';

    try {
        const res = await fetch(`${BASE_URL}/api/get_application/${encodeURIComponent(appId)}`, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });
        if (!res.ok) {
            const msg = await safeText(res);
            body.innerHTML = `<p style="color:#dc3545;">Failed to load details: ${msg}</p>`;
            return;
        }
        const data = await res.json();
        if (data.status !== 'success') {
            body.innerHTML = `<p style="color:#dc3545;">${data.message || 'Unable to load application data'}</p>`;
            return;
        }

        const app = data.application_data || {};
        const personal = app.personal || {};
        const comm = app.communication || {};
        const edu = Array.isArray(app.education) ? app.education : [];
        const work = Array.isArray(app.work) ? app.work : [];

        const fullName = [personal.firstName, personal.middleName, personal.lastName].filter(Boolean).join(' ') || 'N/A';
        const email = comm.email || 'N/A';
        const phone = comm.phone || 'N/A';

        // Best-effort LinkedIn/portfolio extraction
        const possibleLinks = [];
        const textBlobs = [JSON.stringify(app || {})];
        const linkRegex = /(https?:\/\/[\w.-]+\.[\w.-]+\S*)/gi;
        for (const blob of textBlobs) {
            let m;
            while ((m = linkRegex.exec(blob)) !== null) {
                const url = m[1];
                if (!possibleLinks.includes(url)) possibleLinks.push(url);
            }
        }
        const linkedin = possibleLinks.find(u => /linkedin\.com\/in\//i.test(u)) || '';

        const eduLines = edu.slice(0, 3).map((e, i) => `
            <li><strong>${e.degree || 'Degree'}</strong>, ${e.branch || ''} @ ${e.institution || ''}</li>
        `).join('');
        const workLines = work.slice(0, 3).map(w => `
            <li><strong>${w.title || 'Role'}</strong> @ ${w.company || ''}</li>
        `).join('');

        body.innerHTML = `
            <div>
                <div style="margin-bottom:10px;">
                    <div style="font-weight:bold; font-size:1.1em;">${fullName}</div>
                    <div><strong>Email:</strong> <a href="mailto:${email}">${email}</a></div>
                    <div><strong>Phone:</strong> ${phone}</div>
                    ${linkedin ? `<div><strong>LinkedIn:</strong> <a href="${linkedin}" target="_blank" rel="noopener">${linkedin}</a></div>` : ''}
                </div>
                ${eduLines ? `<div style="margin-top:10px;"><strong>Education:</strong><ul>${eduLines}</ul></div>` : ''}
                ${workLines ? `<div style="margin-top:10px;"><strong>Work:</strong><ul>${workLines}</ul></div>` : ''}
            </div>
        `;
    } catch (e) {
        console.error(e);
        body.innerHTML = `<p style="color:#dc3545;">Error: ${e.message}</p>`;
    }
}

function closeApplicantDetails() {
    const modal = document.getElementById('applicantDetailsModal');
    if (modal) modal.style.display = 'none';
}

// Extend outside-click to close applicant details as well
window.addEventListener('click', function (event) {
    const detailsModal = document.getElementById('applicantDetailsModal');
    if (event.target === detailsModal) {
        closeApplicantDetails();
    }
    const splitModal = document.getElementById('splitModal');
    if (event.target === splitModal) {
        closeSplitModal();
    }
});

/**
 * Split-screen modal: populate left (details) and right (RSVP) when clicking App ID
 */
function showSplitModal() {
    const modal = document.getElementById('splitModal');
    if (modal) modal.style.display = 'block';
}

function closeSplitModal() {
    const modal = document.getElementById('splitModal');
    if (modal) modal.style.display = 'none';
}

function setSplitRsvp(appId, statusText) {
    const right = document.getElementById('splitModalRightBody');
    if (!right) return;
    const rsvp = (statusText || 'Pending').toLowerCase();
    const pillClass = rsvp === 'accepted' ? 'pill-go' : (rsvp === 'declined' ? 'pill-nogo' : 'pill-pending');
    const nice = rsvp.charAt(0).toUpperCase() + rsvp.slice(1);
    right.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
            <span class="status-pill ${pillClass}">${nice}</span>
            <span style="color:#555;">Current RSVP status for <strong>${appId}</strong></span>
        </div>
        <div style="margin-top:10px; font-size:0.9em; color:#666;">This updates automatically when the applicant clicks their email link. Use Refresh to pull latest.</div>
        <div style="margin-top:12px;">
            <button class="btn btn-secondary" id="split-refresh-btn">Refresh Status</button>
        </div>
    `;
    const btn = document.getElementById('split-refresh-btn');
    if (btn) {
        btn.onclick = async () => {
            await loadSchedule();
            const updated = SCHEDULE.find(r => r.App_ID === appId);
            setSplitRsvp(appId, updated ? updated.Rsvp_Status : statusText);
        };
    }
}

async function renderApplicantDetailsToSplit(appId) {
    const left = document.getElementById('splitModalLeftBody');
    if (!left) return;
    left.innerHTML = '<p>Loading...</p>';
    try {
        const res = await fetch(`${BASE_URL}/api/get_application/${encodeURIComponent(appId)}`, {
            method: 'GET',
            headers: { 'X-Recruiter-Key': RECRUITER_KEY }
        });
        if (!res.ok) {
            const msg = await safeText(res);
            left.innerHTML = `<p style="color:#dc3545;">Failed to load details: ${msg}</p>`;
            return;
        }
        const data = await res.json();
        if (data.status !== 'success') {
            left.innerHTML = `<p style="color:#dc3545;">${data.message || 'Unable to load application data'}</p>`;
            return;
        }
        const app = data.application_data || {};
        const personal = app.personal || {};
        const comm = app.communication || {};
        const edu = Array.isArray(app.education) ? app.education : [];
        const work = Array.isArray(app.work) ? app.work : [];

        const fullName = [personal.firstName, personal.middleName, personal.lastName].filter(Boolean).join(' ') || 'N/A';
        const email = comm.email || 'N/A';
        const phone = comm.phone || 'N/A';

        const possibleLinks = [];
        const textBlobs = [JSON.stringify(app || {})];
        const linkRegex = /(https?:\/\/[^\s"']+)/gi;
        for (const blob of textBlobs) {
            let m;
            while ((m = linkRegex.exec(blob)) !== null) {
                const url = m[1];
                if (!possibleLinks.includes(url)) possibleLinks.push(url);
            }
        }
        const linkedin = possibleLinks.find(u => /linkedin\.com\/in\//i.test(u)) || '';

        const eduLines = edu.slice(0, 3).map((e) => `
            <li><strong>${e.degree || 'Degree'}</strong>, ${e.branch || ''} @ ${e.institution || ''}</li>
        `).join('');
        const workLines = work.slice(0, 3).map(w => `
            <li><strong>${w.title || 'Role'}</strong> @ ${w.company || ''}</li>
        `).join('');

        left.innerHTML = `
            <div>
                <div style="margin-bottom:10px;">
                    <div style="font-weight:bold; font-size:1.1em;">${fullName}</div>
                    <div><strong>Email:</strong> <a href="mailto:${email}">${email}</a></div>
                    <div><strong>Phone:</strong> ${phone}</div>
                    ${linkedin ? `<div><strong>LinkedIn:</strong> <a href="${linkedin}" target="_blank" rel="noopener">${linkedin}</a></div>` : ''}
                </div>
                ${eduLines ? `<div style=\"margin-top:10px;\"><strong>Education:</strong><ul>${eduLines}</ul></div>` : ''}
                ${workLines ? `<div style=\"margin-top:10px;\"><strong>Work:</strong><ul>${workLines}</ul></div>` : ''}
            </div>
        `;
    } catch (e) {
        console.error(e);
        left.innerHTML = `<p style="color:#dc3545;">Error: ${e.message}</p>`;
    }
}

function openApplicantSplit(item) {
    showSplitModal();
    renderApplicantDetailsToSplit(item.App_ID);
    setSplitRsvp(item.App_ID, item.Rsvp_Status);
}

