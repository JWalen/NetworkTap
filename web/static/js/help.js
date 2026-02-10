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
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">🛡️ Rules</h4>
                        <p>Manage Suricata IDS rules. Browse rule files, search rules, enable/disable individual rules, and reload the rule set.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">💻 Terminal</h4>
                        <p>Limited terminal access for diagnostics. Allowed commands include: ip, tcpdump, ss, netstat, ping, traceroute, journalctl, systemctl, df, free, uptime, cat.</p>
                    </div>

                    <div class="help-section">
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">⚙️ Settings</h4>
                        <p>Manage your login credentials, user accounts (admin only), backup and restore configuration, and view system settings.</p>
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
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Version History</span>
                </div>
                <div class="changelog-content" style="line-height:1.7;color:var(--text-secondary);">
                    
                    <div class="changelog-version">
                        <h3 style="color:var(--accent);margin:0 0 8px;">v1.0.0 <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">February 2026</span></h3>
                        
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Added</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>AI Anomaly Detection</strong> - Lightweight statistical detection of traffic anomalies, port scans, host scans, beaconing (C2), and DNS threats (DGA, tunneling)</li>
                            <li><strong>AI Assistant</strong> - On-device LLM (TinyLLaMA via Ollama) for natural language network analysis</li>
                            <li><strong>AI Analysis Page</strong> - Dashboard for anomaly results, AI chat, and feature toggles</li>
                        </ul>

                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Fixed</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Traffic Statistics</strong> - Fixed timezone bug where UTC timestamps were incorrectly compared</li>
                        </ul>
                    </div>

                    <hr style="border:none;border-top:1px solid var(--border-color);margin:24px 0;">

                    <div class="changelog-version">
                        <h3 style="color:var(--accent);margin:0 0 8px;">v0.3.0 <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">February 2026</span></h3>
                        
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Added</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Packet Viewer</strong> - In-browser packet inspection with protocol coloring, layer details, hex dump</li>
                            <li><strong>Display Filters</strong> - Wireshark-style filter syntax for packet viewing</li>
                            <li><strong>Stream Following</strong> - View TCP/UDP stream content in ASCII or hex</li>
                        </ul>
                    </div>

                    <hr style="border:none;border-top:1px solid var(--border-color);margin:24px 0;">

                    <div class="changelog-version">
                        <h3 style="color:var(--accent);margin:0 0 8px;">v0.2.0 <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">February 2026</span></h3>
                        
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Added</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Zeek Log Browser</strong> - Browse, filter, and search Zeek logs (conn, dns, http, ssl, files, notice, weird)</li>
                            <li><strong>Enhanced Statistics</strong> - Connection trends chart, DNS analytics, service distribution</li>
                            <li><strong>PCAP Filtering</strong> - BPF filter builder, preview matching packets, download filtered PCAPs</li>
                            <li><strong>UI Modernization</strong> - Page transitions, skeleton loading, animated values, hover effects</li>
                        </ul>
                    </div>

                    <hr style="border:none;border-top:1px solid var(--border-color);margin:24px 0;">

                    <div class="changelog-version">
                        <h3 style="color:var(--accent);margin:0 0 8px;">v0.1.0 <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">February 2026</span></h3>
                        
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Added</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>HTTPS/TLS Support</strong> - Self-signed certificate generation, optional Let's Encrypt integration</li>
                            <li><strong>Multi-user Authentication</strong> - Role-based access control (admin/viewer), PBKDF2 password hashing</li>
                            <li><strong>Traffic Statistics</strong> - Bandwidth charts, protocol distribution, top talkers, top ports from Zeek data</li>
                            <li><strong>PCAP Search/Preview</strong> - Search packets by IP, port, protocol; view connection summaries</li>
                            <li><strong>Suricata Rules Management</strong> - Browse, search, enable/disable rules; threshold configuration; live reload</li>
                            <li><strong>Backup & Restore</strong> - Configuration backup/restore with automatic pre-restore snapshots</li>
                            <li><strong>Syslog Forwarding</strong> - Remote syslog/SIEM integration (UDP/TCP, syslog/JSON format)</li>
                            <li><strong>Report Export</strong> - CSV, HTML, and JSON report generation for alerts and statistics</li>
                            <li><strong>Dark/Light Theme</strong> - Toggle between themes with preference persistence</li>
                            <li><strong>Mobile Responsive</strong> - Improved touch targets, hamburger menu, responsive layouts</li>
                        </ul>
                    </div>

                    <hr style="border:none;border-top:1px solid var(--border-color);margin:24px 0;">

                    <div class="changelog-version">
                        <h3 style="color:var(--accent);margin:0 0 8px;">v0.0.1-beta <span style="color:var(--text-muted);font-weight:normal;font-size:0.85rem;">February 2026</span></h3>
                        
                        <h4 style="color:var(--text-primary);margin:16px 0 8px;">Initial Release</h4>
                        <ul style="padding-left:24px;margin:8px 0;">
                            <li><strong>Operating modes</strong> - SPAN/mirror and inline transparent bridge</li>
                            <li><strong>Packet capture</strong> - tcpdump with time-based rotation, file limits, BPF filtering, and gzip compression</li>
                            <li><strong>Suricata IDS</strong> - af-packet capture, EVE JSON logging, community-id, automatic rule updates</li>
                            <li><strong>Zeek IDS</strong> - JSON logging, standard protocol analyzers, connection tracking</li>
                            <li><strong>FastAPI web backend</strong> - REST API for system status, capture control, alerts, configuration</li>
                            <li><strong>WebSocket</strong> - Real-time Suricata alert streaming to the dashboard</li>
                            <li><strong>Web dashboard</strong> - Dark-themed SPA with Dashboard, Captures, Alerts, Network, PCAPs, Settings pages</li>
                            <li><strong>Authentication</strong> - HTTP Basic auth for all API endpoints</li>
                            <li><strong>systemd services</strong> - Units for capture, Suricata, Zeek, web dashboard, and storage cleanup</li>
                            <li><strong>Storage management</strong> - Automatic pcap retention enforcement, emergency cleanup on low disk</li>
                            <li><strong>Firewall hardening</strong> - UFW rules scoped to management interface</li>
                            <li><strong>Health check script</strong> - Validates services, interfaces, disk space, and memory</li>
                            <li><strong>Installer/Uninstaller</strong> - Automated setup and clean removal</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    return { render };
})();
