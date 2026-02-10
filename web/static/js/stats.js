/* NetworkTap - Traffic Statistics Page */

const Stats = (() => {
    let bandwidthChart = null;
    let dataAvailable = false;

    async function render(container) {
        container.innerHTML = `
            <div id="stats-status-banner"></div>

            <div class="stat-grid">
                <div class="stat-card stat-card-highlight" id="stat-bytes">
                    <div class="stat-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                        </svg>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Total Traffic (24h)</div>
                        <div class="stat-value">-</div>
                    </div>
                </div>
                <div class="stat-card" id="stat-connections">
                    <div class="stat-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                            <polyline points="15 3 21 3 21 9"/>
                            <line x1="10" y1="14" x2="21" y2="3"/>
                        </svg>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Connections</div>
                        <div class="stat-value">-</div>
                    </div>
                </div>
                <div class="stat-card" id="stat-sources">
                    <div class="stat-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="2" y1="12" x2="22" y2="12"/>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                        </svg>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Unique Sources</div>
                        <div class="stat-value">-</div>
                    </div>
                </div>
                <div class="stat-card" id="stat-destinations">
                    <div class="stat-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
                        </svg>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Unique Destinations</div>
                        <div class="stat-value">-</div>
                    </div>
                </div>
            </div>

            <div class="card chart-card">
                <div class="card-header">
                    <span class="card-title">Connection Trends</span>
                    <div class="time-range-selector" id="trend-range">
                        <button class="time-range-btn" data-hours="6">6h</button>
                        <button class="time-range-btn active" data-hours="24">24h</button>
                        <button class="time-range-btn" data-hours="72">3d</button>
                        <button class="time-range-btn" data-hours="168">1w</button>
                    </div>
                </div>
                <div class="chart-container" id="trend-chart" style="height:220px">
                    ${skeleton('chart')}
                </div>
            </div>

            <div class="grid-2">
                <div class="card chart-card">
                    <div class="card-header">
                        <span class="card-title">Bandwidth (Last Hour)</span>
                    </div>
                    <div class="chart-container" id="bandwidth-chart" style="height:200px">
                        ${skeleton('chart')}
                    </div>
                </div>

                <div class="card chart-card">
                    <div class="card-header">
                        <span class="card-title">Protocol Distribution</span>
                    </div>
                    <div id="protocol-chart" style="min-height:200px">
                        ${skeleton('chart')}
                    </div>
                </div>
            </div>

            <div class="grid-3">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Top DNS Domains</span>
                    </div>
                    <div id="dns-domains" class="dns-domains-list">
                        ${skeleton('row', 5)}
                    </div>
                </div>

                <div class="card chart-card">
                    <div class="card-header">
                        <span class="card-title">DNS Query Types</span>
                    </div>
                    <div id="dns-types" style="min-height:180px">
                        ${skeleton('chart')}
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Service Distribution</span>
                    </div>
                    <div id="service-dist">
                        ${skeleton('row', 5)}
                    </div>
                </div>
            </div>

            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Top Talkers</span>
                    </div>
                    <div id="top-talkers">
                        ${skeleton('row', 5)}
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Top Ports</span>
                    </div>
                    <div id="top-ports">
                        ${skeletonTable(5, 3)}
                    </div>
                </div>
            </div>

            <div class="card export-card">
                <div class="card-header">
                    <span class="card-title">Export Statistics</span>
                </div>
                <div class="export-buttons">
                    <a href="/api/reports/stats.csv" class="btn btn-secondary" download>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        Download CSV
                    </a>
                    <a href="/api/reports/report.html" class="btn btn-secondary" download>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Download HTML Report
                    </a>
                </div>
            </div>
        `;

        // Set up time range selector
        document.querySelectorAll('#trend-range .time-range-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#trend-range .time-range-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                loadTrends(parseInt(btn.dataset.hours));
            });
        });

        // Check data availability first
        await checkDataAvailability();

        // Load all data in parallel
        await Promise.all([
            loadStats(),
            loadBandwidth(),
            loadTrends(24),
            loadDnsStats(),
            loadServices(),
        ]);

        App.setRefresh(() => {
            loadStats();
            loadBandwidth();
        }, 30000);
    }

    async function checkDataAvailability() {
        const banner = document.getElementById('stats-status-banner');
        try {
            const data = await api('/api/zeek/logs');
            const logs = data.logs || [];

            // Check if conn.log and dns.log are available
            const connLog = logs.find(l => l.type === 'conn');
            const dnsLog = logs.find(l => l.type === 'dns');

            const hasConn = connLog && connLog.available;
            const hasDns = dnsLog && dnsLog.available;

            dataAvailable = hasConn || hasDns;

            if (!dataAvailable) {
                banner.innerHTML = `
                    <div class="alert alert-warning">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="8" x2="12" y2="12"/>
                            <line x1="12" y1="16" x2="12.01" y2="16"/>
                        </svg>
                        <div class="alert-content">
                            <strong>No Zeek log data found</strong>
                            <p>Statistics require Zeek to be running and generating logs. Please ensure:
                            <ul>
                                <li>Zeek service is running (<code>systemctl status zeek</code>)</li>
                                <li>Packet capture is active to generate traffic data</li>
                                <li>Log files exist in the configured Zeek log directory</li>
                            </ul>
                            </p>
                        </div>
                    </div>
                `;
            } else if (!hasConn) {
                banner.innerHTML = `
                    <div class="alert alert-info">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="16" x2="12" y2="12"/>
                            <line x1="12" y1="8" x2="12.01" y2="8"/>
                        </svg>
                        <div class="alert-content">
                            <strong>Limited data available</strong>
                            <p>Connection logs (conn.log) not found. Some statistics may be unavailable.</p>
                        </div>
                    </div>
                `;
            } else {
                banner.innerHTML = '';
            }
        } catch (e) {
            console.error('Failed to check data availability:', e);
            banner.innerHTML = `
                <div class="alert alert-warning">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <div class="alert-content">
                        <strong>Could not check data sources</strong>
                        <p>Unable to verify Zeek log availability. Statistics may be incomplete.</p>
                    </div>
                </div>
            `;
        }
    }

    async function loadStats() {
        try {
            const data = await api('/api/stats/traffic?hours=24');

            // Check if we have any actual data
            const hasData = data.total_connections > 0;

            if (hasData) {
                // Update stat cards with animation
                animateValue(document.querySelector('#stat-bytes .stat-value'), data.total_bytes, formatBytes);
                animateValue(document.querySelector('#stat-connections .stat-value'), data.total_connections, v => v.toLocaleString());
                animateValue(document.querySelector('#stat-sources .stat-value'), data.unique_src_ips, v => v.toLocaleString());
                animateValue(document.querySelector('#stat-destinations .stat-value'), data.unique_dest_ips, v => v.toLocaleString());
            } else {
                // Show zeros with context
                document.querySelector('#stat-bytes .stat-value').textContent = '0 B';
                document.querySelector('#stat-connections .stat-value').textContent = '0';
                document.querySelector('#stat-sources .stat-value').textContent = '0';
                document.querySelector('#stat-destinations .stat-value').textContent = '0';
            }

            // Protocol chart
            renderProtocolChart(data.protocols);

            // Top talkers
            renderTopTalkers(data.top_talkers);

            // Top ports
            renderTopPorts(data.top_ports);

        } catch (e) {
            console.error('Failed to load stats:', e);
            // Show error state in stat cards
            document.querySelectorAll('.stat-card .stat-value').forEach(el => {
                el.textContent = '-';
            });
        }
    }

    async function loadBandwidth() {
        try {
            const data = await api('/api/stats/bandwidth?minutes=60');
            renderBandwidthChart(data.data);
        } catch (e) {
            document.getElementById('bandwidth-chart').innerHTML = renderNoData('Unable to load bandwidth data.');
        }
    }

    async function loadTrends(hours = 24) {
        const container = document.getElementById('trend-chart');
        try {
            const data = await api(`/api/stats/trends?hours=${hours}&interval=15`);
            renderTrendChart(data.trends, container);
        } catch (e) {
            container.innerHTML = renderNoData('Unable to load trend data.');
        }
    }

    async function loadDnsStats() {
        try {
            const data = await api('/api/stats/dns?hours=24');
            renderDnsDomains(data.top_domains);
            renderDnsTypes(data.query_types);
        } catch (e) {
            document.getElementById('dns-domains').innerHTML = renderNoData('Unable to load DNS data.');
            document.getElementById('dns-types').innerHTML = renderNoData('Unable to load DNS data.');
        }
    }

    async function loadServices() {
        try {
            const data = await api('/api/stats/services?hours=24');
            renderServiceDistribution(data.services);
        } catch (e) {
            document.getElementById('service-dist').innerHTML = renderNoData('Unable to load service data.');
        }
    }

    function renderTrendChart(data, container) {
        if (!data || data.length === 0) {
            container.innerHTML = renderNoData('Connection trend data will appear once Zeek begins logging traffic.');
            return;
        }

        const width = container.offsetWidth || 600;
        const height = 200;
        const padding = { top: 20, right: 20, bottom: 40, left: 60 };

        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        const maxConns = Math.max(...data.map(d => d.connections)) || 1;
        const xStep = chartWidth / (data.length - 1 || 1);

        // Build path
        let linePath = '';
        let areaPath = `M ${padding.left} ${padding.top + chartHeight} `;

        data.forEach((d, i) => {
            const x = padding.left + i * xStep;
            const y = padding.top + chartHeight - (d.connections / maxConns) * chartHeight;

            if (i === 0) {
                linePath += `M ${x} ${y}`;
                areaPath += `L ${x} ${y}`;
            } else {
                linePath += ` L ${x} ${y}`;
                areaPath += ` L ${x} ${y}`;
            }
        });

        areaPath += ` L ${padding.left + (data.length - 1) * xStep} ${padding.top + chartHeight} Z`;

        let svg = `
            <svg width="${width}" height="${height}" style="display:block">
                <defs>
                    <linearGradient id="trend-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:var(--accent);stop-opacity:0.4"/>
                        <stop offset="100%" style="stop-color:var(--accent);stop-opacity:0.05"/>
                    </linearGradient>
                </defs>

                <!-- Grid lines -->
                ${[0, 0.25, 0.5, 0.75, 1].map(pct => {
                    const y = padding.top + chartHeight * (1 - pct);
                    return `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--border)" stroke-dasharray="3,3"/>`;
                }).join('')}

                <!-- Y-axis labels -->
                <text x="${padding.left - 10}" y="${padding.top + 4}" fill="var(--text-muted)" font-size="10" text-anchor="end">${maxConns.toLocaleString()}</text>
                <text x="${padding.left - 10}" y="${padding.top + chartHeight}" fill="var(--text-muted)" font-size="10" text-anchor="end">0</text>

                <!-- Area under curve -->
                <path d="${areaPath}" fill="url(#trend-gradient)"/>

                <!-- Line -->
                <path d="${linePath}" class="trend-line" fill="none" stroke="var(--accent)" stroke-width="2"/>

                <!-- Points -->
                ${data.map((d, i) => {
                    const x = padding.left + i * xStep;
                    const y = padding.top + chartHeight - (d.connections / maxConns) * chartHeight;
                    const time = formatTrendTime(d.time);
                    return `<circle cx="${x}" cy="${y}" r="4" class="trend-point"
                        onmouseover="ChartTooltip.show(event.pageX, event.pageY, '${time}', '${d.connections.toLocaleString()} connections')"
                        onmouseout="ChartTooltip.hide()"/>`;
                }).join('')}

                <!-- X-axis labels -->
                ${data.filter((_, i) => i % Math.ceil(data.length / 6) === 0).map((d, idx, arr) => {
                    const i = data.indexOf(d);
                    const x = padding.left + i * xStep;
                    return `<text x="${x}" y="${height - 10}" fill="var(--text-muted)" font-size="10" text-anchor="middle">${formatTrendTime(d.time)}</text>`;
                }).join('')}
            </svg>
        `;

        container.innerHTML = svg;
    }

    function formatTrendTime(isoTime) {
        try {
            const d = new Date(isoTime);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return isoTime;
        }
    }

    function renderNoData(message) {
        return `
            <div class="no-data-placeholder">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 21H4.6c-.56 0-.84 0-1.054-.109a1 1 0 0 1-.437-.437C3 20.24 3 19.96 3 19.4V3"/>
                    <path d="m7 14 4-4 4 4 6-6"/>
                </svg>
                <span>${message}</span>
            </div>
        `;
    }

    function renderBandwidthChart(data) {
        const container = document.getElementById('bandwidth-chart');
        if (!data || data.length === 0) {
            container.innerHTML = renderNoData('Bandwidth data will appear as traffic is captured.');
            return;
        }

        const width = container.offsetWidth || 400;
        const height = 180;
        const padding = { top: 10, right: 10, bottom: 30, left: 50 };

        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        const maxBytes = Math.max(...data.map(d => d.bytes_in + d.bytes_out)) || 1;
        const barWidth = Math.max(2, chartWidth / data.length - 1);

        let svg = `<svg width="${width}" height="${height}" style="display:block">`;

        // Y-axis labels
        svg += `<text x="${padding.left - 5}" y="${padding.top + 10}" fill="var(--text-muted)" font-size="10" text-anchor="end">${formatBytes(maxBytes)}</text>`;
        svg += `<text x="${padding.left - 5}" y="${height - padding.bottom}" fill="var(--text-muted)" font-size="10" text-anchor="end">0</text>`;

        // Bars with hover
        data.forEach((d, i) => {
            const x = padding.left + i * (barWidth + 1);
            const totalBytes = d.bytes_in + d.bytes_out;
            const barHeight = (totalBytes / maxBytes) * chartHeight;
            const y = padding.top + chartHeight - barHeight;

            svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}"
                fill="var(--accent)" class="chart-bar" opacity="0.7"
                onmouseover="ChartTooltip.show(event.pageX, event.pageY, '${d.time}', '${formatBytes(totalBytes)}')"
                onmouseout="ChartTooltip.hide()"/>`;
        });

        // X-axis labels
        const labelInterval = Math.ceil(data.length / 6);
        data.forEach((d, i) => {
            if (i % labelInterval === 0) {
                const x = padding.left + i * (barWidth + 1) + barWidth / 2;
                svg += `<text x="${x}" y="${height - 5}" fill="var(--text-muted)" font-size="10" text-anchor="middle">${d.time}</text>`;
            }
        });

        svg += '</svg>';
        container.innerHTML = svg;
    }

    function renderProtocolChart(protocols) {
        const container = document.getElementById('protocol-chart');
        if (!protocols || Object.keys(protocols).length === 0) {
            container.innerHTML = renderNoData('Protocol distribution will appear as connections are logged.');
            return;
        }

        const total = Object.values(protocols).reduce((a, b) => a + b, 0);
        const colors = ['var(--accent)', 'var(--blue)', 'var(--yellow)', 'var(--orange)', 'var(--red)'];

        const sorted = Object.entries(protocols).sort((a, b) => b[1] - a[1]).slice(0, 5);

        let html = '<div class="protocol-bars">';
        sorted.forEach(([proto, count], i) => {
            const pct = ((count / total) * 100).toFixed(1);
            html += `
                <div class="protocol-row" style="margin-bottom:12px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-weight:500">${escapeHtml(proto)}</span>
                        <span style="color:var(--text-muted)">${count.toLocaleString()} (${pct}%)</span>
                    </div>
                    <div class="stat-bar">
                        <div class="stat-bar-fill" style="width:${pct}%;background:${colors[i % colors.length]};transition:width 0.5s ease"></div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    function renderDnsDomains(domains) {
        const container = document.getElementById('dns-domains');
        if (!domains || domains.length === 0) {
            container.innerHTML = renderNoData('DNS queries will appear as traffic is captured.');
            return;
        }

        let html = '';
        domains.slice(0, 10).forEach((d, i) => {
            html += `
                <div class="dns-domain-item">
                    <span class="dns-domain-rank">${i + 1}.</span>
                    <span class="dns-domain-name" title="${escapeHtml(d.domain)}">${escapeHtml(d.domain)}</span>
                    <span class="dns-domain-count">${d.count.toLocaleString()}</span>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    function renderDnsTypes(types) {
        const container = document.getElementById('dns-types');
        if (!types || Object.keys(types).length === 0) {
            container.innerHTML = renderNoData('DNS query types will appear here.');
            return;
        }

        const total = Object.values(types).reduce((a, b) => a + b, 0);
        const sorted = Object.entries(types).sort((a, b) => b[1] - a[1]).slice(0, 6);
        const colors = ['#00d4aa', '#3b82f6', '#f97316', '#eab308', '#ef4444', '#8b5cf6'];

        // Render as donut chart
        const size = 140;
        const cx = size / 2;
        const cy = size / 2;
        const radius = 50;
        const innerRadius = 30;

        let startAngle = -90;
        let paths = '';

        sorted.forEach(([type, count], i) => {
            const pct = count / total;
            const angle = pct * 360;
            const endAngle = startAngle + angle;

            const x1 = cx + radius * Math.cos(startAngle * Math.PI / 180);
            const y1 = cy + radius * Math.sin(startAngle * Math.PI / 180);
            const x2 = cx + radius * Math.cos(endAngle * Math.PI / 180);
            const y2 = cy + radius * Math.sin(endAngle * Math.PI / 180);

            const ix1 = cx + innerRadius * Math.cos(startAngle * Math.PI / 180);
            const iy1 = cy + innerRadius * Math.sin(startAngle * Math.PI / 180);
            const ix2 = cx + innerRadius * Math.cos(endAngle * Math.PI / 180);
            const iy2 = cy + innerRadius * Math.sin(endAngle * Math.PI / 180);

            const largeArc = angle > 180 ? 1 : 0;

            paths += `<path d="M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix1} ${iy1} Z"
                fill="${colors[i]}" class="donut-segment"
                onmouseover="ChartTooltip.show(event.pageX, event.pageY, '${escapeHtml(type)}', '${count.toLocaleString()} (${(pct * 100).toFixed(1)}%)')"
                onmouseout="ChartTooltip.hide()"/>`;

            startAngle = endAngle;
        });

        let html = `
            <div class="donut-chart-wrapper">
                <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="display:block;margin:0 auto">
                    ${paths}
                    <text x="${cx}" y="${cy - 5}" class="donut-center-text" text-anchor="middle">${total.toLocaleString()}</text>
                    <text x="${cx}" y="${cy + 12}" class="donut-center-label" text-anchor="middle">queries</text>
                </svg>
                <div class="chart-legend">
                    ${sorted.map(([type, count], i) => `
                        <div class="chart-legend-item">
                            <span class="chart-legend-swatch" style="background:${colors[i]}"></span>
                            <span>${escapeHtml(type)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    function renderServiceDistribution(services) {
        const container = document.getElementById('service-dist');
        if (!services || services.length === 0) {
            container.innerHTML = renderNoData('Service distribution will appear as connections are logged.');
            return;
        }

        const maxCount = services[0]?.count || 1;
        const colors = ['var(--accent)', 'var(--blue)', 'var(--green)', 'var(--yellow)', 'var(--orange)'];

        let html = '<div class="hbar-chart">';
        services.slice(0, 8).forEach((s, i) => {
            const pct = (s.count / maxCount) * 100;
            html += `
                <div class="hbar-item">
                    <span class="hbar-label" title="${escapeHtml(s.service)}">${escapeHtml(s.service)}</span>
                    <div class="hbar-bar-wrapper">
                        <div class="hbar-bar" style="width:${pct}%;background:${colors[i % colors.length]}"></div>
                    </div>
                    <span class="hbar-value">${s.count.toLocaleString()}</span>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    function renderTopTalkers(talkers) {
        const container = document.getElementById('top-talkers');
        if (!talkers || talkers.length === 0) {
            container.innerHTML = renderNoData('Top talkers will appear as traffic is captured.');
            return;
        }

        const maxBytes = talkers[0]?.bytes || 1;

        let html = '<div class="top-list">';
        talkers.slice(0, 10).forEach((t, i) => {
            const pct = ((t.bytes / maxBytes) * 100).toFixed(0);
            html += `
                <div class="top-item" style="margin-bottom:8px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                        <span style="font-family:monospace">${escapeHtml(t.ip)}</span>
                        <span style="color:var(--text-muted)">${formatBytes(t.bytes)}</span>
                    </div>
                    <div class="stat-bar">
                        <div class="stat-bar-fill accent" style="width:${pct}%"></div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    function renderTopPorts(ports) {
        const container = document.getElementById('top-ports');
        if (!ports || ports.length === 0) {
            container.innerHTML = renderNoData('Top ports will appear as traffic is captured.');
            return;
        }

        let html = '<table><thead><tr><th>Port</th><th>Service</th><th>Connections</th></tr></thead><tbody>';
        ports.slice(0, 10).forEach(p => {
            html += `
                <tr>
                    <td style="font-family:monospace">${p.port}</td>
                    <td>${escapeHtml(p.service) || '-'}</td>
                    <td>${p.count.toLocaleString()}</td>
                </tr>
            `;
        });
        html += '</tbody></table>';

        container.innerHTML = html;
    }

    return { render };
})();
