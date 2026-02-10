/* NetworkTap - Zeek Log Browser Page */

const Zeek = (() => {
    let currentLogType = 'conn';
    let currentPage = 1;
    let perPage = 50;
    let filters = {};
    let expandedRows = new Set();

    async function render(container) {
        container.innerHTML = `
            <div class="card" style="margin-bottom:16px">
                <div class="tabs" id="zeek-tabs">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <div class="filter-panel" id="filter-panel">
                <div class="filter-panel-header" onclick="Zeek.toggleFilter()">
                    <h3>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                        </svg>
                        Filters
                    </h3>
                    <svg class="filter-panel-toggle" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </div>
                <div class="filter-row">
                    <div class="filter-group">
                        <label>IP Address</label>
                        <input type="text" id="filter-ip" placeholder="Any IP...">
                    </div>
                    <div class="filter-group">
                        <label>Port</label>
                        <input type="number" id="filter-port" placeholder="Any port...">
                    </div>
                    <div class="filter-group">
                        <label>Protocol</label>
                        <select id="filter-proto">
                            <option value="">Any</option>
                            <option value="tcp">TCP</option>
                            <option value="udp">UDP</option>
                            <option value="icmp">ICMP</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Time Range</label>
                        <select id="filter-hours">
                            <option value="">All</option>
                            <option value="1">Last hour</option>
                            <option value="6">Last 6 hours</option>
                            <option value="24" selected>Last 24 hours</option>
                            <option value="72">Last 3 days</option>
                            <option value="168">Last week</option>
                        </select>
                    </div>
                    <div class="filter-group" style="flex:2">
                        <label>Search</label>
                        <input type="text" id="filter-search" placeholder="Search in logs...">
                    </div>
                    <div class="filter-group" style="flex:0">
                        <label>&nbsp;</label>
                        <button class="btn btn-primary" onclick="Zeek.applyFilters()">Apply</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title" id="log-title">Connection Logs</span>
                    <div class="items-per-page">
                        <span>Show</span>
                        <select id="per-page-select" onchange="Zeek.changePerPage(this.value)">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                        </select>
                        <span>entries</span>
                    </div>
                </div>
                <div class="table-wrapper" id="log-table">
                    ${skeletonTable(10, 6)}
                </div>
                <div id="pagination"></div>
            </div>
        `;

        // Add filter input listeners
        const debouncedApply = debounce(() => applyFilters(), 500);
        document.getElementById('filter-ip').addEventListener('input', debouncedApply);
        document.getElementById('filter-port').addEventListener('input', debouncedApply);
        document.getElementById('filter-proto').addEventListener('change', debouncedApply);
        document.getElementById('filter-hours').addEventListener('change', debouncedApply);
        document.getElementById('filter-search').addEventListener('input', debouncedApply);

        await loadLogTypes();
        await loadLogs();
    }

    async function loadLogTypes() {
        try {
            const data = await api('/api/zeek/logs');
            const tabsEl = document.getElementById('zeek-tabs');

            tabsEl.innerHTML = data.logs.map(log => `
                <div class="tab ${log.type === currentLogType ? 'active' : ''} ${!log.available ? 'disabled' : ''}"
                     data-type="${log.type}"
                     onclick="${log.available ? `Zeek.switchLogType('${log.type}')` : ''}">
                    ${log.display}
                    ${log.available ? `<span class="tab-count">${formatCount(log.estimated_count)}</span>` : ''}
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load log types:', e);
        }
    }

    async function loadLogs() {
        const tableEl = document.getElementById('log-table');
        tableEl.innerHTML = skeletonTable(10, 6);

        try {
            const params = new URLSearchParams({
                page: currentPage,
                per_page: perPage,
            });

            if (filters.ip) params.append('ip', filters.ip);
            if (filters.port) params.append('port', filters.port);
            if (filters.proto) params.append('proto', filters.proto);
            if (filters.search) params.append('search', filters.search);
            if (filters.hours) params.append('hours', filters.hours);

            const data = await api(`/api/zeek/logs/${currentLogType}?${params}`);

            renderTable(data);
            renderPagination(
                document.getElementById('pagination'),
                data.page,
                data.total_pages,
                (page) => { currentPage = page; loadLogs(); }
            );

            // Update title
            const titles = {
                conn: 'Connection Logs',
                dns: 'DNS Queries',
                http: 'HTTP Requests',
                ssl: 'SSL/TLS Connections',
                files: 'File Activity',
                notice: 'Notices',
                weird: 'Weird Events',
            };
            document.getElementById('log-title').textContent =
                `${titles[currentLogType] || 'Logs'} (${data.total.toLocaleString()} entries)`;

        } catch (e) {
            tableEl.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <h3>Failed to load logs</h3>
                    <p>${escapeHtml(e.message)}</p>
                </div>
            `;
        }
    }

    function renderTable(data) {
        const tableEl = document.getElementById('log-table');

        if (!data.entries || data.entries.length === 0) {
            tableEl.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <h3>No log entries found</h3>
                    <p>Try adjusting your filters or check if Zeek is running</p>
                </div>
            `;
            return;
        }

        // Different table layouts for different log types
        const renderers = {
            conn: renderConnTable,
            dns: renderDnsTable,
            http: renderHttpTable,
            ssl: renderSslTable,
            files: renderFilesTable,
            notice: renderNoticeTable,
            weird: renderWeirdTable,
        };

        const renderer = renderers[currentLogType] || renderGenericTable;
        tableEl.innerHTML = renderer(data.entries);
    }

    function renderConnTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Destination</th>
                        <th>Proto</th>
                        <th>Service</th>
                        <th>Duration</th>
                        <th>Bytes</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e.uid) ? 'expanded' : ''}"
                            onclick="Zeek.toggleRow('${e.uid}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td class="ip-cell">${escapeHtml(e['id.orig_h'] || '')}<span class="port-cell">:${e['id.orig_p'] || ''}</span></td>
                            <td class="ip-cell">${escapeHtml(e['id.resp_h'] || '')}<span class="port-cell">:${e['id.resp_p'] || ''}</span></td>
                            <td><span class="protocol-badge">${escapeHtml(e.proto || '')}</span></td>
                            <td>${e.service ? `<span class="service-badge">${escapeHtml(e.service)}</span>` : '-'}</td>
                            <td class="duration-cell">${formatDuration(e.duration)}</td>
                            <td class="bytes-cell">${formatBytes((e.orig_bytes || 0) + (e.resp_bytes || 0))}</td>
                        </tr>
                        ${expandedRows.has(e.uid) ? renderConnDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderConnDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="8">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">UID</span>
                                <span class="zeek-detail-value">${escapeHtml(e.uid || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Connection State</span>
                                <span class="zeek-detail-value">${escapeHtml(e.conn_state || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">History</span>
                                <span class="zeek-detail-value">${escapeHtml(e.history || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Bytes Sent</span>
                                <span class="zeek-detail-value">${formatBytes(e.orig_bytes || 0)}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Bytes Received</span>
                                <span class="zeek-detail-value">${formatBytes(e.resp_bytes || 0)}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Packets Sent</span>
                                <span class="zeek-detail-value">${(e.orig_pkts || 0).toLocaleString()}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Packets Received</span>
                                <span class="zeek-detail-value">${(e.resp_pkts || 0).toLocaleString()}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Missed Bytes</span>
                                <span class="zeek-detail-value">${formatBytes(e.missed_bytes || 0)}</span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderDnsTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Query</th>
                        <th>Type</th>
                        <th>Response</th>
                        <th>Answers</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e.uid) ? 'expanded' : ''}"
                            onclick="Zeek.toggleRow('${e.uid}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td class="ip-cell">${escapeHtml(e['id.orig_h'] || '')}</td>
                            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.query || '-')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.qtype_name || e.qtype || '-')}</span></td>
                            <td>${getRcodeDisplay(e.rcode_name || e.rcode)}</td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${formatAnswers(e.answers)}</td>
                        </tr>
                        ${expandedRows.has(e.uid) ? renderDnsDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderDnsDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="7">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">UID</span>
                                <span class="zeek-detail-value">${escapeHtml(e.uid || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Server</span>
                                <span class="zeek-detail-value">${escapeHtml(e['id.resp_h'] || '-')}:${e['id.resp_p'] || ''}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Protocol</span>
                                <span class="zeek-detail-value">${escapeHtml(e.proto || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Query Class</span>
                                <span class="zeek-detail-value">${escapeHtml(e.qclass_name || e.qclass || '-')}</span>
                            </div>
                            <div class="zeek-detail-item" style="grid-column:span 2">
                                <span class="zeek-detail-label">Full Answers</span>
                                <span class="zeek-detail-value">${escapeHtml(Array.isArray(e.answers) ? e.answers.join(', ') : e.answers || '-')}</span>
                            </div>
                            <div class="zeek-detail-item" style="grid-column:span 2">
                                <span class="zeek-detail-label">TTLs</span>
                                <span class="zeek-detail-value">${escapeHtml(Array.isArray(e.TTLs) ? e.TTLs.join(', ') : e.TTLs || '-')}</span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderHttpTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Method</th>
                        <th>Host</th>
                        <th>URI</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e.uid) ? 'expanded' : ''}"
                            onclick="Zeek.toggleRow('${e.uid}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td class="ip-cell">${escapeHtml(e['id.orig_h'] || '')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.method || '-')}</span></td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.host || '-')}</td>
                            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.uri || '-')}</td>
                            <td>${getStatusDisplay(e.status_code)}</td>
                        </tr>
                        ${expandedRows.has(e.uid) ? renderHttpDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderHttpDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="7">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">UID</span>
                                <span class="zeek-detail-value">${escapeHtml(e.uid || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Destination</span>
                                <span class="zeek-detail-value">${escapeHtml(e['id.resp_h'] || '-')}:${e['id.resp_p'] || ''}</span>
                            </div>
                            <div class="zeek-detail-item" style="grid-column:span 2">
                                <span class="zeek-detail-label">User Agent</span>
                                <span class="zeek-detail-value">${escapeHtml(e.user_agent || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">MIME Type</span>
                                <span class="zeek-detail-value">${escapeHtml(Array.isArray(e.resp_mime_types) ? e.resp_mime_types.join(', ') : e.resp_mime_types || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Response Length</span>
                                <span class="zeek-detail-value">${formatBytes(e.response_body_len || 0)}</span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderSslTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Server Name</th>
                        <th>Version</th>
                        <th>Cipher</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e.uid) ? 'expanded' : ''}"
                            onclick="Zeek.toggleRow('${e.uid}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td class="ip-cell">${escapeHtml(e['id.orig_h'] || '')}</td>
                            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.server_name || '-')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.version || '-')}</span></td>
                            <td style="font-size:0.75rem">${escapeHtml(e.cipher || '-').substring(0, 30)}${(e.cipher || '').length > 30 ? '...' : ''}</td>
                            <td>${e.established ? '<span style="color:var(--green)">Established</span>' : '<span style="color:var(--text-muted)">-</span>'}</td>
                        </tr>
                        ${expandedRows.has(e.uid) ? renderSslDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderSslDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="7">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">UID</span>
                                <span class="zeek-detail-value">${escapeHtml(e.uid || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">Destination</span>
                                <span class="zeek-detail-value">${escapeHtml(e['id.resp_h'] || '-')}:${e['id.resp_p'] || ''}</span>
                            </div>
                            <div class="zeek-detail-item" style="grid-column:span 2">
                                <span class="zeek-detail-label">Full Cipher Suite</span>
                                <span class="zeek-detail-value">${escapeHtml(e.cipher || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">JA3</span>
                                <span class="zeek-detail-value">${escapeHtml(e.ja3 || '-')}</span>
                            </div>
                            <div class="zeek-detail-item">
                                <span class="zeek-detail-label">JA3S</span>
                                <span class="zeek-detail-value">${escapeHtml(e.ja3s || '-')}</span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderFilesTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Source</th>
                        <th>MIME Type</th>
                        <th>Filename</th>
                        <th>Size</th>
                        <th>MD5</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td><span class="service-badge">${escapeHtml(e.source || '-')}</span></td>
                            <td>${escapeHtml(e.mime_type || '-')}</td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.filename || '-')}</td>
                            <td class="bytes-cell">${formatBytes(e.total_bytes || 0)}</td>
                            <td style="font-family:monospace;font-size:0.7rem">${escapeHtml((e.md5 || '-').substring(0, 12))}...</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderNoticeTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Note</th>
                        <th>Message</th>
                        <th>Source</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td><span class="severity severity-2">${escapeHtml(e.note || '-')}</span></td>
                            <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.msg || '-')}</td>
                            <td class="ip-cell">${escapeHtml(e.src || '-')}</td>
                            <td>${escapeHtml(Array.isArray(e.actions) ? e.actions.join(', ') : e.actions || '-')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderWeirdTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Name</th>
                        <th>Additional Info</th>
                        <th>Source</th>
                        <th>Notice</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            <td class="timestamp">${formatTime(e.ts)}</td>
                            <td><span class="severity severity-3">${escapeHtml(e.name || '-')}</span></td>
                            <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.addl || '-')}</td>
                            <td class="ip-cell">${escapeHtml(e['id.orig_h'] || '-')}</td>
                            <td>${e.notice ? '<span style="color:var(--yellow)">Yes</span>' : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderGenericTable(entries) {
        if (entries.length === 0) return '<p>No entries</p>';

        const keys = Object.keys(entries[0]).filter(k => !k.startsWith('_'));
        const displayKeys = keys.slice(0, 8);

        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        ${displayKeys.map(k => `<th>${escapeHtml(k)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            ${displayKeys.map(k => `<td>${escapeHtml(String(e[k] || '-').substring(0, 50))}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    // Helper functions
    function formatCount(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return n;
    }

    function formatAnswers(answers) {
        if (!answers) return '-';
        if (Array.isArray(answers)) {
            return answers.slice(0, 2).join(', ') + (answers.length > 2 ? ` +${answers.length - 2}` : '');
        }
        return String(answers);
    }

    function getRcodeDisplay(rcode) {
        const codes = {
            'NOERROR': '<span style="color:var(--green)">OK</span>',
            'NXDOMAIN': '<span style="color:var(--orange)">NXDOMAIN</span>',
            'SERVFAIL': '<span style="color:var(--red)">SERVFAIL</span>',
            'REFUSED': '<span style="color:var(--red)">REFUSED</span>',
            '0': '<span style="color:var(--green)">OK</span>',
            '3': '<span style="color:var(--orange)">NXDOMAIN</span>',
        };
        return codes[rcode] || escapeHtml(rcode || '-');
    }

    function getStatusDisplay(status) {
        if (!status) return '-';
        const s = parseInt(status);
        if (s >= 200 && s < 300) return `<span style="color:var(--green)">${s}</span>`;
        if (s >= 300 && s < 400) return `<span style="color:var(--blue)">${s}</span>`;
        if (s >= 400 && s < 500) return `<span style="color:var(--orange)">${s}</span>`;
        if (s >= 500) return `<span style="color:var(--red)">${s}</span>`;
        return s;
    }

    function switchLogType(type) {
        currentLogType = type;
        currentPage = 1;
        expandedRows.clear();

        // Update tab active state
        document.querySelectorAll('#zeek-tabs .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.type === type);
        });

        loadLogs();
    }

    function toggleRow(uid) {
        if (expandedRows.has(uid)) {
            expandedRows.delete(uid);
        } else {
            expandedRows.add(uid);
        }
        loadLogs();
    }

    function toggleFilter() {
        document.getElementById('filter-panel').classList.toggle('collapsed');
    }

    function applyFilters() {
        filters = {
            ip: document.getElementById('filter-ip').value.trim(),
            port: document.getElementById('filter-port').value.trim() || null,
            proto: document.getElementById('filter-proto').value,
            search: document.getElementById('filter-search').value.trim(),
            hours: document.getElementById('filter-hours').value || null,
        };

        // Remove empty filters
        Object.keys(filters).forEach(k => {
            if (!filters[k]) delete filters[k];
        });

        currentPage = 1;
        loadLogs();
    }

    function changePerPage(value) {
        perPage = parseInt(value);
        currentPage = 1;
        loadLogs();
    }

    return {
        render,
        switchLogType,
        toggleRow,
        toggleFilter,
        applyFilters,
        changePerPage,
    };
})();
