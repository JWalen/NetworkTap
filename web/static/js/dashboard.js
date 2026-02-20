/* NetworkTap - Dashboard View with SVG Charts */

const Dashboard = (() => {
    // Time range options (in seconds)
    const TIME_RANGES = {
        '30m': { label: '30 min', seconds: 30 * 60, points: 60 },
        '1h': { label: '1 hour', seconds: 60 * 60, points: 60 },
        '6h': { label: '6 hours', seconds: 6 * 60 * 60, points: 72 },
        '1d': { label: '1 day', seconds: 24 * 60 * 60, points: 96 },
        '1w': { label: '1 week', seconds: 7 * 24 * 60 * 60, points: 84 },
        '1M': { label: '1 month', seconds: 30 * 24 * 60 * 60, points: 90 },
    };

    // Current selected ranges
    let netTimeRange = '30m';
    let cpuMemTimeRange = '30m';

    // History with timestamps { timestamp, value }
    let cpuHistory = [];
    let memHistory = [];
    let netHistory = {};       // { ifaceName: [{ timestamp, rx, tx }] }
    let prevNetBytes = {};     // previous raw byte counts for delta
    let alertRateHistory = [];
    let alertSeverityCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };
    let topTalkers = {};
    let protocolCounts = {};
    let prevAlertCount = 0;

    // Max history to keep (enough for 1 month at 5s intervals would be huge, so we aggregate)
    const MAX_RAW_HISTORY = 720; // 1 hour of 5s samples

    // Old traffic sparkline data
    let trafficHistory = [];
    const MAX_TRAFFIC = 30;

    // Format large numbers for chart axis labels
    function formatChartValue(val) {
        if (val >= 1000000000) return (val / 1000000000).toFixed(1) + 'G';
        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
        if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
        return val.toString();
    }

    // Format timestamp for x-axis based on time range
    function formatTimeLabel(timestamp, rangeKey) {
        const d = new Date(timestamp);
        const pad2 = n => n.toString().padStart(2, '0');
        
        if (rangeKey === '30m' || rangeKey === '1h') {
            // Show HH:MM
            return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
        } else if (rangeKey === '6h' || rangeKey === '1d') {
            // Show HH:MM
            return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
        } else {
            // Week/Month: show MM/DD
            return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`;
        }
    }

    /* ── SVG Chart Utilities ──────────────────────────── */

    function svgLineChart(datasets, opts = {}) {
        const w = opts.width || 400;
        const h = opts.height || 140;
        const pad = { top: 8, right: 8, bottom: 28, left: 36 }; // Increased bottom padding for time labels
        const cw = w - pad.left - pad.right;
        const ch = h - pad.top - pad.bottom;

        let yMax = opts.yMax || 0;
        if (!yMax) {
            for (const ds of datasets) {
                const vals = ds.values || [];
                for (const v of vals) {
                    const val = typeof v === 'object' ? v.value : v;
                    if (val > yMax) yMax = val;
                }
            }
        }
        if (yMax === 0) yMax = 100;

        // Grid lines (horizontal)
        const gridLines = 4;
        let grid = '';
        for (let i = 0; i <= gridLines; i++) {
            const y = pad.top + (ch / gridLines) * i;
            const val = Math.round(yMax - (yMax / gridLines) * i);
            grid += `<line x1="${pad.left}" y1="${y}" x2="${w - pad.right}" y2="${y}" stroke="var(--border)" stroke-width="0.5"/>`;
            grid += `<text x="${pad.left - 4}" y="${y + 3}" text-anchor="end" fill="var(--text-muted)" font-size="8">${formatChartValue(val)}</text>`;
        }

        // X-axis time labels
        const timestamps = opts.timestamps || [];
        const rangeKey = opts.rangeKey || '30m';
        let xLabels = '';
        
        if (timestamps.length > 0) {
            // Show 4-5 time labels evenly distributed (fewer to prevent overlap)
            const labelCount = 5;
            const step = Math.max(1, Math.floor((timestamps.length - 1) / (labelCount - 1)));
            
            // Calculate which indices to show labels at
            const labelIndices = [];
            for (let i = 0; i < timestamps.length; i += step) {
                labelIndices.push(i);
            }
            // Ensure last point is included
            if (labelIndices[labelIndices.length - 1] !== timestamps.length - 1) {
                labelIndices.push(timestamps.length - 1);
            }
            
            labelIndices.forEach((idx, i) => {
                const x = pad.left + (timestamps.length > 1 ? (idx / (timestamps.length - 1)) * cw : cw / 2);
                const label = formatTimeLabel(timestamps[idx], rangeKey);
                
                // Vertical grid line (skip first and last to avoid edge clutter)
                if (i > 0 && i < labelIndices.length - 1) {
                    grid += `<line x1="${x}" y1="${pad.top}" x2="${x}" y2="${pad.top + ch}" stroke="var(--border)" stroke-width="0.3" stroke-dasharray="2,2"/>`;
                }
                
                // Anchor: start for first, end for last, middle for others
                let anchor = 'middle';
                if (i === 0) anchor = 'start';
                if (i === labelIndices.length - 1) anchor = 'end';
                
                xLabels += `<text x="${x}" y="${h - 6}" text-anchor="${anchor}" fill="var(--text-muted)" font-size="9">${label}</text>`;
            });
        }

        // X-axis label (legacy)
        const xLabel = opts.xLabel || '';
        const xText = xLabel ? `<text x="${w / 2}" y="${h - 2}" text-anchor="middle" fill="var(--text-muted)" font-size="8">${xLabel}</text>` : '';

        // Data lines
        let paths = '';
        for (const ds of datasets) {
            const vals = ds.values || [];
            if (vals.length < 2) continue;
            
            const points = vals.map((v, i) => {
                const val = typeof v === 'object' ? v.value : v;
                const x = pad.left + (vals.length > 1 ? (i / (vals.length - 1)) * cw : cw / 2);
                const y = pad.top + ch - (val / yMax) * ch;
                return `${x},${y}`;
            });

            if (opts.fill) {
                const firstX = pad.left;
                const lastX = pad.left + cw;
                const bottom = pad.top + ch;
                paths += `<polygon points="${firstX},${bottom} ${points.join(' ')} ${lastX},${bottom}" fill="${ds.color}" opacity="0.15"/>`;
            }
            paths += `<polyline points="${points.join(' ')}" fill="none" stroke="${ds.color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>`;
        }

        return `<div class="chart-container"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">${grid}${paths}${xLabels}${xText}</svg></div>`;
    }

    function svgBarChart(values, opts = {}) {
        const w = opts.width || 400;
        const h = opts.height || 120;
        const pad = { top: 8, right: 8, bottom: 16, left: 32 };
        const cw = w - pad.left - pad.right;
        const ch = h - pad.top - pad.bottom;
        const color = opts.color || 'var(--accent)';

        let yMax = opts.yMax || Math.max(...values, 1);

        // Grid
        const gridLines = 3;
        let grid = '';
        for (let i = 0; i <= gridLines; i++) {
            const y = pad.top + (ch / gridLines) * i;
            const val = Math.round(yMax - (yMax / gridLines) * i);
            grid += `<line x1="${pad.left}" y1="${y}" x2="${w - pad.right}" y2="${y}" stroke="var(--border)" stroke-width="0.5"/>`;
            grid += `<text x="${pad.left - 4}" y="${y + 3}" text-anchor="end" fill="var(--text-muted)" font-size="7">${val}</text>`;
        }

        const barWidth = values.length > 0 ? Math.max(2, (cw / values.length) - 2) : 4;
        let bars = '';
        for (let i = 0; i < values.length; i++) {
            const bh = (values[i] / yMax) * ch;
            const x = pad.left + (i / values.length) * cw + 1;
            const y = pad.top + ch - bh;
            bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${bh}" fill="${color}" rx="1" opacity="0.8"/>`;
        }

        return `<div class="chart-container"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">${grid}${bars}</svg></div>`;
    }

    function svgDonut(segments, opts = {}) {
        const size = opts.size || 140;
        const cx = size / 2;
        const cy = size / 2;
        const r = (size / 2) - 16;
        const strokeW = opts.stroke || 16;
        const circumference = 2 * Math.PI * r;

        const total = segments.reduce((s, seg) => s + seg.value, 0);
        if (total === 0) {
            return `<div class="chart-container chart-container--donut"><svg viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet">
                <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--border)" stroke-width="${strokeW}"/>
                <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central" fill="var(--text-muted)" font-size="10">No data</text>
            </svg></div>`;
        }

        let arcs = '';
        let offset = 0;
        for (const seg of segments) {
            const pct = seg.value / total;
            const dash = pct * circumference;
            const gap = circumference - dash;
            arcs += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${seg.color}" stroke-width="${strokeW}"
                stroke-dasharray="${dash} ${gap}" stroke-dashoffset="${-offset}"
                transform="rotate(-90 ${cx} ${cy})"/>`;
            offset += dash;
        }

        arcs += `<text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central" fill="var(--text-primary)" font-size="14" font-weight="700">${total}</text>`;

        // Legend
        let legend = '<div class="chart-legend">';
        for (const seg of segments) {
            legend += `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${seg.color}"></span>${seg.label}: ${seg.value}</span>`;
        }
        legend += '</div>';

        return `<div class="chart-container chart-container--donut"><svg viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet">${arcs}</svg>${legend}</div>`;
    }

    function svgHorizontalBar(items, opts = {}) {
        const w = opts.width || 400;
        const barH = 18;
        const gap = 3;
        const labelW = 100;
        const h = Math.max(70, items.length * (barH + gap) + 8);
        const maxVal = items.length > 0 ? Math.max(...items.map(i => i.value), 1) : 1;
        const barArea = w - labelW - 40;
        const color = opts.color || 'var(--accent)';

        let bars = '';
        items.forEach((item, i) => {
            const y = 4 + i * (barH + gap);
            const bw = (item.value / maxVal) * barArea;
            const label = item.label.length > 14 ? item.label.slice(0, 14) + '…' : item.label;
            bars += `<text x="${labelW - 4}" y="${y + barH / 2 + 3}" text-anchor="end" fill="var(--text-secondary)" font-size="8">${label}</text>`;
            bars += `<rect x="${labelW}" y="${y}" width="${bw}" height="${barH}" fill="${color}" rx="2" opacity="0.8"/>`;
            bars += `<text x="${labelW + bw + 3}" y="${y + barH / 2 + 3}" fill="var(--text-muted)" font-size="7">${item.value}</text>`;
        });

        return `<div class="chart-container"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">${bars}</svg></div>`;
    }

    // Time range selector HTML
    function timeRangeSelector(id, currentRange, onChange) {
        return `
            <div class="time-range-selector" id="${id}">
                ${Object.entries(TIME_RANGES).map(([key, val]) => 
                    `<button class="time-range-btn ${key === currentRange ? 'active' : ''}" data-range="${key}">${val.label}</button>`
                ).join('')}
            </div>
        `;
    }

    /* ── Render ────────────────────────────────────────── */

    async function render(container) {
        container.innerHTML = `
            <!-- Row 1: Key metrics -->
            <div class="stat-grid" id="stat-cards">
                <div class="stat-card">
                    <span class="stat-label">CPU</span>
                    <span class="stat-value" id="cpu-val">--</span>
                    <div class="stat-bar"><div class="stat-bar-fill green" id="cpu-bar" style="width:0%"></div></div>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Memory</span>
                    <span class="stat-value" id="mem-val">--</span>
                    <div class="stat-bar"><div class="stat-bar-fill green" id="mem-bar" style="width:0%"></div></div>
                    <span class="stat-sub" id="mem-detail"></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Disk</span>
                    <span class="stat-value" id="disk-val">--</span>
                    <div class="stat-bar"><div class="stat-bar-fill green" id="disk-bar" style="width:0%"></div></div>
                    <span class="stat-sub" id="disk-detail"></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Uptime</span>
                    <span class="stat-value" id="uptime-val">--</span>
                    <span class="stat-sub" id="load-val"></span>
                </div>
            </div>

            <!-- Row 2: Services and Interfaces (critical for monitoring appliance) -->
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Services</span>
                    </div>
                    <div id="service-list">
                        ${skeleton('row', 4)}
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Interfaces</span>
                    </div>
                    <div id="iface-list">
                        ${skeleton('row', 3)}
                    </div>
                </div>
            </div>

            <!-- Row 3: Network throughput (full width, primary purpose of network tap) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Network Throughput</span>
                    ${timeRangeSelector('net-time-range', netTimeRange)}
                </div>
                <div id="net-throughput-chart" class="chart-full-width"></div>
            </div>

            <!-- Row 4: Recent alerts (security-critical) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Recent Alerts</span>
                    <a href="#alerts" class="btn btn-sm btn-secondary">View All</a>
                </div>
                <div class="alert-feed" id="alert-feed">
                    ${skeleton('row', 5)}
                </div>
            </div>

            <!-- Row 5: Alert analytics -->
            <div class="grid-3">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Severity</span>
                    </div>
                    <div id="severity-chart"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Top Talkers</span>
                    </div>
                    <div id="talkers-chart"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Protocols</span>
                    </div>
                    <div id="protocol-chart"></div>
                </div>
            </div>

            <!-- Row 6: Traffic and alert rate -->
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Traffic</span>
                        <span class="stat-sub">packets/sec</span>
                    </div>
                    <div class="sparkline-container" id="traffic-chart"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Alert Rate</span>
                        <span class="stat-sub">per interval</span>
                    </div>
                    <div id="alert-rate-chart"></div>
                </div>
            </div>

            <!-- Row 7: CPU/Memory history -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">CPU & Memory History</span>
                    ${timeRangeSelector('cpumem-time-range', cpuMemTimeRange)}
                </div>
                <div id="cpumem-chart" class="chart-full-width"></div>
            </div>
        `;

        // Bind time range selectors
        bindTimeRangeSelector('net-time-range', async (range) => {
            netTimeRange = range;
            await loadHistoricalStats(range);
        });

        bindTimeRangeSelector('cpumem-time-range', async (range) => {
            cpuMemTimeRange = range;
            await loadHistoricalStats(range);
        });

        await refresh();
        App.setRefresh(refresh, 10000);
    }

    // Load historical stats from backend
    async function loadHistoricalStats(range) {
        try {
            const data = await api(`/api/stats/history?range=${range}`);
            
            if (data.system && data.system.length > 0) {
                // Replace in-memory history with backend data
                cpuHistory = data.system.map(d => ({ timestamp: d.timestamp, value: d.cpu }));
                memHistory = data.system.map(d => ({ timestamp: d.timestamp, value: d.memory }));
            }
            
            if (data.network) {
                // Replace network history with backend data
                for (const [iface, points] of Object.entries(data.network)) {
                    netHistory[iface] = points.map(d => ({ 
                        timestamp: d.timestamp, 
                        rx: d.rx, 
                        tx: d.tx 
                    }));
                }
            }
            
            renderCpuMemChart();
            renderNetThroughputChart();
        } catch (e) {
            console.error('Failed to load historical stats:', e);
            // Fall back to in-memory data
            renderCpuMemChart();
            renderNetThroughputChart();
        }
    }

    function bindTimeRangeSelector(id, onChange) {
        const selector = document.getElementById(id);
        if (!selector) return;
        selector.querySelectorAll('.time-range-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                selector.querySelectorAll('.time-range-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                onChange(btn.dataset.range);
            });
        });
    }

    async function refresh() {
        try {
            const [status, ifaces, alerts] = await Promise.all([
                api('/api/system/status'),
                api('/api/system/interfaces'),
                api('/api/alerts/all?limit=20').catch(() => ({ alerts: [] })),
            ]);

            updateStats(status.system);
            updateInterfaces(ifaces.interfaces);
            updateServices(status.services);
            updateTrafficChart(ifaces.interfaces);
            updateCpuMemHistory(status.system);
            updateNetHistory(ifaces.interfaces);
            updateAlertAnalytics(alerts.alerts);
            updateAlertFeed(alerts.alerts);
        } catch (e) {
            // Will be retried on next interval
        }
    }

    function updateStats(sys) {
        if (!sys) return;

        const cpu = Math.round(sys.cpu_percent);
        document.getElementById('cpu-val').textContent = cpu + '%';
        const cpuBar = document.getElementById('cpu-bar');
        cpuBar.style.width = cpu + '%';
        cpuBar.className = 'stat-bar-fill ' + barColor(cpu);

        const mem = Math.round(sys.memory_percent);
        document.getElementById('mem-val').textContent = mem + '%';
        const memBar = document.getElementById('mem-bar');
        memBar.style.width = mem + '%';
        memBar.className = 'stat-bar-fill ' + barColor(mem);
        document.getElementById('mem-detail').textContent =
            formatBytes(sys.memory_used) + ' / ' + formatBytes(sys.memory_total);

        const disk = Math.round(sys.disk_percent);
        document.getElementById('disk-val').textContent = disk + '%';
        const diskBar = document.getElementById('disk-bar');
        diskBar.style.width = disk + '%';
        diskBar.className = 'stat-bar-fill ' + barColor(disk);
        document.getElementById('disk-detail').textContent =
            formatBytes(sys.disk_free) + ' free of ' + formatBytes(sys.disk_total);

        document.getElementById('uptime-val').textContent = formatUptime(sys.uptime);
        document.getElementById('load-val').textContent =
            'Load: ' + sys.load_avg.map(v => v.toFixed(2)).join(' / ');
    }

    function updateCpuMemHistory(sys) {
        if (!sys) return;

        const now = Date.now();
        cpuHistory.push({ timestamp: now, value: Math.round(sys.cpu_percent) });
        memHistory.push({ timestamp: now, value: Math.round(sys.memory_percent) });

        // Keep limited raw history
        if (cpuHistory.length > MAX_RAW_HISTORY) cpuHistory.shift();
        if (memHistory.length > MAX_RAW_HISTORY) memHistory.shift();

        renderCpuMemChart();
    }

    function renderCpuMemChart() {
        const el = document.getElementById('cpumem-chart');
        if (!el) return;

        const range = TIME_RANGES[cpuMemTimeRange];
        const cutoff = Date.now() - range.seconds * 1000;

        // Filter and aggregate data for the selected range
        const cpuFiltered = cpuHistory.filter(d => d.timestamp >= cutoff);
        const memFiltered = memHistory.filter(d => d.timestamp >= cutoff);

        // Aggregate to target points
        const cpuAggregated = aggregateData(cpuFiltered, range.points);
        const memAggregated = aggregateData(memFiltered, range.points);

        const datasets = [
            { label: 'CPU', values: cpuAggregated.values, color: 'var(--accent)' },
            { label: 'Memory', values: memAggregated.values, color: 'var(--blue)' },
        ];

        let legend = '<div class="chart-legend">';
        legend += '<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:var(--accent)"></span>CPU</span>';
        legend += '<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:var(--blue)"></span>Memory</span>';
        legend += '</div>';

        // Use timestamps from CPU data (they should be the same as memory)
        const timestamps = cpuAggregated.timestamps;

        el.innerHTML = svgLineChart(datasets, { 
            yMax: 100, 
            fill: true, 
            height: 180, 
            width: 800,
            timestamps: timestamps,
            rangeKey: cpuMemTimeRange
        }) + legend;
    }

    // Color palette for multiple NICs
    const nicColors = [
        'var(--accent)',    // teal
        'var(--orange)',    // orange
        'var(--blue)',      // blue
        'var(--green)',     // green
        'var(--yellow)',    // yellow
        'var(--red)',       // red
        '#a855f7',          // purple
        '#ec4899',          // pink
    ];

    function updateNetHistory(interfaces) {
        if (!interfaces) return;

        const now = Date.now();

        // Update history for each interface
        for (const iface of interfaces) {
            const name = iface.name;
            if (!netHistory[name]) netHistory[name] = [];
            if (!prevNetBytes[name]) prevNetBytes[name] = { rx: iface.bytes_recv, tx: iface.bytes_sent };

            const dRx = Math.max(0, iface.bytes_recv - prevNetBytes[name].rx);
            const dTx = Math.max(0, iface.bytes_sent - prevNetBytes[name].tx);
            // bytes per 5s interval → bytes/s
            const rxRate = Math.round(dRx / 5);
            const txRate = Math.round(dTx / 5);

            netHistory[name].push({ timestamp: now, rx: rxRate, tx: txRate });
            if (netHistory[name].length > MAX_RAW_HISTORY) netHistory[name].shift();

            prevNetBytes[name] = { rx: iface.bytes_recv, tx: iface.bytes_sent };
        }

        renderNetThroughputChart();
    }

    function renderNetThroughputChart() {
        const el = document.getElementById('net-throughput-chart');
        if (!el) return;

        const range = TIME_RANGES[netTimeRange];
        const cutoff = Date.now() - range.seconds * 1000;

        const datasets = [];
        let legend = '<div class="chart-legend">';
        let timestamps = [];

        const ifaceNames = Object.keys(netHistory);
        ifaceNames.forEach((name, idx) => {
            const color = nicColors[idx % nicColors.length];
            const history = netHistory[name] || [];
            
            // Filter to time range
            const filtered = history.filter(d => d.timestamp >= cutoff);
            
            // Aggregate and combine RX+TX
            const combined = filtered.map(d => d.rx + d.tx);
            const aggregated = aggregateData(
                filtered.map((d, i) => ({ timestamp: d.timestamp, value: combined[i] })),
                range.points
            );

            if (aggregated.values.length > 0) {
                datasets.push({
                    label: name,
                    values: aggregated.values,
                    color: color
                });
                legend += `<span class="chart-legend-item"><span class="chart-legend-swatch" style="background:${color}"></span>${name}</span>`;
                // Use timestamps from first interface with data
                if (timestamps.length === 0) {
                    timestamps = aggregated.timestamps;
                }
            }
        });
        legend += '</div>';

        if (datasets.length === 0 || datasets.every(ds => ds.values.length < 2)) {
            el.innerHTML = '<div class="empty-state" style="padding:40px"><h3>Collecting data...</h3><p>Throughput data will appear as traffic flows</p></div>';
            return;
        }

        el.innerHTML = svgLineChart(datasets, { 
            fill: false, 
            height: 200, 
            width: 800,
            timestamps: timestamps,
            rangeKey: netTimeRange
        }) + legend;
    }

    // Aggregate data points to a target number of points, preserving timestamps
    function aggregateData(data, targetPoints) {
        if (data.length === 0) return { values: [], timestamps: [] };
        if (data.length <= targetPoints) {
            return {
                values: data.map(d => d.value),
                timestamps: data.map(d => d.timestamp)
            };
        }

        const bucketSize = Math.ceil(data.length / targetPoints);
        const values = [];
        const timestamps = [];
        
        for (let i = 0; i < data.length; i += bucketSize) {
            const bucket = data.slice(i, i + bucketSize);
            const avg = bucket.reduce((sum, d) => sum + d.value, 0) / bucket.length;
            values.push(Math.round(avg));
            // Use middle timestamp of bucket
            timestamps.push(bucket[Math.floor(bucket.length / 2)].timestamp);
        }

        return { values, timestamps };
    }

    function updateAlertAnalytics(alerts) {
        if (!alerts) alerts = [];

        // Count new alerts since last refresh for rate chart
        const currentCount = alerts.length;
        const newAlerts = Math.max(0, currentCount - prevAlertCount);
        prevAlertCount = currentCount;
        alertRateHistory.push(newAlerts);
        if (alertRateHistory.length > 60) alertRateHistory.shift();

        // Tally severity, source IPs, protocols from the full set
        alertSeverityCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };
        topTalkers = {};
        protocolCounts = {};

        for (const a of alerts) {
            const sev = a.severity || 4;
            alertSeverityCounts[sev] = (alertSeverityCounts[sev] || 0) + 1;

            const srcIp = a.src_ip || '';
            if (srcIp) topTalkers[srcIp] = (topTalkers[srcIp] || 0) + 1;

            const proto = (a.proto || 'OTHER').toUpperCase();
            protocolCounts[proto] = (protocolCounts[proto] || 0) + 1;
        }

        // Alert rate bar chart
        const rateEl = document.getElementById('alert-rate-chart');
        if (rateEl) {
            rateEl.innerHTML = svgBarChart(alertRateHistory, { color: 'var(--orange)', height: 100 });
        }

        // Severity donut
        const sevEl = document.getElementById('severity-chart');
        if (sevEl) {
            sevEl.innerHTML = svgDonut([
                { label: 'Critical', value: alertSeverityCounts[1], color: 'var(--red)' },
                { label: 'High', value: alertSeverityCounts[2], color: 'var(--orange)' },
                { label: 'Medium', value: alertSeverityCounts[3], color: 'var(--yellow)' },
                { label: 'Low', value: alertSeverityCounts[4], color: 'var(--blue)' },
            ]);
        }

        // Top talkers
        const talkEl = document.getElementById('talkers-chart');
        if (talkEl) {
            const sorted = Object.entries(topTalkers)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 6)
                .map(([ip, count]) => ({ label: ip, value: count }));

            if (sorted.length === 0) {
                talkEl.innerHTML = '<div class="empty-state" style="padding:24px"><h3>No data</h3></div>';
            } else {
                talkEl.innerHTML = svgHorizontalBar(sorted, { color: 'var(--accent)' });
            }
        }

        // Protocol donut
        const protoEl = document.getElementById('protocol-chart');
        if (protoEl) {
            const protoColors = { TCP: 'var(--accent)', UDP: 'var(--orange)', ICMP: 'var(--yellow)' };
            const protoSegments = Object.entries(protocolCounts).map(([name, count]) => ({
                label: name,
                value: count,
                color: protoColors[name] || 'var(--blue)',
            }));
            protoEl.innerHTML = svgDonut(protoSegments);
        }
    }

    function updateInterfaces(interfaces) {
        const el = document.getElementById('iface-list');
        if (!interfaces || interfaces.length === 0) {
            el.innerHTML = '<div class="empty-state"><h3>No interfaces found</h3></div>';
            return;
        }

        const items = el.querySelectorAll('.interface-item');
        if (items.length !== interfaces.length) {
            // Interface count changed — full rebuild
            el.innerHTML = interfaces.map(iface => buildIfaceHtml(iface)).join('');
        } else {
            // Update existing items in-place
            interfaces.forEach((iface, i) => {
                const stateClass = iface.state === 'up' ? 'up' : 'down';
                const icon = items[i].querySelector('.interface-icon');
                if (icon) icon.className = 'interface-icon ' + stateClass;
                const nameEl = items[i].querySelector('.interface-name');
                if (nameEl) nameEl.textContent = iface.name;
                const ipEl = items[i].querySelector('.interface-ip');
                if (ipEl) ipEl.textContent = iface.addresses.length ? iface.addresses.join(', ') : 'No IP assigned';
                const byteEls = items[i].querySelectorAll('.stat-bytes');
                if (byteEls[0]) byteEls[0].textContent = formatBytes(iface.bytes_recv);
                if (byteEls[1]) byteEls[1].textContent = formatBytes(iface.bytes_sent);
                const status = items[i].querySelector('.iface-status');
                if (status) { status.className = 'iface-status ' + stateClass; status.textContent = iface.state; }
            });
        }
    }

    function buildIfaceHtml(iface) {
        const stateClass = iface.state === 'up' ? 'up' : 'down';
        return `
            <div class="interface-item">
                <div class="interface-icon ${stateClass}">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="1" y="4" width="22" height="16" rx="2"/>
                        <line x1="1" y1="10" x2="23" y2="10"/>
                    </svg>
                </div>
                <div class="interface-info">
                    <div class="interface-name">${escapeHtml(iface.name)}</div>
                    <div class="interface-ip">${iface.addresses.length ? iface.addresses.join(', ') : 'No IP assigned'}</div>
                </div>
                <div class="interface-stats">
                    <div class="interface-stat">
                        <span class="stat-direction rx">RX</span>
                        <span class="stat-bytes">${formatBytes(iface.bytes_recv)}</span>
                    </div>
                    <div class="interface-stat">
                        <span class="stat-direction tx">TX</span>
                        <span class="stat-bytes">${formatBytes(iface.bytes_sent)}</span>
                    </div>
                </div>
                <span class="iface-status ${stateClass}">${iface.state}</span>
            </div>
        `;
    }

    function updateServices(services) {
        const el = document.getElementById('service-list');
        if (!services || services.length === 0) {
            el.innerHTML = '<div class="empty-state"><h3>No services</h3></div>';
            return;
        }

        const items = el.querySelectorAll('.service-item');
        if (items.length !== services.length) {
            // Service count changed — full rebuild
            el.innerHTML = services.map(svc => buildServiceHtml(svc)).join('');
        } else {
            // Update existing items in-place
            services.forEach((svc, i) => {
                const statusClass = svc.running ? 'online' : 'offline';
                const statusLabel = svc.running ? 'Running' : 'Stopped';
                const name = svc.name.replace('networktap-', '');
                const displayName = name.charAt(0).toUpperCase() + name.slice(1);

                const dot = items[i].querySelector('.status-dot');
                if (dot) dot.className = 'status-dot ' + statusClass;
                const indicator = items[i].querySelector('.service-status-indicator');
                if (indicator) indicator.className = 'service-status-indicator ' + statusClass;
                const nameEl = items[i].querySelector('.service-name');
                if (nameEl) nameEl.textContent = displayName;
                const meta = items[i].querySelector('.service-meta');
                if (meta) meta.textContent = statusLabel + ' - ' + svc.enabled;
            });
        }
    }

    function buildServiceHtml(svc) {
        const name = svc.name.replace('networktap-', '');
        const displayName = name.charAt(0).toUpperCase() + name.slice(1);
        const statusClass = svc.running ? 'online' : 'offline';
        const statusLabel = svc.running ? 'Running' : 'Stopped';
        return `
            <div class="service-item">
                <div class="service-status-indicator ${statusClass}">
                    <span class="status-dot ${statusClass}"></span>
                </div>
                <div class="service-info">
                    <div class="service-name">${escapeHtml(displayName)}</div>
                    <div class="service-meta">${statusLabel} - ${svc.enabled}</div>
                </div>
            </div>
        `;
    }

    function updateTrafficChart(interfaces) {
        const totalPkts = interfaces.reduce((sum, i) => sum + i.packets_recv + i.packets_sent, 0);
        trafficHistory.push(totalPkts);
        if (trafficHistory.length > MAX_TRAFFIC) trafficHistory.shift();

        const deltas = [];
        for (let i = 1; i < trafficHistory.length; i++) {
            deltas.push(Math.max(0, trafficHistory[i] - trafficHistory[i - 1]));
        }

        const maxDelta = Math.max(...deltas, 1);
        const chart = document.getElementById('traffic-chart');
        if (!chart) return;

        // Pad deltas at front so total length = MAX_TRAFFIC - 1
        const totalBars = MAX_TRAFFIC - 1;
        const padded = [];
        for (let i = 0; i < totalBars - deltas.length; i++) padded.push(0);
        for (const d of deltas) padded.push(d);

        const bars = chart.children;
        if (bars.length !== totalBars) {
            // First render or bar count changed — rebuild
            chart.innerHTML = padded.map(d => {
                const pct = Math.max(3, (d / maxDelta) * 100);
                return `<div class="sparkline-bar" style="height:${pct}%" title="${d.toLocaleString()} pkts"></div>`;
            }).join('');
        } else {
            // Batch style updates in a single animation frame to avoid per-bar reflow
            requestAnimationFrame(() => {
                for (let i = 0; i < totalBars; i++) {
                    const pct = Math.max(3, (padded[i] / maxDelta) * 100);
                    bars[i].style.height = pct + '%';
                    bars[i].title = padded[i].toLocaleString() + ' pkts';
                }
            });
        }
    }

    function updateAlertFeed(alerts) {
        const el = document.getElementById('alert-feed');
        // Only show latest 8 in the feed
        const recent = (alerts || []).slice(0, 8);
        if (recent.length === 0) {
            el.innerHTML = '<div class="empty-state"><h3>No recent alerts</h3></div>';
            return;
        }

        const entries = el.querySelectorAll('.alert-entry');
        if (entries.length !== recent.length) {
            // Count changed — full rebuild
            el.innerHTML = recent.map(a => buildAlertEntryHtml(a)).join('');
        } else {
            // Update existing entries in-place
            recent.forEach((a, i) => {
                const sev = entries[i].querySelector('.severity');
                if (sev) { sev.className = 'severity severity-' + (a.severity || 3); sev.textContent = severityLabel(a.severity); }
                const time = entries[i].querySelector('.alert-time');
                if (time) time.textContent = formatTime(a.timestamp);
                const msg = entries[i].querySelector('.alert-msg');
                if (msg) msg.textContent = a.signature || a.message || '';
                const src = entries[i].querySelector('.alert-src');
                if (src) src.textContent = a.source;
            });
        }
    }

    function buildAlertEntryHtml(a) {
        return `
            <div class="alert-entry">
                <span class="severity severity-${a.severity || 3}">${severityLabel(a.severity)}</span>
                <span class="alert-time">${formatTime(a.timestamp)}</span>
                <span class="alert-msg">${escapeHtml(a.signature || a.message || '')}</span>
                <span class="alert-src">${escapeHtml(a.source)}</span>
            </div>
        `;
    }

    function severityLabel(s) {
        switch (s) {
            case 1: return 'CRIT';
            case 2: return 'HIGH';
            case 3: return 'MED';
            default: return 'LOW';
        }
    }

    return { render };
})();
