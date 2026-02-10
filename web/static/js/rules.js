/* NetworkTap - Suricata Rules Management Page */

const Rules = (() => {
    let searchTerm = '';
    let selectedClasstype = '';
    let enabledOnly = false;

    async function render(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Suricata Rule Statistics</span>
                    <button class="btn btn-primary btn-sm" id="btn-reload-rules">Reload Suricata</button>
                </div>
                <div class="stat-grid" id="rule-stats">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <div class="card" style="margin-top:20px">
                <div class="card-header">
                    <span class="card-title">Rule Browser</span>
                </div>
                <div class="rule-filters" style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap">
                    <input type="text" id="rule-search" placeholder="Search rules..." style="flex:1;min-width:200px">
                    <select id="rule-classtype" style="min-width:150px">
                        <option value="">All classtypes</option>
                    </select>
                    <label style="display:flex;align-items:center;gap:6px;color:var(--text-secondary)">
                        <input type="checkbox" id="rule-enabled-only"> Enabled only
                    </label>
                    <button class="btn btn-secondary btn-sm" id="btn-search-rules">Search</button>
                </div>
                <div id="rules-list">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <!-- Rule Detail Modal -->
            <div class="modal" id="rule-modal" style="display:none">
                <div class="modal-content" style="max-width:700px">
                    <div class="modal-header">
                        <span class="modal-title">Rule Details</span>
                        <button class="modal-close" id="close-rule-modal">&times;</button>
                    </div>
                    <div id="rule-detail-content">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>
        `;

        loadStats();
        loadClasstypes();
        loadRules();
        setupEventListeners();
    }

    function setupEventListeners() {
        document.getElementById('btn-reload-rules').addEventListener('click', reloadSuricata);
        document.getElementById('btn-search-rules').addEventListener('click', loadRules);
        document.getElementById('rule-search').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadRules();
        });
        document.getElementById('rule-classtype').addEventListener('change', loadRules);
        document.getElementById('rule-enabled-only').addEventListener('change', loadRules);
        document.getElementById('close-rule-modal').addEventListener('click', () => {
            document.getElementById('rule-modal').style.display = 'none';
        });
    }

    async function loadStats() {
        try {
            const data = await api('/api/rules/stats');
            
            document.getElementById('rule-stats').innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Total Rules</div>
                    <div class="stat-value">${data.total.toLocaleString()}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Enabled</div>
                    <div class="stat-value" style="color:var(--green)">${data.enabled.toLocaleString()}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Disabled</div>
                    <div class="stat-value" style="color:var(--text-muted)">${data.disabled.toLocaleString()}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Categories</div>
                    <div class="stat-value">${Object.keys(data.by_classtype || {}).length}</div>
                </div>
            `;
        } catch (e) {
            document.getElementById('rule-stats').innerHTML = 
                '<p class="form-help" style="color:var(--red)">Failed to load rule statistics</p>';
        }
    }

    async function loadClasstypes() {
        try {
            const data = await api('/api/rules/classtypes');
            const select = document.getElementById('rule-classtype');
            
            data.classtypes.forEach(ct => {
                const option = document.createElement('option');
                option.value = ct;
                option.textContent = ct;
                select.appendChild(option);
            });
        } catch (e) {
            console.error('Failed to load classtypes:', e);
        }
    }

    async function loadRules() {
        searchTerm = document.getElementById('rule-search').value.trim();
        selectedClasstype = document.getElementById('rule-classtype').value;
        enabledOnly = document.getElementById('rule-enabled-only').checked;

        const container = document.getElementById('rules-list');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            let url = '/api/rules/?limit=200';
            if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
            if (selectedClasstype) url += `&classtype=${encodeURIComponent(selectedClasstype)}`;
            if (enabledOnly) url += '&enabled_only=true';

            const data = await api(url);

            if (data.rules.length === 0) {
                container.innerHTML = '<p class="form-help">No rules found matching your criteria</p>';
                return;
            }

            container.innerHTML = `
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>SID</th>
                                <th>Message</th>
                                <th>Classtype</th>
                                <th>Severity</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.rules.map(r => `
                                <tr>
                                    <td style="font-family:monospace">${r.sid}</td>
                                    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(r.msg)}">${escapeHtml(r.msg)}</td>
                                    <td>${escapeHtml(r.classtype) || '-'}</td>
                                    <td><span class="severity severity-${r.severity}">${r.severity}</span></td>
                                    <td>${r.enabled ? '<span style="color:var(--green)">Enabled</span>' : '<span style="color:var(--text-muted)">Disabled</span>'}</td>
                                    <td>
                                        <button class="btn btn-sm btn-secondary" onclick="Rules.viewRule(${r.sid})">View</button>
                                        <button class="btn btn-sm ${r.enabled ? 'btn-danger' : 'btn-primary'}" onclick="Rules.toggleRule(${r.sid}, ${!r.enabled})">${r.enabled ? 'Disable' : 'Enable'}</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <p class="form-help" style="margin-top:12px">Showing ${data.rules.length} of ${data.count} rules</p>
            `;
        } catch (e) {
            container.innerHTML = `<p class="form-help" style="color:var(--red)">Error: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function viewRule(sid) {
        const modal = document.getElementById('rule-modal');
        const content = document.getElementById('rule-detail-content');
        
        modal.style.display = 'flex';
        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const rule = await api(`/api/rules/${sid}`);
            
            content.innerHTML = `
                <div class="form-group">
                    <label class="form-label">SID</label>
                    <input type="text" value="${rule.sid}" readonly style="width:100%">
                </div>
                <div class="form-group">
                    <label class="form-label">Message</label>
                    <input type="text" value="${escapeHtml(rule.msg)}" readonly style="width:100%">
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label class="form-label">Action</label>
                        <input type="text" value="${rule.action}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Classtype</label>
                        <input type="text" value="${escapeHtml(rule.classtype) || 'none'}" readonly style="width:100%">
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label class="form-label">Severity</label>
                        <input type="text" value="${rule.severity}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Status</label>
                        <input type="text" value="${rule.enabled ? 'Enabled' : 'Disabled'}" readonly style="width:100%">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">File</label>
                    <input type="text" value="${escapeHtml(rule.file)} (line ${rule.line})" readonly style="width:100%">
                </div>
                <div class="form-group">
                    <label class="form-label">Raw Rule</label>
                    <textarea readonly style="width:100%;height:100px;font-family:monospace;font-size:0.8rem">${escapeHtml(rule.raw)}</textarea>
                </div>
                <div style="display:flex;gap:12px;margin-top:16px">
                    <button class="btn ${rule.enabled ? 'btn-danger' : 'btn-primary'}" onclick="Rules.toggleRule(${rule.sid}, ${!rule.enabled}); document.getElementById('rule-modal').style.display='none';">
                        ${rule.enabled ? 'Disable Rule' : 'Enable Rule'}
                    </button>
                </div>
            `;
        } catch (e) {
            content.innerHTML = `<p style="color:var(--red)">Error loading rule: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function toggleRule(sid, enabled) {
        try {
            await api(`/api/rules/${sid}/state`, {
                method: 'PUT',
                body: { enabled }
            });
            
            toast(`Rule ${sid} ${enabled ? 'enabled' : 'disabled'}`, 'success');
            loadRules();
            loadStats();
        } catch (e) {
            toast('Failed to update rule: ' + e.message, 'error');
        }
    }

    async function reloadSuricata() {
        if (!confirm('Reload Suricata to apply rule changes? This may briefly interrupt IDS monitoring.')) {
            return;
        }

        try {
            await api('/api/rules/reload', { method: 'POST' });
            toast('Suricata reloaded successfully', 'success');
        } catch (e) {
            toast('Failed to reload Suricata: ' + e.message, 'error');
        }
    }

    return { render, viewRule, toggleRule };
})();
