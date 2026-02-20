/* NetworkTap - Suricata EVE Log Browser Page */

const Suricata = (() => {
    let currentEventType = 'alert';
    let currentPage = 1;
    let perPage = 50;
    let filters = {};
    let expandedRows = new Set();

    async function render(container) {
        container.innerHTML = `
            <div class="card" style="margin-bottom:16px">
                <div class="tabs" id="suricata-tabs">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <div class="filter-panel" id="suri-filter-panel">
                <div class="filter-panel-header" onclick="Suricata.toggleFilter()">
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
                        <input type="text" id="suri-filter-ip" placeholder="Any IP...">
                    </div>
                    <div class="filter-group">
                        <label>Port</label>
                        <input type="number" id="suri-filter-port" placeholder="Any port...">
                    </div>
                    <div class="filter-group">
                        <label>Protocol</label>
                        <select id="suri-filter-proto">
                            <option value="">Any</option>
                            <option value="tcp">TCP</option>
                            <option value="udp">UDP</option>
                            <option value="icmp">ICMP</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Time Range</label>
                        <select id="suri-filter-hours">
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
                        <input type="text" id="suri-filter-search" placeholder="Search in logs...">
                    </div>
                    <div class="filter-group" style="flex:0">
                        <label>&nbsp;</label>
                        <button class="btn btn-primary" onclick="Suricata.applyFilters()">Apply</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title" id="suri-log-title">Alerts</span>
                    <div class="items-per-page">
                        <span>Show</span>
                        <select id="suri-per-page" onchange="Suricata.changePerPage(this.value)">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                        </select>
                        <span>entries</span>
                    </div>
                </div>
                <div class="table-wrapper" id="suri-log-table">
                    ${skeletonTable(10, 6)}
                </div>
                <div id="suri-pagination"></div>
            </div>
        `;

        const debouncedApply = debounce(() => applyFilters(), 500);
        document.getElementById('suri-filter-ip').addEventListener('input', debouncedApply);
        document.getElementById('suri-filter-port').addEventListener('input', debouncedApply);
        document.getElementById('suri-filter-proto').addEventListener('change', debouncedApply);
        document.getElementById('suri-filter-hours').addEventListener('change', debouncedApply);
        document.getElementById('suri-filter-search').addEventListener('input', debouncedApply);

        await loadEventTypes();
        await loadEvents();
    }

    async function loadEventTypes() {
        try {
            const data = await api('/api/suricata/events');
            const tabsEl = document.getElementById('suricata-tabs');

            tabsEl.innerHTML = data.events.map(ev => `
                <div class="tab ${ev.type === currentEventType ? 'active' : ''} ${!ev.available ? 'disabled' : ''}"
                     data-type="${ev.type}"
                     onclick="${ev.available ? `Suricata.switchEventType('${ev.type}')` : ''}">
                    ${ev.display}
                    ${ev.available ? `<span class="tab-count">${formatCount(ev.estimated_count)}</span>` : ''}
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load event types:', e);
        }
    }

    async function loadEvents() {
        const tableEl = document.getElementById('suri-log-table');
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

            const data = await api(`/api/suricata/events/${currentEventType}?${params}`);

            renderTable(data);
            renderPagination(
                document.getElementById('suri-pagination'),
                data.page,
                data.total_pages,
                (page) => { currentPage = page; loadEvents(); }
            );

            const titles = {
                alert: 'Alerts',
                dns: 'DNS Events',
                http: 'HTTP Transactions',
                tls: 'TLS Handshakes',
                flow: 'Flow Records',
                fileinfo: 'File Info',
                stats: 'Engine Stats',
            };
            document.getElementById('suri-log-title').textContent =
                `${titles[currentEventType] || 'Events'} (${data.total.toLocaleString()} entries)`;

        } catch (e) {
            tableEl.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <h3>Failed to load events</h3>
                    <p>${escapeHtml(e.message)}</p>
                </div>
            `;
        }
    }

    function renderTable(data) {
        const tableEl = document.getElementById('suri-log-table');

        if (!data.entries || data.entries.length === 0) {
            tableEl.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                    <h3>No events found</h3>
                    <p>Try adjusting your filters or check if Suricata is running</p>
                </div>
            `;
            return;
        }

        const renderers = {
            alert: renderAlertTable,
            dns: renderDnsTable,
            http: renderHttpTable,
            tls: renderTlsTable,
            flow: renderFlowTable,
            fileinfo: renderFileTable,
            stats: renderStatsTable,
        };

        const renderer = renderers[currentEventType] || renderGenericTable;
        tableEl.innerHTML = renderer(data.entries);
    }

    // ── Alert Table ──────────────────────────────────────────────────────
    function renderAlertTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Severity</th>
                        <th>Signature</th>
                        <th>Source</th>
                        <th>Destination</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e._id) ? 'expanded' : ''}"
                            onclick="Suricata.toggleRow('${escapeAttr(e._id)}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td>${getSeverityBadge(e.severity)}</td>
                            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.signature || '-')}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}<span class="port-cell">:${e.src_port || ''}</span></td>
                            <td class="ip-cell">${escapeHtml(e.dest_ip || '')}<span class="port-cell">:${e.dest_port || ''}</span></td>
                            <td>${getActionBadge(e.action)}</td>
                        </tr>
                        ${expandedRows.has(e._id) ? renderAlertDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderAlertDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="7">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item"><span class="zeek-detail-label">SID</span><span class="zeek-detail-value">${e.signature_id || '-'}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Rev</span><span class="zeek-detail-value">${e.rev || '-'}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Category</span><span class="zeek-detail-value">${escapeHtml(e.category || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Protocol</span><span class="zeek-detail-value">${escapeHtml(e.proto || '-')}</span></div>
                            <div class="zeek-detail-item" style="grid-column:span 2"><span class="zeek-detail-label">Full Signature</span><span class="zeek-detail-value">${escapeHtml(e.signature || '-')}</span></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    // ── DNS Table ────────────────────────────────────────────────────────
    function renderDnsTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Type</th>
                        <th>Query</th>
                        <th>RR Type</th>
                        <th>Response</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e._id) ? 'expanded' : ''}"
                            onclick="Suricata.toggleRow('${escapeAttr(e._id)}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.query_type || '-')}</span></td>
                            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.rrname || '-')}</td>
                            <td><span class="service-badge">${escapeHtml(e.rrtype || '-')}</span></td>
                            <td>${e.rcode ? getRcodeBadge(e.rcode) : (escapeHtml(e.rdata || '-'))}</td>
                        </tr>
                        ${expandedRows.has(e._id) ? renderDnsDetails(e) : ''}
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
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Server</span><span class="zeek-detail-value">${escapeHtml(e.dest_ip || '-')}:${e.dest_port || ''}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Protocol</span><span class="zeek-detail-value">${escapeHtml(e.proto || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">TX ID</span><span class="zeek-detail-value">${e.tx_id != null ? e.tx_id : '-'}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Response Code</span><span class="zeek-detail-value">${escapeHtml(e.rcode || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Response Data</span><span class="zeek-detail-value">${escapeHtml(e.rdata || '-')}</span></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    // ── HTTP Table ───────────────────────────────────────────────────────
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
                        <th>URL</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e._id) ? 'expanded' : ''}"
                            onclick="Suricata.toggleRow('${escapeAttr(e._id)}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.http_method || '-')}</span></td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.hostname || '-')}</td>
                            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.url || '-')}</td>
                            <td>${getHttpStatusBadge(e.status)}</td>
                        </tr>
                        ${expandedRows.has(e._id) ? renderHttpDetails(e) : ''}
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
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Destination</span><span class="zeek-detail-value">${escapeHtml(e.dest_ip || '-')}:${e.dest_port || ''}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Content Type</span><span class="zeek-detail-value">${escapeHtml(e.http_content_type || '-')}</span></div>
                            <div class="zeek-detail-item" style="grid-column:span 2"><span class="zeek-detail-label">User Agent</span><span class="zeek-detail-value">${escapeHtml(e.http_user_agent || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Length</span><span class="zeek-detail-value">${e.length ? formatBytes(e.length) : '-'}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Referrer</span><span class="zeek-detail-value">${escapeHtml(e.http_refer || '-')}</span></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    // ── TLS Table ────────────────────────────────────────────────────────
    function renderTlsTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>SNI</th>
                        <th>Version</th>
                        <th>Subject</th>
                        <th>Issuer</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e._id) ? 'expanded' : ''}"
                            onclick="Suricata.toggleRow('${escapeAttr(e._id)}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}</td>
                            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.sni || '-')}</td>
                            <td><span class="protocol-badge">${escapeHtml(e.version || '-')}</span></td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-size:0.75rem">${escapeHtml(e.subject || '-')}</td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-size:0.75rem">${escapeHtml(e.issuerdn || '-')}</td>
                        </tr>
                        ${expandedRows.has(e._id) ? renderTlsDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderTlsDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="7">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Destination</span><span class="zeek-detail-value">${escapeHtml(e.dest_ip || '-')}:${e.dest_port || ''}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Fingerprint</span><span class="zeek-detail-value" style="font-size:0.7rem;font-family:monospace">${escapeHtml(e.fingerprint || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">JA3</span><span class="zeek-detail-value" style="font-size:0.7rem;font-family:monospace">${escapeHtml(e.ja3_hash || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">JA3S</span><span class="zeek-detail-value" style="font-size:0.7rem;font-family:monospace">${escapeHtml(e.ja3s_hash || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Not Before</span><span class="zeek-detail-value">${escapeHtml(e.notbefore || '-')}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Not After</span><span class="zeek-detail-value">${escapeHtml(e.notafter || '-')}</span></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    // ── Flow Table ───────────────────────────────────────────────────────
    function renderFlowTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Destination</th>
                        <th>Proto</th>
                        <th>App</th>
                        <th>Bytes</th>
                        <th>State</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr class="expandable-row ${expandedRows.has(e._id) ? 'expanded' : ''}"
                            onclick="Suricata.toggleRow('${escapeAttr(e._id)}')">
                            <td>
                                <svg class="expand-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9 18 15 12 9 6"/>
                                </svg>
                            </td>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}<span class="port-cell">:${e.src_port || ''}</span></td>
                            <td class="ip-cell">${escapeHtml(e.dest_ip || '')}<span class="port-cell">:${e.dest_port || ''}</span></td>
                            <td><span class="protocol-badge">${escapeHtml(e.proto || '')}</span></td>
                            <td>${e.app_proto ? `<span class="service-badge">${escapeHtml(e.app_proto)}</span>` : '-'}</td>
                            <td class="bytes-cell">${formatBytes((e.bytes_toserver || 0) + (e.bytes_toclient || 0))}</td>
                            <td>${escapeHtml(e.state || '-')}</td>
                        </tr>
                        ${expandedRows.has(e._id) ? renderFlowDetails(e) : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function renderFlowDetails(e) {
        return `
            <tr class="row-details open">
                <td colspan="8">
                    <div class="zeek-details">
                        <div class="zeek-details-grid">
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Bytes To Server</span><span class="zeek-detail-value">${formatBytes(e.bytes_toserver || 0)}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Bytes To Client</span><span class="zeek-detail-value">${formatBytes(e.bytes_toclient || 0)}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Packets To Server</span><span class="zeek-detail-value">${(e.pkts_toserver || 0).toLocaleString()}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Packets To Client</span><span class="zeek-detail-value">${(e.pkts_toclient || 0).toLocaleString()}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Start</span><span class="zeek-detail-value">${formatTime(e.start)}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">End</span><span class="zeek-detail-value">${formatTime(e.end)}</span></div>
                            <div class="zeek-detail-item"><span class="zeek-detail-label">Reason</span><span class="zeek-detail-value">${escapeHtml(e.reason || '-')}</span></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    // ── File Table ───────────────────────────────────────────────────────
    function renderFileTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Source</th>
                        <th>App</th>
                        <th>Filename</th>
                        <th>Size</th>
                        <th>State</th>
                        <th>MD5</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td class="ip-cell">${escapeHtml(e.src_ip || '')}</td>
                            <td>${e.app_proto ? `<span class="service-badge">${escapeHtml(e.app_proto)}</span>` : '-'}</td>
                            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(e.filename || e.http_url || '-')}</td>
                            <td class="bytes-cell">${formatBytes(e.size || 0)}</td>
                            <td>${escapeHtml(e.state || '-')}</td>
                            <td style="font-family:monospace;font-size:0.7rem">${escapeHtml((e.md5 || '-').substring(0, 12))}${e.md5 ? '...' : ''}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    // ── Stats Table ──────────────────────────────────────────────────────
    function renderStatsTable(entries) {
        return `
            <table class="zeek-log-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Uptime</th>
                        <th>Packets</th>
                        <th>Drops</th>
                        <th>Drop %</th>
                        <th>Bytes</th>
                        <th>Alerts</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => {
                        const pkts = e.capture_kernel_packets || 0;
                        const drops = e.capture_kernel_drops || 0;
                        const dropPct = pkts > 0 ? ((drops / pkts) * 100).toFixed(2) : '0.00';
                        return `
                        <tr>
                            <td class="timestamp">${formatTime(e.timestamp)}</td>
                            <td>${formatUptime(e.uptime || 0)}</td>
                            <td>${(e.decoder_pkts || 0).toLocaleString()}</td>
                            <td>${drops.toLocaleString()}</td>
                            <td>${parseFloat(dropPct) > 1 ? `<span style="color:var(--red)">${dropPct}%</span>` : `${dropPct}%`}</td>
                            <td class="bytes-cell">${formatBytes(e.decoder_bytes || 0)}</td>
                            <td>${(e.detect_alert || 0).toLocaleString()}</td>
                        </tr>
                    `;}).join('')}
                </tbody>
            </table>
        `;
    }

    // ── Generic Table ────────────────────────────────────────────────────
    function renderGenericTable(entries) {
        if (entries.length === 0) return '<p>No entries</p>';
        const keys = Object.keys(entries[0]).filter(k => !k.startsWith('_'));
        const displayKeys = keys.slice(0, 8);
        return `
            <table class="zeek-log-table">
                <thead><tr>${displayKeys.map(k => `<th>${escapeHtml(k)}</th>`).join('')}</tr></thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>${displayKeys.map(k => `<td>${escapeHtml(String(e[k] || '-').substring(0, 50))}</td>`).join('')}</tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    // ── Helpers ──────────────────────────────────────────────────────────
    function formatCount(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return n;
    }

    function escapeAttr(s) {
        return String(s).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    }

    function getSeverityBadge(sev) {
        const labels = { 1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low' };
        const colors = { 1: 'var(--red)', 2: 'var(--orange)', 3: 'var(--yellow)', 4: 'var(--text-muted)' };
        return `<span class="severity severity-${sev || 3}" style="color:${colors[sev] || 'var(--text-muted)'}">${labels[sev] || sev || '-'}</span>`;
    }

    function getActionBadge(action) {
        if (action === 'allowed') return '<span style="color:var(--green)">Allowed</span>';
        if (action === 'blocked') return '<span style="color:var(--red)">Blocked</span>';
        return escapeHtml(action || '-');
    }

    function getRcodeBadge(rcode) {
        if (rcode === 'NOERROR') return '<span style="color:var(--green)">OK</span>';
        if (rcode === 'NXDOMAIN') return '<span style="color:var(--orange)">NXDOMAIN</span>';
        if (rcode === 'SERVFAIL') return '<span style="color:var(--red)">SERVFAIL</span>';
        return escapeHtml(rcode || '-');
    }

    function getHttpStatusBadge(status) {
        if (!status) return '-';
        const s = parseInt(status);
        if (s >= 200 && s < 300) return `<span style="color:var(--green)">${s}</span>`;
        if (s >= 300 && s < 400) return `<span style="color:var(--blue)">${s}</span>`;
        if (s >= 400 && s < 500) return `<span style="color:var(--orange)">${s}</span>`;
        if (s >= 500) return `<span style="color:var(--red)">${s}</span>`;
        return String(s);
    }

    function switchEventType(type) {
        currentEventType = type;
        currentPage = 1;
        expandedRows.clear();
        document.querySelectorAll('#suricata-tabs .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.type === type);
        });
        loadEvents();
    }

    function toggleRow(id) {
        if (expandedRows.has(id)) {
            expandedRows.delete(id);
        } else {
            expandedRows.add(id);
        }
        loadEvents();
    }

    function toggleFilter() {
        document.getElementById('suri-filter-panel').classList.toggle('collapsed');
    }

    function applyFilters() {
        filters = {
            ip: document.getElementById('suri-filter-ip').value.trim(),
            port: document.getElementById('suri-filter-port').value.trim() || null,
            proto: document.getElementById('suri-filter-proto').value,
            search: document.getElementById('suri-filter-search').value.trim(),
            hours: document.getElementById('suri-filter-hours').value || null,
        };
        Object.keys(filters).forEach(k => { if (!filters[k]) delete filters[k]; });
        currentPage = 1;
        loadEvents();
    }

    function changePerPage(value) {
        perPage = parseInt(value);
        currentPage = 1;
        loadEvents();
    }

    return {
        render,
        switchEventType,
        toggleRow,
        toggleFilter,
        applyFilters,
        changePerPage,
    };
})();
