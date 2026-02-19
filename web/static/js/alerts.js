/* NetworkTap - IDS Alerts View */

const Alerts = (() => {
    let autoScroll = true;
    let currentSource = 'all';
    let alertCount = 0;
    let filterTimeout = null;

    async function render(container) {
        container.innerHTML = `
            <div class="alerts-controls">
                <div class="alerts-toolbar">
                    <div class="source-tabs">
                        <button class="source-tab active" data-source="all">
                            <span class="source-tab-label">All Sources</span>
                        </button>
                        <button class="source-tab" data-source="suricata">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                            </svg>
                            <span class="source-tab-label">Suricata</span>
                        </button>
                        <button class="source-tab" data-source="zeek">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="2" y1="12" x2="22" y2="12"/>
                                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                            </svg>
                            <span class="source-tab-label">Zeek</span>
                        </button>
                    </div>
                    <div class="alerts-actions">
                        <div class="search-box">
                            <svg class="search-box-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="11" cy="11" r="8"/>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            </svg>
                            <input type="text" id="alert-filter" placeholder="Filter alerts...">
                        </div>
                        <label class="auto-scroll-toggle">
                            <input type="checkbox" id="auto-scroll" checked>
                            <span>Auto-scroll</span>
                        </label>
                        <button class="btn btn-secondary" id="btn-refresh-alerts">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="23 4 23 10 17 10"/>
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>
            </div>

            <div class="card alerts-card">
                <div class="card-header">
                    <span class="card-title">IDS Alerts</span>
                    <span class="alerts-count" id="alert-total"></span>
                </div>
                <div class="table-wrapper alerts-table-wrapper">
                    <table class="alerts-table">
                        <thead>
                            <tr>
                                <th style="width:70px">Severity</th>
                                <th style="width:90px">Time</th>
                                <th style="width:80px">Source</th>
                                <th>Signature</th>
                                <th style="width:140px">Src IP</th>
                                <th style="width:140px">Dst IP</th>
                                <th style="width:60px">Proto</th>
                            </tr>
                        </thead>
                        <tbody id="alert-table-body">
                        </tbody>
                    </table>
                </div>
                <div id="alert-empty" class="empty-state" hidden>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    <h3>No alerts detected</h3>
                    <p>Alerts from Suricata and Zeek will appear here in real-time</p>
                </div>
            </div>
        `;

        // Event listeners
        document.getElementById('auto-scroll').addEventListener('change', e => {
            autoScroll = e.target.checked;
        });

        document.getElementById('btn-refresh-alerts').addEventListener('click', refresh);

        document.querySelectorAll('.source-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.source-tab').forEach(b => {
                    b.classList.remove('active');
                });
                btn.classList.add('active');
                currentSource = btn.dataset.source;
                refresh();
            });
        });

        document.getElementById('alert-filter').addEventListener('input', () => {
            // Debounce filter input
            if (filterTimeout) clearTimeout(filterTimeout);
            filterTimeout = setTimeout(() => filterTable(), 300);
        });

        // Listen for live alerts via WebSocket
        WS.onAlert = (alert) => {
            addLiveAlert(alert);
        };

        await refresh();
        App.setRefresh(refresh, 15000);
    }

    async function refresh() {
        try {
            let data;
            if (currentSource === 'all') {
                data = await api('/api/alerts/all?limit=200');
            } else if (currentSource === 'suricata') {
                data = await api('/api/alerts/suricata?limit=200');
            } else {
                data = await api('/api/alerts/zeek?limit=200');
            }

            renderAlerts(data.alerts || []);
        } catch (e) {
            // retry
        }
    }

    function renderAlerts(alerts) {
        const tbody = document.getElementById('alert-table-body');
        const empty = document.getElementById('alert-empty');
        if (!tbody) return;

        if (alerts.length === 0) {
            tbody.innerHTML = '';
            if (empty) empty.hidden = false;
            return;
        }

        if (empty) empty.hidden = true;
        alertCount = alerts.length;
        const totalEl = document.getElementById('alert-total');
        if (totalEl) totalEl.textContent = `(${alertCount})`;

        tbody.innerHTML = alerts.map(a => alertRow(a)).join('');
        filterTable();

        if (autoScroll) {
            tbody.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
    }

    function addLiveAlert(alert) {
        if (currentSource !== 'all' && currentSource !== alert.source) return;

        const tbody = document.getElementById('alert-table-body');
        if (!tbody) return;

        const row = document.createElement('tr');
        row.innerHTML = alertRowInner(alert);
        row.style.animation = 'slideIn 0.3s ease';

        // Add to top
        if (tbody.firstChild) {
            tbody.insertBefore(row, tbody.firstChild);
        } else {
            tbody.appendChild(row);
        }

        // Limit visible rows
        while (tbody.children.length > 300) {
            tbody.removeChild(tbody.lastChild);
        }

        alertCount++;
        const totalEl = document.getElementById('alert-total');
        if (totalEl) totalEl.textContent = `(${alertCount})`;

        const emptyEl = document.getElementById('alert-empty');
        if (emptyEl) emptyEl.hidden = true;

        // Update badge
        updateBadge();

        filterTable();
    }

    function alertRow(a) {
        return `<tr>${alertRowInner(a)}</tr>`;
    }

    function alertRowInner(a) {
        const srcPort = a.src_port ? `<span class="port-num">:${a.src_port}</span>` : '';
        const destPort = a.dest_port ? `<span class="port-num">:${a.dest_port}</span>` : '';
        return `
            <td><span class="severity severity-${a.severity || 3}">${severityLabel(a.severity)}</span></td>
            <td class="timestamp">${formatTime(a.timestamp)}</td>
            <td><span class="source-badge source-${escapeHtml(a.source || 'unknown')}">${escapeHtml(a.source || '')}</span></td>
            <td class="signature-cell">${escapeHtml(a.signature || a.message || '')}</td>
            <td class="ip-cell">${escapeHtml(a.src_ip || '')}${srcPort}</td>
            <td class="ip-cell">${escapeHtml(a.dest_ip || '')}${destPort}</td>
            <td class="proto-cell">${escapeHtml(a.proto || '')}</td>
        `;
    }

    function filterTable() {
        const filter = (document.getElementById('alert-filter')?.value || '').toLowerCase();
        const rows = document.querySelectorAll('#alert-table-body tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    }

    function severityLabel(s) {
        switch (s) {
            case 1: return 'CRIT';
            case 2: return 'HIGH';
            case 3: return 'MED';
            default: return 'LOW';
        }
    }

    function updateBadge() {
        const badge = document.getElementById('alert-badge');
        if (badge) {
            const count = parseInt(badge.textContent || '0') + 1;
            badge.textContent = count > 99 ? '99+' : count;
            badge.hidden = false;
        }
    }

    function cleanup() {
        WS.onAlert = null;
        // Clear filter timeout to prevent memory leaks
        if (filterTimeout) {
            clearTimeout(filterTimeout);
            filterTimeout = null;
        }
    }

    return { render, cleanup };
})();
