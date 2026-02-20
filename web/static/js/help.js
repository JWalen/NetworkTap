/* NetworkTap - Help View */

const Help = (() => {
    let currentTab = 'guide';

    async function render(container) {
        container.innerHTML = `
            <div class="settings-tabs" style="display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap;">
                <button class="btn btn-secondary settings-tab active" data-tab="guide">User Guide</button>
                <button class="btn btn-secondary settings-tab" data-tab="changelog">Changelog</button>
            </div>
            <div id="help-content"></div>
        `;

        container.querySelectorAll('.settings-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.settings-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTab = btn.dataset.tab;
                renderTab(container.querySelector('#help-content'));
            });
        });

        renderTab(container.querySelector('#help-content'));
    }

    function renderTab(container) {
        switch (currentTab) {
            case 'guide': renderGuideTab(container); break;
            case 'changelog': renderChangelogTab(container); break;
        }
    }

    function renderGuideTab(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Welcome to NetworkTap</span>
                </div>
                <div class="help-content" style="line-height:1.7;color:var(--text-secondary);">
                    <p>NetworkTap is a network monitoring appliance that combines packet capture, intrusion detection, and traffic analysis in a single dashboard.</p>
                </div>
            </div>

            <div class="card" style="margin-top:24px">
                <div class="card-header">
                    <span class="card-title">Operating Modes</span>
                </div>
                <div class="help-content" style="line-height:1.7;color:var(--text-secondary);">
                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">SPAN Mode (Default)</h4>
                    <p>In SPAN mode, NIC1 passively monitors traffic from a switch SPAN/mirror port. NIC2 serves as the management interface for accessing this dashboard and SSH.</p>
                    <ul style="margin:8px 0;padding-left:24px;">
                        <li>Connect NIC1 to your switch's SPAN/mirror port</li>
                        <li>Connect NIC2 to your management network</li>
                        <li>NIC1 operates in promiscuous mode with no IP address</li>
                    </ul>

                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">Bridge Mode</h4>
                    <p>In bridge mode, NIC1 and NIC2 form a transparent Layer 2 bridge. Traffic passes through the appliance for inline inspection.</p>
                    <ul style="margin:8px 0;padding-left:24px;">
                        <li>Insert the appliance inline between network segments</li>
                        <li>All traffic is inspected as it passes through</li>
                        <li>Management IP is assigned to the bridge interface</li>
                    </ul>

                    <p style="margin-top:12px;">Switch modes from the <a href="#network" style="color:var(--accent);">Network</a> page.</p>
                </div>
            </div>

            <div class="card" style="margin-top:24px">
                <div class="card-header">
                    <span class="card-title">Pages Overview</span>
                </div>
                <div class="help-content" style="line-height:1.7;color:var(--text-secondary);">
                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">📊 Dashboard</h4>
                        <p>System overview with CPU, memory, disk, and uptime stats. Shows service status, network throughput per interface, and recent security alerts.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🎯 Captures</h4>
                        <p>Start and stop packet capture. View recent capture files. Captures are automatically rotated based on time intervals and compressed to save storage.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">⚠️ Alerts</h4>
                        <p>Real-time security alerts from Suricata IDS and Zeek network monitor. Filter by source and search alert messages. Alerts update via WebSocket without refreshing.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🌐 Network</h4>
                        <p>View interface status and traffic statistics. Switch between SPAN and Bridge modes. Configure static IP for the management interface.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">📁 PCAPs</h4>
                        <p>Browse, search, and download captured packet files. View storage usage and retention settings. Filter packets with BPF expressions before download. In-browser packet viewer with display filters and stream following.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">📋 Zeek Logs</h4>
                        <p>Browse and search Zeek network logs (conn, dns, http, ssl, files, notice, weird). Filter by IP, port, protocol, or time range. Click any row to see full entry details.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">📈 Statistics</h4>
                        <p>Traffic analytics from Zeek connection logs. View connection trends over time, DNS analytics (top domains, query types), service distribution, protocol breakdown, and top talkers.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🤖 AI Analysis</h4>
                        <p>AI-powered network analysis. Anomaly detection identifies traffic spikes, port scans, beaconing, and DNS threats. AI Assistant answers questions about your network activity using on-device LLM.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">📡 WiFi</h4>
                        <p>Comprehensive wireless security platform with 7 tabs:</p>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Overview:</strong> All wireless features at a glance</li>
                            <li><strong>Client Mode:</strong> Connect to WiFi networks, scan for SSIDs</li>
                            <li><strong>Access Point:</strong> Create wireless hotspot (WPA2-PSK), track clients</li>
                            <li><strong>Packet Capture:</strong> Monitor mode 802.11 frame capture</li>
                            <li><strong>Site Survey:</strong> Signal analysis, channel utilization mapping</li>
                            <li><strong>Wireless IDS:</strong> Rogue AP detection, alert management</li>
                            <li><strong>Client Tracking:</strong> Device inventory, vendor identification</li>
                        </ul>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">⬆️ Updates</h4>
                        <p>Software update management from GitHub releases. Check for updates, download and install with automatic backup, view update history, and rollback if needed. All updates are SHA256-verified.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🛡️ Rules</h4>
                        <p>Manage Suricata IDS rules. Browse rule files, search rules, enable/disable individual rules, and reload the rule set.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">💻 Terminal</h4>
                        <p>Limited terminal access for diagnostics. Allowed commands include: ip, tcpdump, ss, netstat, ping, traceroute, journalctl, systemctl, df, free, uptime, cat.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">⚙️ Settings</h4>
                        <p>Manage your login credentials, user accounts (admin only), backup and restore configuration, and system settings.</p>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Authentication:</strong> Browser credentials and server password management</li>
                            <li><strong>Users:</strong> Add/edit/delete users with admin or viewer roles</li>
                            <li><strong>Backup & Restore:</strong> Create and restore configuration backups</li>
                            <li><strong>Power:</strong> Reboot the appliance (double confirmation required)</li>
                            <li><strong>Configuration:</strong> Edit all system settings including capture, retention, IDS, display, AI, and more</li>
                        </ul>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🖥️ FR202 Front Panel Display</h4>
                        <p>The OnLogic FR202 has a 3.5" front panel touchscreen showing system status across 5 pages. Tap to cycle pages, auto-dims or shows screensaver after idle timeout.</p>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Dashboard:</strong> Mode, IP, CPU/MEM/DISK bars, service status</li>
                            <li><strong>Network:</strong> All interfaces with IP, state, speed, MAC</li>
                            <li><strong>Services:</strong> All services with status and uptime</li>
                            <li><strong>Alerts:</strong> Event counts, severity breakdown, top signatures</li>
                            <li><strong>System:</strong> Hostname, uptime, temp, kernel, storage, version</li>
                        </ul>
                        <p>Configure display settings (refresh, timeout, screensaver, color) in <a href="#settings" style="color:var(--accent);">Settings</a> > Configuration > Display.</p>
                    </div>
                </div>
            </div>

            <div class="card" style="margin-top:24px">
                <div class="card-header">
                    <span class="card-title">Quick Tips</span>
                </div>
                <div class="help-content" style="line-height:1.7;color:var(--text-secondary);">
                    <ul style="padding-left:24px;">
                        <li><strong>Status Dots:</strong> Green = running/connected, Yellow = warning, Red = stopped/error</li>
                        <li><strong>Theme:</strong> Click the sun/moon icon in the top bar to toggle dark/light mode</li>
                        <li><strong>WebSocket:</strong> The "Live" indicator shows if real-time alerts are connected</li>
                        <li><strong>Credentials:</strong> Browser credentials are stored locally. Change server passwords in Settings → Users</li>
                        <li><strong>Backups:</strong> Regular backups are recommended before making configuration changes</li>
                        <li><strong>Storage:</strong> PCAPs are automatically cleaned up based on retention settings (default: 7 days)</li>
                    </ul>
                </div>
            </div>

            <div class="card" style="margin-top:24px">
                <div class="card-header">
                    <span class="card-title">Troubleshooting</span>
                </div>
                <div class="help-content" style="line-height:1.7;color:var(--text-secondary);">
                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">Service Won't Start</h4>
                    <p>Check service logs: <code>sudo journalctl -u networktap-capture -n 50</code></p>

                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">No Traffic Captured</h4>
                    <ul style="padding-left:24px;margin:8px 0;">
                        <li>Verify the capture interface is connected and up</li>
                        <li>Check that the switch SPAN port is configured correctly</li>
                        <li>Ensure the interface is in promiscuous mode</li>
                    </ul>

                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">WebSocket Disconnected</h4>
                    <p>The connection will automatically reconnect. If persistent, check that the web service is running.</p>

                    <h4 style="color:var(--text-primary);margin:16px 0 8px;">Health Check</h4>
                    <p>Run the health check script: <code>sudo /opt/networktap/scripts/health_check.sh</code></p>
                </div>
            </div>
        `;
    }

    function renderChangelogTab(container) {
        const versions = [
            {
                ver: '1.0.29', date: 'February 2026', title: 'Performance Optimizations',
                sections: [{
                    heading: 'Performance',
                    items: [
                        'Non-blocking CPU monitoring — no longer freezes the server for 500ms per poll',
                        'Dashboard refresh slowed from 5s to 10s — halves load on CM4',
                        'Alert fetch limit reduced from 200 to 20 on dashboard',
                        'TTL caching on alerts API, capture status, Zeek conn.log parsing',
                        'lru_cache on binary path lookups, port name resolution',
                        'heapq.nlargest for efficient top-N queries',
                        'Debounced filter inputs and sparkline bar batching',
                    ]
                }]
            },
            {
                ver: '1.0.27', date: 'February 2026', title: 'NIC Swap & Reboot',
                sections: [
                    { heading: 'Changed', items: ['Swapped NIC assignments: eth1 = capture, eth0 = management'] },
                    { heading: 'Added', items: ['Reboot button in Settings > Power with double confirmation', 'POST /api/system/reboot endpoint (admin only)'] },
                ]
            },
            {
                ver: '1.0.26', date: 'February 2026', title: 'Clearer Logo & Color Picker',
                sections: [{
                    heading: 'Changed',
                    items: [
                        'Larger clearer logo — "NETWORK" at 36px and "TAP" at 28px using bold font',
                        'Logo moved up to fit 64px clock on screen',
                        'Screensaver color picker in Settings > Configuration > Display with 9 preset swatches',
                    ]
                }]
            },
            {
                ver: '1.0.23', date: 'February 2026', title: 'Screensaver & Display Settings',
                sections: [{
                    heading: 'Added',
                    items: [
                        'Boot splash — ASCII art "NETWORKTAP" logo on startup',
                        'Screensaver mode — pulsing logo + large clock on idle timeout',
                        'Screensaver on/off toggle in Settings > Configuration > Display',
                        'Display settings in web UI — refresh interval, backlight timeout, default page',
                    ]
                }]
            },
            {
                ver: '1.0.21', date: 'February 2026', title: 'Config Save Fix',
                sections: [{ heading: 'Fixed', items: ['Fixed "failed to save" error when saving config (double JSON.stringify bug)'] }]
            },
            {
                ver: '1.0.20', date: 'February 2026', title: 'Power LED Fix',
                sections: [{ heading: 'Fixed', items: ['Auto-corrects FR202 power LED config in config.txt'] }]
            },
            {
                ver: '1.0.17', date: 'February 2026', title: 'Multi-Page Touch Display',
                sections: [{
                    heading: 'Added',
                    items: [
                        '5-page touch display for FR202 front panel (Dashboard, Network, Services, Alerts, System)',
                        'Touch navigation via ST1633i controller on I2C bus 5',
                        'Page indicator dots, auto-dim backlight, tap to wake',
                    ]
                }]
            },
            {
                ver: '1.0.9', date: 'February 2026', title: 'FR202 Display Support',
                sections: [{ heading: 'Added', items: ['Initial FR202 front panel display support (ST7789V 3.5" TFT on SPI3)', 'Display service and setup script'] }]
            },
            {
                ver: '1.1.0', date: 'February 2026', title: 'WiFi Security Platform',
                sections: [{
                    heading: 'Added',
                    items: [
                        'WiFi Management UI — 7-tab interface: Overview, Client, AP, Capture, Survey, IDS, Tracking',
                        'Auto-Update system — GitHub releases with SHA256 verification, backup, rollback',
                        'WiFi Access Point, Packet Capture, Site Survey, Wireless IDS, Client Tracking',
                        '25 new WiFi + 9 update API endpoints',
                    ]
                }]
            },
            {
                ver: '1.0.0', date: 'February 2026', title: 'AI Features',
                sections: [{
                    heading: 'Added',
                    items: [
                        'AI Anomaly Detection — volume anomalies, port/host scans, beaconing, DNS DGA/tunneling',
                        'AI Assistant — on-device LLM (TinyLLaMA via Ollama)',
                    ]
                }]
            },
            {
                ver: '0.3.0', date: 'February 2026', title: 'Packet Viewer',
                sections: [{ heading: 'Added', items: ['In-browser packet inspection with protocol coloring', 'Wireshark-style display filters', 'TCP/UDP stream following'] }]
            },
            {
                ver: '0.2.0', date: 'February 2026', title: 'Zeek Logs & Statistics',
                sections: [{ heading: 'Added', items: ['Zeek Log Browser — conn, dns, http, ssl, files, notice, weird', 'Traffic statistics with connection trends and DNS analytics', 'PCAP filtering with BPF expressions'] }]
            },
            {
                ver: '0.1.0', date: 'February 2026', title: 'Initial Release',
                sections: [{ heading: 'Added', items: ['SPAN and Bridge network modes', 'tcpdump packet capture with rotation', 'Suricata IDS and Zeek integration', 'FastAPI web dashboard with real-time WebSocket alerts', 'Multi-user auth, TLS, backup/restore, syslog forwarding', 'systemd services, firewall hardening, health checks'] }]
            },
        ];

        const html = versions.map((v, i) => {
            const sects = v.sections.map(s =>
                '<h4 style="color:var(--text-primary);margin:12px 0 6px;">' + s.heading + '</h4>' +
                '<ul style="padding-left:24px;margin:4px 0;">' +
                s.items.map(item => '<li>' + item + '</li>').join('') +
                '</ul>'
            ).join('');
            const hr = i < versions.length - 1 ? '<hr style="border:none;border-top:1px solid var(--border-color);margin:20px 0;">' : '';
            return '<div class="changelog-version">' +
                '<h3 style="color:var(--accent);margin:0 0 4px;">v' + v.ver +
                ' <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">' + v.date + ' &mdash; ' + v.title + '</span></h3>' +
                sects + '</div>' + hr;
        }).join('');

        container.innerHTML = '<div class="card"><div class="card-header"><span class="card-title">Version History</span></div>' +
            '<div class="changelog-content" style="line-height:1.6;color:var(--text-secondary);">' + html + '</div></div>';
    }

    return { render };
})();
