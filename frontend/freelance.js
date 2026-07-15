document.addEventListener('DOMContentLoaded', () => {
    // Navigation Logic
    const navLinks = document.querySelectorAll('.nav-links a');
    const modules = document.querySelectorAll('.module');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navLinks.forEach(l => l.classList.remove('active'));
            modules.forEach(m => m.classList.remove('active'));
            
            link.classList.add('active');
            const target = link.getAttribute('data-nav');
            const targetModule = document.getElementById(`module-${target}`);
            if (targetModule) {
                targetModule.classList.add('active');
            }
        });
    });

    // State Management
    let currentOpportunities = [];
    let loadTimeoutId = null;
    let scanTimeoutId = null;
    let currentFilter = 'all';
    let currentDays = 3;
    const API_BASE = 'http://localhost:8000/api';

    const btnLoadJson = document.getElementById('btn-load-json');
    const signalList = document.getElementById('signal-list');

    if (btnLoadJson && signalList) {
        btnLoadJson.addEventListener('click', async () => {
            signalList.innerHTML = '<div class="dim-text">Fetching data from API...</div>';
            try {
                const res = await fetch(`${API_BASE}/opportunities`);
                const data = await res.json();
                currentOpportunities = data;
                applyFiltersAndRender();
                fetchStats();
            } catch (err) {
                signalList.innerHTML = `<div class="dim-text" style="color:red">Error fetching data: ${err.message}</div>`;
            }
        });
    }

    // Filters and Toggles Logic
    const filterChips = document.querySelectorAll('.filter-chip');
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    
    filterChips.forEach(chip => {
        chip.addEventListener('click', (e) => {
            filterChips.forEach(c => c.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            applyFiltersAndRender();
        });
    });

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            toggleBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentDays = parseInt(e.target.getAttribute('data-days'), 10);
            applyFiltersAndRender();
        });
    });

    function applyFiltersAndRender() {
        let filtered = currentOpportunities.filter(opp => {
            let matchesFilter = true;
            if (currentFilter === 'high-intent') {
                matchesFilter = opp.confidence === 'high';
            } else if (currentFilter === 'freelance') {
                matchesFilter = opp.opportunity_type === 'freelance';
            }
            let matchesDays = parseInt(opp.days_old, 10) <= currentDays;
            return matchesFilter && matchesDays;
        });
        renderSignals(filtered);
    }

    async function fetchStats() {
        try {
            const res = await fetch(`${API_BASE}/opportunities/stats`);
            const data = await res.json();
            const setStat = (id, value) => {
                const el = document.getElementById(id);
                if (el) el.innerText = value;
            };
            setStat('stat-fresh', data.fresh);
            setStat('stat-high-intent', data.high_intent);
            setStat('stat-contactable', data.contactable);
            setStat('stat-sent', data.pitches_sent);
        } catch (e) {
            console.error("Failed to fetch stats", e);
        }
    }

    // Event Delegation for Pitch Buttons
    if (signalList) {
        signalList.addEventListener('click', (e) => {
            const pitchBtn = e.target.closest('.btn-pitch');
            if (pitchBtn) {
                const index = pitchBtn.getAttribute('data-index');
                if (index !== null && currentOpportunities[index]) {
                    openPitchModal(currentOpportunities[index]);
                }
            }
        });
    }

    function sanitizeHTML(str) {
        if (!str) return '';
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    }

    function renderSignals(data) {
        signalList.innerHTML = '';
        
        if (!data || data.length === 0) {
            signalList.innerHTML = '<div class="dim-text">No opportunities found.</div>';
            return;
        }

        data.forEach((opp, index) => {
            const card = document.createElement('div');
            card.className = 'opp-card';
            
            const platform = sanitizeHTML(opp.platform.toUpperCase());
            const company = sanitizeHTML(opp.company_or_person);
            const type = sanitizeHTML(opp.opportunity_type.toUpperCase());
            const intent = sanitizeHTML(opp.intent_signal);
            const score = sanitizeHTML(opp.outreach_score.toString());
            const contact = sanitizeHTML((opp.contact_path || 'UNKNOWN').toUpperCase());
            const days = sanitizeHTML(opp.days_old.toString());
            const why = sanitizeHTML(opp.why_it_matters);
            const url = encodeURI(opp.source_url);
            
            card.innerHTML = `
                <div class="opp-info">
                    <h3>[${platform}] ${company}</h3>
                    <div class="opp-meta">
                        TYPE: <span class="badge-high">${type}</span> | INTENT: ${intent}
                        <br>SCORE: <span class="badge-med">${score}</span> 
                        <div class="score-bar-container"><div class="score-bar-fill" style="width: ${score}%"></div></div>
                        | CONTACT: ${contact}
                        <br>FRESHNESS: ${days} DAYS OLD
                    </div>
                    <div class="opp-reason">> ${why}</div>
                </div>
                <div class="opp-actions">
                    <a href="${url}" target="_blank" class="btn btn-secondary" rel="noopener noreferrer">[ VIEW ]</a>
                    <button class="btn btn-accent btn-pitch" data-index="${index}">[ PITCH ]</button>
                </div>
            `;
            signalList.appendChild(card);
        });
    }

    // updateStats is replaced by fetchStats() hitting the API.

    // Modal Logic
    const modal = document.getElementById('modal-outreach');
    const btnCancel = document.getElementById('btn-cancel-outreach');
    const btnSend = document.getElementById('btn-send-outreach');
    
    function openPitchModal(opp) {
        if (!modal) return;
        
        const targetEl = document.getElementById('outreach-target');
        const pathEl = document.getElementById('outreach-path');
        const bodyEl = document.getElementById('outreach-body');
        
        if (targetEl) targetEl.innerText = `${opp.company_or_person} | ${opp.platform.toUpperCase()}`;
        if (pathEl) pathEl.value = opp.email || opp.contact_path || '';
        
        if (bodyEl) {
            let pitchCopy = \`Hi \${opp.company_or_person},\n\nSaw your post on \${opp.platform} about needing help with \${opp.opportunity_type}.\n\nI run a specialized agency that does exactly this. Would you be open to a quick chat or audit?\n\nBest,\n[Your Name]\`;
            bodyEl.value = pitchCopy;
        }
        
        modal.classList.remove('hidden');
    }

    if (btnCancel && modal) {
        btnCancel.addEventListener('click', () => modal.classList.add('hidden'));
    }
    
    if (btnSend && modal) {
        btnSend.addEventListener('click', () => {
            modal.classList.add('hidden');
            alert("Pitch queued for sending via Opportunity Engine backend!");
            const sentCount = document.getElementById('stat-sent');
            if (sentCount) sentCount.innerText = parseInt(sentCount.innerText) + 1;
        });
    }

    // Scan Logic
    const btnStartScan = document.getElementById('btn-start-scan');
    const liveLogPanel = document.getElementById('live-log-panel');
    const logContent = document.getElementById('log-content');
    
    if (btnStartScan) {
        btnStartScan.addEventListener('click', async () => {
            if (liveLogPanel) liveLogPanel.classList.remove('hidden');
            if (logContent) logContent.innerHTML = '<div>Initiating trigger request...</div>';
            
            try {
                const res = await fetch(`${API_BASE}/scan/trigger`, { method: 'POST' });
                const data = await res.json();
                
                if (data.job_id) {
                    const evtSource = new EventSource(`${API_BASE}/scan/${data.job_id}/stream`);
                    evtSource.onmessage = (event) => {
                        const payload = JSON.parse(event.data);
                        if (payload.error) {
                            logContent.innerHTML += `<div style="color:red">Error: ${payload.error}</div>`;
                            evtSource.close();
                        } else if (payload.message === "DONE") {
                            logContent.innerHTML += `<div style="color:lime">Pipeline Finished. Loading opportunities...</div>`;
                            evtSource.close();
                            setTimeout(() => {
                                const dashboardNav = document.querySelector('[data-nav="dashboard"]');
                                if (dashboardNav) dashboardNav.click();
                                if (btnLoadJson) btnLoadJson.click();
                            }, 1500);
                        } else {
                            const p = document.createElement('div');
                            p.className = 'log-line';
                            p.innerText = `> ${payload.message}`;
                            logContent.appendChild(p);
                            logContent.scrollTop = logContent.scrollHeight;
                        }
                    };
                    evtSource.onerror = () => {
                        logContent.innerHTML += `<div style="color:red">Connection lost.</div>`;
                        evtSource.close();
                    };
                }
            } catch (err) {
                if (logContent) logContent.innerHTML += `<div style="color:red">Trigger failed: ${err.message}</div>`;
            }
        });
    }
});
