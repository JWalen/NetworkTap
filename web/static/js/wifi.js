// WiFi Management Page
const WiFi = (() => {
    let currentTab = 'overview';
    let statusInterval = null;

    async function render(container) {
        container.innerHTML = `
            <div class="page-header">
                <h1>WiFi Management</h1>
                <p>Wireless networking, security, and analysis</p>
            </div>

            <div class="tabs">
                <button class="tab-button active" data-tab="overview">Overview</button>
                <button class="tab-button" data-tab="client">Client Mode</button>
                <button class="tab-button" data-tab="ap">Access Point</button>
                <button class="tab-button" data-tab="capture">Packet Capture</button>
                <button class="tab-button" data-tab="survey">Site Survey</button>
                <button class="tab-button" data-tab="ids">Wireless IDS</button>
                <button class="tab-button" data-tab="tracking">Client Tracking</button>
            </div>

            <div class="tab-content" id="wifi-content"></div>
        `;

        // Tab switching
        container.querySelectorAll('.tab-button').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTab = btn.dataset.tab;
                renderTab(container.querySelector('#wifi-content'));
            });
        });

        renderTab(container.querySelector('#wifi-content'));
        startPolling();
    }

    function startPolling() {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(() => {
            if (currentTab === 'overview') {
                loadOverview();
            } else if (currentTab === 'ap') {
                loadAPStatus();
            } else if (currentTab === 'capture') {
                loadCaptureStatus();
            }
        }, 5000);
    }

    function renderTab(container) {
        switch (currentTab) {
            case 'overview':
                renderOverview(container);
                break;
            case 'client':
                renderClientMode(container);
                break;
            case 'ap':
                renderAccessPoint(container);
                break;
            case 'capture':
                renderPacketCapture(container);
                break;
            case 'survey':
                renderSiteSurvey(container);
                break;
            case 'ids':
                renderWirelessIDS(container);
                break;
            case 'tracking':
                renderClientTracking(container);
                break;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // OVERVIEW TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderOverview(container) {
        container.innerHTML = `
            <div class="grid-3">
                <div class="card">
                    <div class="card-header">Client Mode</div>
                    <div id="client-status">Loading...</div>
                </div>
                <div class="card">
                    <div class="card-header">Access Point</div>
                    <div id="ap-status">Loading...</div>
                </div>
                <div class="card">
                    <div class="card-header">Packet Capture</div>
                    <div id="capture-status">Loading...</div>
                </div>
            </div>

            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Recent Wireless Alerts</div>
                    <div id="recent-alerts">Loading...</div>
                </div>
                <div class="card">
                    <div class="card-header">Tracked Clients</div>
                    <div id="tracked-clients">Loading...</div>
                </div>
            </div>
        `;

        loadOverview();
    }

    async function loadOverview() {
        try {
            // Client mode status
            const clientStatus = await api('/api/wifi/status');
            document.getElementById('client-status').innerHTML = clientStatus.connected 
                ? `<div class="status-good">Connected to ${clientStatus.ssid || 'network'}</div>
                   <div class="stat-row"><span>IP:</span><span>${clientStatus.ip || 'N/A'}</span></div>`
                : '<div class="status-warn">Not connected</div>';

            // AP status
            const apStatus = await api('/api/wifi/ap/status');
            document.getElementById('ap-status').innerHTML = apStatus.running
                ? `<div class="status-good">Running</div>
                   <div class="stat-row"><span>SSID:</span><span>${apStatus.ssid || 'N/A'}</span></div>
                   <div class="stat-row"><span>Clients:</span><span>${apStatus.clients || 0}</span></div>`
                : '<div class="status-off">Stopped</div>';

            // Capture status
            const captureStatus = await api('/api/wifi/capture/status');
            document.getElementById('capture-status').innerHTML = captureStatus.running
                ? `<div class="status-good">Active</div>
                   <div class="stat-row"><span>Channel:</span><span>${captureStatus.channel || 'N/A'}</span></div>
                   <div class="stat-row"><span>Files:</span><span>${captureStatus.file_count || 0}</span></div>`
                : '<div class="status-off">Stopped</div>';

            // Recent alerts
            const alerts = await api('/api/wifi/ids/alerts?since_minutes=60');
            const alertsHtml = alerts.alerts && alerts.alerts.length > 0
                ? alerts.alerts.slice(0, 5).map(a => `
                    <div class="alert-item severity-${a.severity}">
                        <strong>${a.type}</strong> - ${a.details}
                        <div class="alert-meta">${new Date(a.timestamp).toLocaleString()}</div>
                    </div>
                `).join('')
                : '<div class="empty-state">No recent wireless alerts</div>';
            document.getElementById('recent-alerts').innerHTML = alertsHtml;

            // Tracked clients
            const clients = await api('/api/wifi/clients/stats');
            document.getElementById('tracked-clients').innerHTML = `
                <div class="stat-row"><span>Total:</span><span>${clients.total_clients || 0}</span></div>
                <div class="stat-row"><span>Active:</span><span>${clients.active_clients || 0}</span></div>
            `;
        } catch (error) {
            console.error('Error loading overview:', error);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CLIENT MODE TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderClientMode(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">WiFi Client Status</div>
                <div id="client-details">Loading...</div>
            </div>

            <div class="card">
                <div class="card-header">Available Networks</div>
                <button class="btn btn-primary" onclick="WiFi.scanNetworks()">
                    <i class="icon">📡</i> Scan Networks
                </button>
                <div id="network-list" style="margin-top: 1rem;">Click scan to see available networks</div>
            </div>

            <div class="card">
                <div class="card-header">Connect to Network</div>
                <form id="connect-form">
                    <div class="form-group">
                        <label>SSID</label>
                        <input type="text" id="connect-ssid" required>
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="connect-psk" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Connect</button>
                    <button type="button" class="btn btn-secondary" onclick="WiFi.disconnect()">Disconnect</button>
                </form>
            </div>
        `;

        loadClientStatus();

        document.getElementById('connect-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const ssid = document.getElementById('connect-ssid').value;
            const psk = document.getElementById('connect-psk').value;

            try {
                const result = await api('/api/wifi/connect', {
                    method: 'POST',
                    body: JSON.stringify({ ssid, psk })
                });
                
                toast(result.success ? result.message : 'Connection failed', result.success ? 'success' : 'error');
                if (result.success) loadClientStatus();
            } catch (error) {
                toast('Failed to connect: ' + error.message, 'error');
            }
        });
    }

    async function loadClientStatus() {
        try {
            const status = await api('/api/wifi/status');
            const html = status.connected 
                ? `
                    <div class="status-good">Connected</div>
                    <div class="stat-row"><span>SSID:</span><span>${status.ssid || 'N/A'}</span></div>
                    <div class="stat-row"><span>IP Address:</span><span>${status.ip || 'N/A'}</span></div>
                    <div class="stat-row"><span>State:</span><span>${status.state || 'N/A'}</span></div>
                `
                : '<div class="status-warn">Not connected to any network</div>';
            
            document.getElementById('client-details').innerHTML = html;
        } catch (error) {
            document.getElementById('client-details').innerHTML = '<div class="status-error">Error loading status</div>';
        }
    }

    window.WiFi = window.WiFi || {};
    window.WiFi.scanNetworks = async function() {
        const listEl = document.getElementById('network-list');
        listEl.innerHTML = '<div class="loading">Scanning... (this may take up to 30 seconds)</div>';
        
        try {
            const result = await api('/api/wifi/scan');
            if (result.networks && result.networks.length > 0) {
                listEl.innerHTML = `
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>SSID</th>
                                <th>Signal</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${result.networks.map(n => `
                                <tr>
                                    <td>${n.ssid}</td>
                                    <td>${n.raw}</td>
                                    <td>
                                        <button class="btn btn-sm" onclick="document.getElementById('connect-ssid').value='${n.ssid}'">
                                            Select
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            } else {
                listEl.innerHTML = '<div class="empty-state">No networks found</div>';
            }
        } catch (error) {
            listEl.innerHTML = `<div class="status-error">Scan failed: ${error.message}</div>`;
        }
    };

    window.WiFi.disconnect = async function() {
        try {
            const result = await api('/api/wifi/disconnect', { method: 'POST' });
            toast(result.message || 'Disconnected', 'success');
            loadClientStatus();
        } catch (error) {
            toast('Failed to disconnect: ' + error.message, 'error');
        }
    };

    // ═══════════════════════════════════════════════════════════════════════
    // ACCESS POINT TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderAccessPoint(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">Access Point Status</div>
                <div id="ap-details">Loading...</div>
                <div class="button-group" style="margin-top: 1rem;">
                    <button class="btn btn-success" onclick="WiFi.startAP()">Start AP</button>
                    <button class="btn btn-danger" onclick="WiFi.stopAP()">Stop AP</button>
                    <button class="btn btn-primary" onclick="WiFi.restartAP()">Restart AP</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Connected Clients</div>
                <div id="ap-clients">Loading...</div>
            </div>

            <div class="card">
                <div class="card-header">AP Configuration</div>
                <form id="ap-config-form">
                    <div class="form-group">
                        <label>SSID</label>
                        <input type="text" id="ap-ssid" placeholder="NetworkTap-Admin" required>
                    </div>
                    <div class="form-group">
                        <label>Password (WPA2)</label>
                        <input type="password" id="ap-password" placeholder="Min 8 characters" required minlength="8">
                    </div>
                    <div class="form-group">
                        <label>Channel</label>
                        <select id="ap-channel">
                            ${[1,2,3,4,5,6,7,8,9,10,11].map(ch => `<option value="${ch}">${ch}</option>`).join('')}
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">Update Configuration</button>
                    <p class="help-text">Note: Requires AP restart to apply changes</p>
                </form>
            </div>
        `;

        loadAPStatus();
    }

    async function loadAPStatus() {
        try {
            const status = await api('/api/wifi/ap/status');
            const detailsHtml = `
                <div class="${status.running ? 'status-good' : 'status-off'}">
                    ${status.running ? 'Running' : 'Stopped'}
                </div>
                ${status.running ? `
                    <div class="stat-row"><span>SSID:</span><span>${status.ssid || 'N/A'}</span></div>
                    <div class="stat-row"><span>Channel:</span><span>${status.channel || 'N/A'}</span></div>
                    <div class="stat-row"><span>IP:</span><span>${status.ip || 'N/A'}</span></div>
                    <div class="stat-row"><span>Clients:</span><span>${status.clients || 0}</span></div>
                ` : ''}
            `;
            document.getElementById('ap-details').innerHTML = detailsHtml;

            // Load clients
            const clients = await api('/api/wifi/ap/clients');
            const clientsHtml = clients.clients && clients.clients.length > 0
                ? `<table class="data-table">
                    <thead><tr><th>MAC Address</th><th>Hostname</th></tr></thead>
                    <tbody>
                        ${clients.clients.map(c => `
                            <tr>
                                <td><code>${c.mac}</code></td>
                                <td>${c.hostname || 'Unknown'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`
                : '<div class="empty-state">No clients connected</div>';
            document.getElementById('ap-clients').innerHTML = clientsHtml;

        } catch (error) {
            document.getElementById('ap-details').innerHTML = '<div class="status-error">Error loading status</div>';
        }
    }

    window.WiFi.startAP = async function() {
        try {
            const result = await api('/api/wifi/ap/start', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadAPStatus, 2000);
        } catch (error) {
            toast('Failed to start AP: ' + error.message, 'error');
        }
    };

    window.WiFi.stopAP = async function() {
        try {
            const result = await api('/api/wifi/ap/stop', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadAPStatus, 1000);
        } catch (error) {
            toast('Failed to stop AP: ' + error.message, 'error');
        }
    };

    window.WiFi.restartAP = async function() {
        try {
            const result = await api('/api/wifi/ap/restart', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadAPStatus, 3000);
        } catch (error) {
            toast('Failed to restart AP: ' + error.message, 'error');
        }
    };

    document.addEventListener('submit', async (e) => {
        if (e.target.id === 'ap-config-form') {
            e.preventDefault();
            try {
                const config = {
                    ssid: document.getElementById('ap-ssid').value,
                    passphrase: document.getElementById('ap-password').value,
                    channel: parseInt(document.getElementById('ap-channel').value)
                };
                
                const result = await api('/api/wifi/ap/configure', {
                    method: 'POST',
                    body: JSON.stringify(config)
                });
                
                toast(result.message, result.success ? 'success' : 'error');
            } catch (error) {
                toast('Failed to update config: ' + error.message, 'error');
            }
        }
    });

    // ═══════════════════════════════════════════════════════════════════════
    // PACKET CAPTURE TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderPacketCapture(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">Capture Status</div>
                <div id="capture-details">Loading...</div>
                <div class="button-group" style="margin-top: 1rem;">
                    <button class="btn btn-success" onclick="WiFi.startCapture()">Start Capture</button>
                    <button class="btn btn-danger" onclick="WiFi.stopCapture()">Stop Capture</button>
                    <button class="btn btn-primary" onclick="WiFi.restartCapture()">Restart</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Capture Files</div>
                <button class="btn btn-secondary" onclick="WiFi.loadCaptureFiles()">
                    <i class="icon">🔄</i> Refresh
                </button>
                <div id="capture-files" style="margin-top: 1rem;">Loading...</div>
            </div>
        `;

        loadCaptureStatus();
        loadCaptureFiles();
    }

    async function loadCaptureStatus() {
        try {
            const status = await api('/api/wifi/capture/status');
            const html = `
                <div class="${status.running ? 'status-good' : 'status-off'}">
                    ${status.running ? 'Running' : 'Stopped'}
                </div>
                ${status.enabled !== undefined ? `<div class="stat-row"><span>Enabled:</span><span>${status.enabled ? 'Yes' : 'No'}</span></div>` : ''}
                ${status.channel ? `<div class="stat-row"><span>Channel:</span><span>${status.channel}</span></div>` : ''}
                ${status.file_count !== undefined ? `<div class="stat-row"><span>Files:</span><span>${status.file_count}</span></div>` : ''}
                ${status.total_size ? `<div class="stat-row"><span>Total Size:</span><span>${status.total_size}</span></div>` : ''}
            `;
            document.getElementById('capture-details').innerHTML = html;
        } catch (error) {
            document.getElementById('capture-details').innerHTML = '<div class="status-error">Error loading status</div>';
        }
    }

    async function loadCaptureFiles() {
        try {
            const result = await api('/api/wifi/capture/list');
            const filesHtml = result.captures && result.captures.length > 0
                ? `<table class="data-table">
                    <thead><tr><th>Filename</th><th>Size</th><th>Date</th></tr></thead>
                    <tbody>
                        ${result.captures.map(f => `
                            <tr>
                                <td><code>${f.filename}</code></td>
                                <td>${f.size}</td>
                                <td>${f.date}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`
                : '<div class="empty-state">No capture files found</div>';
            document.getElementById('capture-files').innerHTML = filesHtml;
        } catch (error) {
            document.getElementById('capture-files').innerHTML = '<div class="status-error">Error loading files</div>';
        }
    }

    window.WiFi.loadCaptureFiles = loadCaptureFiles;

    window.WiFi.startCapture = async function() {
        try {
            const result = await api('/api/wifi/capture/start', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadCaptureStatus, 2000);
        } catch (error) {
            toast('Failed to start capture: ' + error.message, 'error');
        }
    };

    window.WiFi.stopCapture = async function() {
        try {
            const result = await api('/api/wifi/capture/stop', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadCaptureStatus, 1000);
        } catch (error) {
            toast('Failed to stop capture: ' + error.message, 'error');
        }
    };

    window.WiFi.restartCapture = async function() {
        try {
            const result = await api('/api/wifi/capture/restart', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(loadCaptureStatus, 3000);
        } catch (error) {
            toast('Failed to restart capture: ' + error.message, 'error');
        }
    };

    // ═══════════════════════════════════════════════════════════════════════
    // SITE SURVEY TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderSiteSurvey(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">WiFi Site Survey</div>
                <button class="btn btn-primary" onclick="WiFi.runSurvey()">
                    <i class="icon">📡</i> Run Survey
                </button>
                <p class="help-text">Scans for nearby access points and analyzes signal strength</p>
            </div>

            <div class="card">
                <div class="card-header">Access Points</div>
                <div id="survey-results">Run a survey to see results</div>
            </div>

            <div class="card">
                <div class="card-header">Channel Utilization</div>
                <div id="channel-chart">No data</div>
            </div>
        `;

        loadSurveyResults();
    }

    window.WiFi.runSurvey = async function() {
        const resultsEl = document.getElementById('survey-results');
        resultsEl.innerHTML = '<div class="loading">Running survey... (may take up to 30 seconds)</div>';
        
        try {
            const result = await api('/api/wifi/survey/run', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) {
                setTimeout(loadSurveyResults, 2000);
            }
        } catch (error) {
            toast('Survey failed: ' + error.message, 'error');
            resultsEl.innerHTML = `<div class="status-error">Survey failed: ${error.message}</div>`;
        }
    };

    async function loadSurveyResults() {
        try {
            const results = await api('/api/wifi/survey/results');
            
            if (!results.access_points || results.access_points.length === 0) {
                document.getElementById('survey-results').innerHTML = '<div class="empty-state">No access points found. Run a survey.</div>';
                return;
            }

            // AP table
            const apsHtml = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>BSSID</th>
                            <th>SSID</th>
                            <th>Channel</th>
                            <th>Signal</th>
                            <th>Security</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${results.access_points.map(ap => `
                            <tr>
                                <td><code>${ap.bssid}</code></td>
                                <td>${ap.ssid || '<hidden>'}</td>
                                <td>${ap.channel}</td>
                                <td>${ap.signal} dBm</td>
                                <td><span class="badge ${ap.security === 'Open' ? 'badge-danger' : 'badge-success'}">${ap.security}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <p style="margin-top: 1rem;">
                    <strong>Total APs:</strong> ${results.count}
                    ${results.recommended_channel ? `<br><strong>Recommended Channel:</strong> ${results.recommended_channel}` : ''}
                </p>
            `;
            document.getElementById('survey-results').innerHTML = apsHtml;

            // Channel utilization
            const channels = await api('/api/wifi/survey/channels');
            if (channels.channels && channels.channels.length > 0) {
                const chartHtml = channels.channels
                    .sort((a, b) => a.channel - b.channel)
                    .map(ch => `
                        <div class="channel-bar">
                            <span class="channel-label">Ch ${ch.channel} (${ch.band})</span>
                            <div class="bar">
                                <div class="bar-fill" style="width: ${Math.min(100, ch.ap_count * 10)}%">
                                    ${ch.ap_count} AP${ch.ap_count !== 1 ? 's' : ''}
                                </div>
                            </div>
                        </div>
                    `).join('');
                document.getElementById('channel-chart').innerHTML = chartHtml;
            }
        } catch (error) {
            document.getElementById('survey-results').innerHTML = '<div class="status-error">Error loading results</div>';
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // WIRELESS IDS TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderWirelessIDS(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">Wireless IDS Alerts</div>
                <button class="btn btn-primary" onclick="WiFi.loadIDSAlerts()">
                    <i class="icon">🔄</i> Refresh
                </button>
                <div id="ids-alerts" style="margin-top: 1rem;">Loading...</div>
            </div>

            <div class="card">
                <div class="card-header">Rogue Access Points</div>
                <button class="btn btn-warning" onclick="WiFi.scanRogues()">
                    <i class="icon">🔍</i> Scan for Rogues
                </button>
                <div id="rogue-aps" style="margin-top: 1rem;">Loading...</div>
            </div>
        `;

        loadIDSAlerts();
        loadRogueAPs();
    }

    async function loadIDSAlerts() {
        try {
            const result = await api('/api/wifi/ids/alerts?since_minutes=1440');
            const alertsHtml = result.alerts && result.alerts.length > 0
                ? `<table class="data-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Type</th>
                            <th>Severity</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.alerts.map(a => `
                            <tr>
                                <td>${new Date(a.timestamp).toLocaleString()}</td>
                                <td>${a.type}</td>
                                <td><span class="badge badge-${a.severity}">${a.severity}</span></td>
                                <td>${a.details}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`
                : '<div class="empty-state">No wireless alerts in the last 24 hours</div>';
            document.getElementById('ids-alerts').innerHTML = alertsHtml;
        } catch (error) {
            document.getElementById('ids-alerts').innerHTML = '<div class="status-error">Error loading alerts</div>';
        }
    }

    async function loadRogueAPs() {
        try {
            const result = await api('/api/wifi/ids/rogue-aps');
            const roguesHtml = result.rogue_aps && result.rogue_aps.length > 0
                ? `<table class="data-table">
                    <thead>
                        <tr>
                            <th>BSSID</th>
                            <th>SSID</th>
                            <th>Channel</th>
                            <th>Reason</th>
                            <th>Severity</th>
                            <th>First Seen</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.rogue_aps.map(ap => `
                            <tr>
                                <td><code>${ap.bssid}</code></td>
                                <td>${ap.ssid || '<hidden>'}</td>
                                <td>${ap.channel}</td>
                                <td>${ap.reason.replace(/_/g, ' ')}</td>
                                <td><span class="badge badge-${ap.severity}">${ap.severity}</span></td>
                                <td>${new Date(ap.first_seen).toLocaleString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`
                : '<div class="empty-state">No rogue APs detected</div>';
            document.getElementById('rogue-aps').innerHTML = roguesHtml;
        } catch (error) {
            document.getElementById('rogue-aps').innerHTML = '<div class="status-error">Error loading rogues</div>';
        }
    }

    window.WiFi.loadIDSAlerts = loadIDSAlerts;

    window.WiFi.scanRogues = async function() {
        const roguesEl = document.getElementById('rogue-aps');
        roguesEl.innerHTML = '<div class="loading">Scanning for rogue access points...</div>';
        
        try {
            const result = await api('/api/wifi/ids/scan-rogues', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'warning');
            setTimeout(loadRogueAPs, 1000);
        } catch (error) {
            toast('Scan failed: ' + error.message, 'error');
            roguesEl.innerHTML = `<div class="status-error">Scan failed: ${error.message}</div>`;
        }
    };

    // ═══════════════════════════════════════════════════════════════════════
    // CLIENT TRACKING TAB
    // ═══════════════════════════════════════════════════════════════════════
    async function renderClientTracking(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">Client Statistics</div>
                <div id="client-stats">Loading...</div>
            </div>

            <div class="card">
                <div class="card-header">Tracked Clients</div>
                <button class="btn btn-primary" onclick="WiFi.loadTrackedClients()">
                    <i class="icon">🔄</i> Refresh
                </button>
                <div id="tracked-clients-list" style="margin-top: 1rem;">Loading...</div>
            </div>
        `;

        loadClientStats();
        loadTrackedClients();
    }

    async function loadClientStats() {
        try {
            const stats = await api('/api/wifi/clients/stats');
            const html = `
                <div class="stat-row"><span>Total Clients:</span><span>${stats.total_clients || 0}</span></div>
                <div class="stat-row"><span>Active (last hour):</span><span>${stats.active_clients || 0}</span></div>
                ${stats.top_probe_ssids && stats.top_probe_ssids.length > 0 ? `
                    <div style="margin-top: 1rem;">
                        <strong>Top Probe SSIDs:</strong>
                        <ul>
                            ${stats.top_probe_ssids.map(s => `<li>${s.ssid} (${s.count})</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
            document.getElementById('client-stats').innerHTML = html;
        } catch (error) {
            document.getElementById('client-stats').innerHTML = '<div class="status-error">Error loading stats</div>';
        }
    }

    async function loadTrackedClients() {
        try {
            const result = await api('/api/wifi/clients/list');
            const clientsHtml = result.clients && result.clients.length > 0
                ? `<table class="data-table">
                    <thead>
                        <tr>
                            <th>MAC Address</th>
                            <th>Vendor</th>
                            <th>Probe SSIDs</th>
                            <th>Last Seen</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.clients.map(c => `
                            <tr>
                                <td><code>${c.mac}</code></td>
                                <td>${c.vendor}</td>
                                <td>${c.probe_ssids.slice(0, 3).join(', ')}${c.probe_ssids.length > 3 ? '...' : ''}</td>
                                <td>${new Date(c.last_seen).toLocaleString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`
                : '<div class="empty-state">No clients tracked yet</div>';
            document.getElementById('tracked-clients-list').innerHTML = clientsHtml;
        } catch (error) {
            document.getElementById('tracked-clients-list').innerHTML = '<div class="status-error">Error loading clients</div>';
        }
    }

    window.WiFi.loadTrackedClients = loadTrackedClients;

    function cleanup() {
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
    }

    return { render, cleanup };
})();
