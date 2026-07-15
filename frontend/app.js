// DOM Elements
const navLinks = document.querySelectorAll('.nav-links a');
const modules = document.querySelectorAll('.module');
const loader = document.getElementById('global-loader');
const loaderLog = document.getElementById('loader-log');

// Setup SSE for live logs
const evtSource = new EventSource('/api/logs/stream');
evtSource.onmessage = function(e) {
    if(!loader.classList.contains('hidden')) {
        loaderLog.textContent = '>_ ' + e.data;
    }
};

// Navigation
navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        
        const targetId = 'module-' + link.dataset.nav;
        modules.forEach(m => m.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');
        
        if (link.dataset.nav === 'dashboard') loadDashboard();
        if (link.dataset.nav === 'analytics') loadAnalytics();
    });
});

// UI Helpers
function showLoader(title = "WORKING...") {
    document.getElementById('loader-title').textContent = title;
    loaderLog.textContent = ">_ initializing";
    loader.classList.remove('hidden');
}
function hideLoader() {
    loader.classList.add('hidden');
}

// ==========================================
// MODULE: DASHBOARD
// ==========================================
async function loadDashboard() {
    try {
        // Load stats
        const statRes = await fetch('/api/dashboard/stats');
        if (!statRes.ok) throw new Error(`Stats fetch failed: ${statRes.status}`);
        const stats = await statRes.json();
        document.getElementById('stat-today').textContent = stats.today_found ?? 0;
        document.getElementById('stat-ready').textContent = stats.ready_for_outreach ?? 0;
        document.getElementById('stat-sent').textContent = stats.sent_this_week ?? 0;
        document.getElementById('stat-positive').textContent = stats.positive_replies ?? 0;
        
        // Load Daily Batch
        const batchRes = await fetch('/api/dashboard/daily-batch');
        if (!batchRes.ok) throw new Error(`Batch fetch failed: ${batchRes.status}`);
        const batch = await batchRes.json();
        renderBatch(batch);
    } catch (e) {
        console.error('loadDashboard error:', e);
    }
}

function renderBatch(jobs) {
    const container = document.getElementById('daily-batch-list');
    container.innerHTML = '';
    
    if (jobs.length === 0) {
        container.innerHTML = '<div class="dim-text">No pending opportunities. Schedule a new batch!</div>';
        return;
    }
    
    jobs.forEach(job => {
        const badgeClass = job.outreach_priority === 'HIGH' ? 'badge-high' : 'badge-med';
        
        let emailBadge = '';
        if (job.email_hunt_status === 'hunting') {
            emailBadge = '<span style="color: yellow; font-size: 8px;">[Hunting email...]</span>';
        } else if (job.email_hunt_status === 'email_found') {
            emailBadge = '<span style="color: #00ff00; font-size: 8px;">[Email found]</span>';
        } else if (job.email_hunt_status === 'email_failed') {
            emailBadge = '<span style="color: red; font-size: 8px;">[Email manual]</span>';
        }

        const card = document.createElement('div');
        card.className = 'opp-card';
        card.innerHTML = `
            <div class="opp-info">
                <h3>${job.company} <span class="${badgeClass}">[${job.outreach_priority}]</span> ${emailBadge}</h3>
                <div class="opp-meta">${job.job_title} | Score: ${job.relevance_score}/100</div>
                <div class="opp-reason">> ${job.why_relevant || 'Matching skills'}</div>
            </div>
            <div class="opp-actions">
                <button class="btn btn-danger btn-action" onclick="removeJob(${job.id})">[X]</button>
            </div>
        `;
        container.appendChild(card);
    });
}

async function removeJob(id) {
    await fetch('/api/opportunities/remove', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id})
    });
    loadDashboard();
}

document.getElementById('btn-approve-all').addEventListener('click', async () => {
    try {
        // Re-fetch the batch and approve only 'new' status jobs
        const batchRes = await fetch('/api/dashboard/daily-batch');
        if (!batchRes.ok) throw new Error(`Batch fetch failed: ${batchRes.status}`);
        const batch = await batchRes.json();
        // Client-side guard: only approve jobs with 'new' status
        const ids = batch.filter(j => j.status === 'new' || j.status === undefined).map(j => j.id);
        
        if (ids.length > 0) {
            showLoader("APPROVING BATCH...");
            const approveRes = await fetch('/api/opportunities/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ids})
            });
            if (!approveRes.ok) throw new Error(`Approve failed: ${approveRes.status}`);
            hideLoader();
            loadDashboard();
        } else {
            alert('No new jobs to approve.');
        }
    } catch (e) {
        console.error('Approve-all error:', e);
        hideLoader();
        alert('Error approving batch: ' + e.message);
    }
});

// ==========================================
// MODULE: SCRAPE
// ==========================================
document.getElementById('btn-nav-scrape').addEventListener('click', () => {
    document.querySelector('[data-nav="scrape"]').click();
});

document.getElementById('btn-start-scrape').addEventListener('click', async () => {
    const prompt = document.getElementById('scrape-prompt').value;
    if(!prompt) return;
    
    showLoader("SCRAPING NETWORK...");
    
    // Start background scrape
    await fetch('/api/scrape/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt})
    });
    
    // We poll briefly just to see when it finishes, but SSE logs keep user informed.
    // In a real app we'd have a websocket event for 'scrape_complete'. 
    // Here we'll just hide loader after 90 seconds or let user close it.
    // For this prototype, we'll wait for a specific log line indicating completion.
    const checkInterval = setInterval(async () => {
        if(loaderLog.textContent.includes('Search complete')) {
            clearInterval(checkInterval);
            setTimeout(() => {
                hideLoader();
                document.getElementById('scrape-prompt').value = '';
                document.querySelector('[data-nav="dashboard"]').click();
            }, 3000);
        }
    }, 2000);
});

// ==========================================
// MODULE: SCHEDULE
// ==========================================
const schedModal = document.getElementById('modal-schedule');
document.getElementById('btn-open-schedule').addEventListener('click', () => schedModal.classList.remove('hidden'));
document.getElementById('btn-close-schedule').addEventListener('click', () => schedModal.classList.add('hidden'));
// Manual Queue button
document.getElementById('btn-manual-queue').addEventListener('click', async () => {
    showLoader("LOADING MANUAL QUEUE...");
    const res = await fetch('/api/opportunities/manual-queue');
    const jobs = await res.json();
    hideLoader();
    
    if (jobs.length === 0) {
        alert("No jobs in manual queue. All approved jobs have email addresses.");
        return;
    }
    
    // Inject these into the outreach queue (user must supply email for each)
    outreachQueue = jobs.map(j => ({ ...j, _manual: true }));
    processNextOutreach();
});


document.getElementById('btn-generate-batch').addEventListener('click', async () => {
    const type = document.getElementById('sched-type').value;
    const size = parseInt(document.getElementById('sched-size').value);
    const freshness = parseInt(document.getElementById('sched-freshness').value);
    
    schedModal.classList.add('hidden');
    showLoader("ASSEMBLING BATCH...");
    
    await fetch('/api/schedule/generate-batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type, size, freshness_days: freshness})
    });
    
    setTimeout(() => {
        hideLoader();
        loadDashboard();
    }, 1500);
});

// ==========================================
// MODULE: OUTREACH (Semi-Manual)
// ==========================================
const outreachModal = document.getElementById('modal-outreach');
let outreachQueue = [];
let currentOutreachId = null;

document.getElementById('btn-launch-outreach').addEventListener('click', async () => {
    showLoader("FETCHING APPROVED BATCH...");
    const res = await fetch('/api/opportunities/approved');
    const jobs = await res.json();
    hideLoader();
    
    if (jobs.length === 0) {
        alert("No approved jobs ready for outreach. Please approve a batch first.");
        return;
    }
    
    outreachQueue = jobs;
    processNextOutreach();
});

async function processNextOutreach() {
    if (outreachQueue.length === 0) {
        outreachModal.classList.add('hidden');
        loadDashboard();
        alert("Outreach batch complete!");
        return;
    }
    
    const job = outreachQueue.shift();
    currentOutreachId = job.id;
    
    // Reset UI
    outreachModal.classList.remove('hidden');
    document.getElementById('outreach-company').textContent = job.company + ' | ' + job.job_title;
    document.getElementById('outreach-email').value = '';
    document.getElementById('outreach-name').value = '';
    document.getElementById('outreach-subject').value = '';
    document.getElementById('outreach-body').value = '';
    document.getElementById('outreach-resume').textContent = '';
    document.getElementById('outreach-manual-email').value = '';
    
    // Show manual email row for email_failed jobs
    if (job._manual || job.email_hunt_status === 'email_failed') {
        document.getElementById('manual-email-row').classList.remove('hidden');
        document.getElementById('outreach-email').closest('div').style.opacity = '0.4';
    } else {
        document.getElementById('manual-email-row').classList.add('hidden');
        document.getElementById('outreach-email').closest('div').style.opacity = '1';
    }
    
    // Show spinner inside modal, dim fields
    document.getElementById('outreach-loader').classList.remove('hidden');
    document.getElementById('outreach-fields').style.opacity = '0.3';
    document.getElementById('btn-send-outreach').disabled = true;
    
    // Call Prepare endpoint (this takes ~5-10s)
    let data;
    try {
        const res = await fetch(`/api/outreach/prepare/${job.id}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Prepare request failed: ${res.status}`);
        data = await res.json();
    } catch (e) {
        // Network/server error — restore UI then skip to next job
        document.getElementById('outreach-loader').classList.add('hidden');
        document.getElementById('outreach-fields').style.opacity = '1';
        document.getElementById('btn-send-outreach').disabled = false;
        console.error('Prepare fetch error:', e);
        alert('Error preparing job (network/server): ' + e.message + '\nSkipping to next.');
        processNextOutreach();
        return;
    }
    
    // Hide spinner, restore fields
    document.getElementById('outreach-loader').classList.add('hidden');
    document.getElementById('outreach-fields').style.opacity = '1';
    document.getElementById('btn-send-outreach').disabled = false;
    
    if (data.error) {
        // API returned a logical error — skip to next instead of leaving modal empty
        alert('Error preparing: ' + data.error + '\nSkipping to next.');
        processNextOutreach();
        return;
    }
    
    document.getElementById('outreach-email').value = data.recruiter_email || '';
    document.getElementById('outreach-name').value = data.recruiter_name || '';
    document.getElementById('outreach-subject').value = data.subject || '';
    document.getElementById('outreach-body').value = data.body || '';
    
    if (data.resume_filename && data.resume_filename !== "Resume not ready yet") {
        document.getElementById('outreach-resume').textContent = data.resume_filename;
    } else {
        document.getElementById('outreach-resume').textContent = 'Will be generated upon sending...';
    }
}

document.getElementById('btn-skip-outreach').addEventListener('click', () => {
    processNextOutreach();
});

document.getElementById('btn-send-outreach').addEventListener('click', async () => {
    const email = document.getElementById('outreach-email').value;
    const manualEmail = document.getElementById('outreach-manual-email').value;
    const subject = document.getElementById('outreach-subject').value;
    const body = document.getElementById('outreach-body').value;
    
    const finalEmail = manualEmail.trim() || email.trim();
    if (!finalEmail || !finalEmail.includes('@')) {
        alert("Please provide a valid email.");
        return;
    }
    
    document.getElementById('btn-send-outreach').textContent = "SENDING...";
    document.getElementById('btn-send-outreach').disabled = true;
    
    const res = await fetch(`/api/outreach/send/${currentOutreachId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ subject, body, manual_email: manualEmail.trim() })
    });
    
    const data = await res.json();
    if(data.error) {
        alert("Error: " + data.error);
        document.getElementById('btn-send-outreach').textContent = "[ SEND EMAIL ]";
        document.getElementById('btn-send-outreach').disabled = false;
    } else {
        document.getElementById('btn-send-outreach').textContent = "[ SEND EMAIL ]";
        document.getElementById('btn-send-outreach').disabled = false;
        processNextOutreach();
    }
});

// ==========================================
// MODULE: ANALYTICS
// ==========================================
async function loadAnalytics() {
    const container = document.getElementById('analytics-content');
    try {
        const res = await fetch('/api/analytics');
        if (!res.ok) throw new Error(`Analytics fetch failed: ${res.status}`);
        const data = await res.json();
        
        // Null-safe field access
        const topCategories = data.top_categories && typeof data.top_categories === 'object' ? data.top_categories : {};
        const topAngles = Array.isArray(data.top_angles) ? data.top_angles : [];
        
        let html = `
            <div class="stat-block">
                <h3>GLOBAL METRICS</h3>
                <div class="stat-row"><span>OPPORTUNITIES FOUND</span> <span class="badge-med">${data.opportunities_found ?? 0}</span></div>
                <div class="stat-row"><span>OUTREACH SENT</span> <span class="badge-med">${data.outreach_sent ?? 0}</span></div>
                <div class="stat-row"><span>REPLIES RECEIVED</span> <span class="badge-med">${data.replies_received ?? 0}</span></div>
                <div class="stat-row"><span>POSITIVE REPLIES</span> <span class="badge-high">${data.positive_replies ?? 0}</span></div>
                <div class="stat-row"><span>INTERVIEWS BOOKED</span> <span class="badge-high">${data.interviews_booked ?? 0}</span></div>
            </div>
            
            <div class="stat-block">
                <h3>TOP CATEGORIES</h3>
                <div class="bar-chart">
        `;
        
        const catValues = Object.values(topCategories);
        // Math.max with empty array yields -Infinity; fall back to 1 to avoid division by zero
        const maxCat = catValues.length > 0 ? Math.max(...catValues) : 1;
        if (catValues.length === 0) {
            html += `<div class="dim-text">No category data yet.</div>`;
        } else {
            for (const [cat, val] of Object.entries(topCategories)) {
                const pct = (val / maxCat) * 100;
                html += `
                    <div class="bar-row">
                        <div class="bar-label">${cat.toUpperCase()}</div>
                        <div class="bar-track"><div class="bar-fill" style="width: ${pct}%"></div></div>
                    </div>
                `;
            }
        }
        
        html += `
                </div>
            </div>
            
            <div class="stat-block" style="grid-column: 1 / -1">
                <h3>TOP PERFORMING ANGLES</h3>
        `;
        
        if (topAngles.length === 0) {
            html += `<div class="dim-text">No angle data yet.</div>`;
        } else {
            topAngles.forEach(angle => {
                const type = angle && angle.type ? angle.type.toUpperCase() : 'UNKNOWN';
                const rate = angle && angle.response_rate !== undefined ? angle.response_rate : 'N/A';
                html += `<div class="stat-row"><span>> ${type}</span> <span class="badge-high">${rate}</span></div>`;
            });
        }
        
        html += `</div>`;
        container.innerHTML = html;
    } catch (e) {
        console.error('loadAnalytics error:', e);
        container.innerHTML = `<div class="dim-text">Failed to load analytics: ${e.message}</div>`;
    }
}

// Init
loadDashboard();
