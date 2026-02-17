/* NetworkTap - Network Interface View */

const Network = (() => {
    let isEditingNetwork = false;  // Track if user is editing the form

    async function render(container) {
        isEditingNetwork = false;  // Reset on page load
        
        container.innerHTML = `
            <div class="card" style="margin-bottom:24px">
                <div class="card-header">
                    <span class="card-title">Operating Mode</span>
                </div>
                <div style="margin-bottom:16px">
                    <div class="mode-switch" id="mode-switch">
                        <button class="mode-switch-btn" data-mode="span">SPAN / Mirror</button>
                        <button class="mode-switch-btn" data-mode="bridge">Inline Bridge</button>
                    </div>
                </div>
                <p id="mode-desc" style="color:var(--text-muted);font-size:0.85rem;"></p>
            </div>

            <div class="card" style="margin-bottom:24px">
                <div class="card-header">
                    <span class="card-title">Management Network</span>
                </div>
                <div id="mgmt-network-status" style="margin-bottom:16px;">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
                <div id="mgmt-network-form">
                    <div class="form-row" style="margin-bottom:12px;display:flex;gap:12px;flex-wrap:wrap;align-items:end;">
                        <div style="min-width:120px;">
                            <label class="form-label">Mode</label>
                            <select id="net-mode" style="width:100%">
                                <option value="dhcp">DHCP</option>
                                <option value="static">Static IP</option>
                            </select>
                        </div>
                        <div id="static-ip-fields" class="static-ip-fields hidden">
                            <div style="min-width:160px;flex:1;">
                                <label class="form-label">IP Address (CIDR)</label>
                                <input type="text" id="net-ip" placeholder="192.168.1.100/24" style="width:100%">
                            </div>
                            <div style="min-width:140px;">
                                <label class="form-label">Gateway</label>
                                <input type="text" id="net-gateway" placeholder="192.168.1.1" style="width:100%">
                            </div>
                            <div style="min-width:140px;">
                                <label class="form-label">DNS</label>
                                <input type="text" id="net-dns" placeholder="8.8.8.8" style="width:100%">
                            </div>
                        </div>
                        <div>
                            <button class="btn btn-primary" id="btn-save-network">Save</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card" style="margin-bottom:24px" id="wifi-card" hidden>
                <div class="card-header">
                    <span class="card-title">WiFi</span>
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-sm btn-secondary" id="btn-wifi-scan">Scan</button>
                        <button class="btn btn-sm btn-danger" id="btn-wifi-disconnect" hidden>Disconnect</button>
                    </div>
                </div>
                <div id="wifi-status" style="margin-bottom:16px;">
                    <span style="color:var(--text-muted)">Checking WiFi...</span>
                </div>
                <div id="wifi-connect-form" hidden>
                    <div class="form-row" style="margin-bottom:12px;">
                        <div>
                            <label class="form-label">SSID</label>
                            <input type="text" id="wifi-ssid" placeholder="Network name" style="width:100%">
                        </div>
                        <div>
                            <label class="form-label">Password</label>
                            <input type="password" id="wifi-psk" placeholder="Password" style="width:100%">
                        </div>
                        <div style="flex:0;">
                            <label class="form-label">&nbsp;</label>
                            <button class="btn btn-primary" id="btn-wifi-connect">Connect</button>
                        </div>
                    </div>
                </div>
                <div id="wifi-scan-results" hidden>
                    <div class="card-title" style="margin-bottom:8px;font-size:0.8rem;">Available Networks</div>
                    <div id="wifi-networks"></div>
                </div>
            </div>

            <div id="iface-cards" class="grid-2" style="margin-bottom:24px">
                <div class="loading"><div class="spinner"></div></div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Interface Details</span>
                    <button class="btn btn-sm btn-secondary" id="btn-refresh-net">Refresh</button>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Interface</th>
                                <th>State</th>
                                <th>MAC</th>
                                <th>Speed</th>
                                <th>RX Bytes</th>
                                <th>TX Bytes</th>
                                <th>RX Pkts</th>
                                <th>TX Pkts</th>
                                <th>Errors</th>
                                <th>Drops</th>
                            </tr>
                        </thead>
                        <tbody id="iface-table-body">
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        // Mode switch buttons
        document.querySelectorAll('.mode-switch-btn').forEach(btn => {
            btn.addEventListener('click', () => switchMode(btn.dataset.mode));
        });

        // Network mode toggle - mark as editing when user changes it
        document.getElementById('net-mode').addEventListener('change', (e) => {
            isEditingNetwork = true;
            const staticFields = document.getElementById('static-ip-fields');
            if (e.target.value === 'static') {
                staticFields.classList.remove('hidden');
            } else {
                staticFields.classList.add('hidden');
            }
        });

        // Mark as editing when user types in any network field
        ['net-ip', 'net-gateway', 'net-dns'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('focus', () => { isEditingNetwork = true; });
                el.addEventListener('input', () => { isEditingNetwork = true; });
            }
        });

        document.getElementById('btn-save-network').addEventListener('click', saveNetworkConfig);
        document.getElementById('btn-refresh-net').addEventListener('click', () => {
            isEditingNetwork = false;  // Force refresh when user clicks refresh
            refresh();
        });
        document.getElementById('btn-wifi-scan').addEventListener('click', wifiScan);
        document.getElementById('btn-wifi-connect').addEventListener('click', wifiConnect);
        document.getElementById('btn-wifi-disconnect').addEventListener('click', wifiDisconnect);

        await refresh();
        App.setRefresh(refresh, 5000);
    }

    async function refresh() {
        try {
            const [ifaces, config, wifi, netConfig] = await Promise.all([
                api('/api/system/interfaces'),
                api('/api/config/mode'),
                api('/api/wifi/status').catch(() => null),
                api('/api/system/network').catch(() => null),
            ]);

            updateMode(config);
            updateInterfaces(ifaces);
            updateWifiStatus(wifi);
            updateNetworkConfig(netConfig);
        } catch (e) {
            // retry
        }
    }

    function updateNetworkConfig(netConfig) {
        const statusEl = document.getElementById('mgmt-network-status');
        if (!statusEl) return;  // Page navigated away
        const modeSelect = document.getElementById('net-mode');
        const staticFields = document.getElementById('static-ip-fields');

        if (!netConfig) {
            statusEl.innerHTML = '<span style="color:var(--text-muted)">Unable to load network config</span>';
            return;
        }

        // Show current status (always update the status display)
        const currentIp = netConfig.current_ip || 'Unknown';
        const currentGw = netConfig.current_gateway || 'None';
        const currentDns = netConfig.current_dns || 'None';
        const modeLabel = netConfig.mode === 'dhcp' ? 'DHCP' : 'Static';
        
        statusEl.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:12px;">
                <div>
                    <span style="color:var(--text-muted);font-size:0.75rem;">Current IP</span>
                    <div style="font-family:monospace;">${escapeHtml(currentIp)}</div>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:0.75rem;">Gateway</span>
                    <div style="font-family:monospace;">${escapeHtml(currentGw)}</div>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:0.75rem;">DNS</span>
                    <div style="font-family:monospace;">${escapeHtml(currentDns)}</div>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:0.75rem;">Mode</span>
                    <div><span class="severity ${netConfig.mode === 'dhcp' ? 'severity-4' : 'severity-3'}">${modeLabel}</span></div>
                </div>
            </div>
        `;

        // Only update form values if user is NOT currently editing
        if (!isEditingNetwork) {
            modeSelect.value = netConfig.mode;
            if (netConfig.mode === 'static') {
                staticFields.classList.remove('hidden');
                document.getElementById('net-ip').value = netConfig.configured_ip || '';
                document.getElementById('net-gateway').value = netConfig.configured_gateway || '';
                document.getElementById('net-dns').value = netConfig.configured_dns || '';
            } else {
                staticFields.classList.add('hidden');
                // Clear static fields when in DHCP mode
                document.getElementById('net-ip').value = '';
                document.getElementById('net-gateway').value = '';
                document.getElementById('net-dns').value = '';
            }
        }
    }

    async function saveNetworkConfig() {
        const mode = document.getElementById('net-mode').value;
        const btn = document.getElementById('btn-save-network');
        
        const body = { mode };
        
        if (mode === 'static') {
            const ip = document.getElementById('net-ip').value.trim();
            const gateway = document.getElementById('net-gateway').value.trim();
            const dns = document.getElementById('net-dns').value.trim();
            
            if (!ip) {
                toast('IP address is required for static mode', 'error');
                return;
            }
            
            if (!ip.includes('/')) {
                toast('IP address must include prefix (e.g., 192.168.1.100/24)', 'error');
                return;
            }
            
            body.ip_address = ip;
            if (gateway) body.gateway = gateway;
            if (dns) body.dns = dns;
        }

        // Warn user about potential disconnection
        if (mode === 'static') {
            if (!confirm('Changing network settings may disconnect you. Make sure the new IP is correct. Continue?')) {
                return;
            }
        }

        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            const result = await api('/api/system/network', {
                method: 'POST',
                body: body,
            });
            
            if (result.warning) {
                toast(result.warning, 'warning');
            }
            toast(result.message, result.success ? 'success' : 'error');
            
            if (result.success) {
                isEditingNetwork = false;  // Reset editing flag after successful save
                await refresh();
            }
        } catch (e) {
            toast('Failed to save network config: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save';
        }
    }

    function updateWifiStatus(wifi) {
        const wifiCard = document.getElementById('wifi-card');
        const el = document.getElementById('wifi-status');
        const disconnectBtn = document.getElementById('btn-wifi-disconnect');
        const connectForm = document.getElementById('wifi-connect-form');

        if (!wifi || wifi.available === false) {
            wifiCard.hidden = true;
            return;
        }
        wifiCard.hidden = false;

        if (wifi.connected) {
            el.innerHTML = `
                <div style="display:flex;align-items:center;gap:12px;">
                    <span class="status-dot online"></span>
                    <div>
                        <div style="font-weight:600;">${escapeHtml(wifi.ssid || 'Connected')}</div>
                        <div style="color:var(--text-muted);font-size:0.8rem;">
                            IP: ${escapeHtml(wifi.ip || 'N/A')}
                            ${wifi.signal ? ' &middot; Signal: ' + escapeHtml(wifi.signal) : ''}
                        </div>
                    </div>
                </div>
            `;
            disconnectBtn.hidden = false;
            connectForm.hidden = true;
        } else {
            el.innerHTML = `
                <div style="display:flex;align-items:center;gap:12px;">
                    <span class="status-dot offline"></span>
                    <span style="color:var(--text-muted);">Not connected</span>
                </div>
            `;
            disconnectBtn.hidden = true;
            connectForm.hidden = false;
        }
    }

    async function wifiScan() {
        const btn = document.getElementById('btn-wifi-scan');
        const resultsDiv = document.getElementById('wifi-scan-results');
        const networksDiv = document.getElementById('wifi-networks');

        btn.disabled = true;
        btn.textContent = 'Scanning...';

        try {
            const data = await api('/api/wifi/scan');
            resultsDiv.hidden = false;

            if (!data.networks || data.networks.length === 0) {
                networksDiv.innerHTML = '<div style="color:var(--text-muted);padding:8px;">No networks found</div>';
                return;
            }

            networksDiv.innerHTML = data.networks.map(n => `
                <div class="file-item" style="cursor:pointer" onclick="Network.selectSSID('${escapeHtml(n.ssid)}')">
                    <svg class="nav-icon" style="width:16px;height:16px;color:var(--accent);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M5 12.55a11 11 0 0114.08 0"/>
                        <path d="M1.42 9a16 16 0 0121.16 0"/>
                        <path d="M8.53 16.11a6 6 0 016.95 0"/>
                        <circle cx="12" cy="20" r="1"/>
                    </svg>
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(n.ssid)}</div>
                        <div class="file-meta">${escapeHtml(n.raw || '')}</div>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            toast('WiFi scan failed: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Scan';
        }
    }

    function selectSSID(ssid) {
        document.getElementById('wifi-ssid').value = ssid;
        document.getElementById('wifi-psk').focus();
        document.getElementById('wifi-connect-form').hidden = false;
    }

    async function wifiConnect() {
        const ssid = document.getElementById('wifi-ssid').value.trim();
        const psk = document.getElementById('wifi-psk').value;

        if (!ssid || !psk) {
            toast('SSID and password required', 'error');
            return;
        }

        const btn = document.getElementById('btn-wifi-connect');
        btn.disabled = true;
        btn.textContent = 'Connecting...';

        try {
            const result = await api('/api/wifi/connect', {
                method: 'POST',
                body: { ssid, psk },
            });
            toast(result.message, result.success ? 'success' : 'error');
            document.getElementById('wifi-psk').value = '';
            document.getElementById('wifi-scan-results').hidden = true;
            await refresh();
        } catch (e) {
            toast('WiFi connect failed: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Connect';
        }
    }

    async function wifiDisconnect() {
        try {
            const result = await api('/api/wifi/disconnect', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            await refresh();
        } catch (e) {
            toast('WiFi disconnect failed: ' + e.message, 'error');
        }
    }

    function updateMode(config) {
        document.querySelectorAll('.mode-switch-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === config.mode);
        });

        const desc = document.getElementById('mode-desc');
        if (!desc) return;
        if (config.mode === 'span') {
            desc.textContent = `SPAN Mode: ${config.nic1} monitors traffic, ${config.nic2} is management interface`;
        } else {
            desc.textContent = `Bridge Mode: ${config.nic1} + ${config.nic2} bridged as ${config.bridge_name}, management via bridge IP`;
        }
    }

    function updateInterfaces(data) {
        const container = document.getElementById('iface-cards');
        if (!container) return;
        const ifaces = data.interfaces || [];

        if (ifaces.length === 0) {
            container.innerHTML = '<div class="empty-state full-width"><h3>No interfaces found</h3></div>';
            return;
        }

        container.innerHTML = ifaces.map(iface => `
            <div class="iface-card">
                <div class="iface-header">
                    <span class="iface-name">${escapeHtml(iface.name)}</span>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <button class="btn btn-sm btn-secondary identify-port-btn" data-iface="${escapeHtml(iface.name)}" title="Blink port LED to identify physical port">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle">
                                <circle cx="12" cy="12" r="5"/>
                                <line x1="12" y1="1" x2="12" y2="3"/>
                                <line x1="12" y1="21" x2="12" y2="23"/>
                                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                                <line x1="1" y1="12" x2="3" y2="12"/>
                                <line x1="21" y1="12" x2="23" y2="12"/>
                                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                            </svg>
                            Identify
                        </button>
                        <span class="iface-status ${iface.state}">
                            <span class="status-dot ${iface.state === 'up' ? 'online' : 'offline'}"></span>
                            ${iface.state}
                        </span>
                    </div>
                </div>
                <div class="iface-stats">
                    <div class="iface-stat">
                        <span class="iface-stat-label">IP Address</span>
                        <span class="iface-stat-value">${iface.addresses.length ? iface.addresses[0] : 'None'}</span>
                    </div>
                    <div class="iface-stat">
                        <span class="iface-stat-label">MAC</span>
                        <span class="iface-stat-value">${iface.mac || 'N/A'}</span>
                    </div>
                    <div class="iface-stat">
                        <span class="iface-stat-label">RX Traffic</span>
                        <span class="iface-stat-value">${formatBytes(iface.bytes_recv)}</span>
                    </div>
                    <div class="iface-stat">
                        <span class="iface-stat-label">TX Traffic</span>
                        <span class="iface-stat-value">${formatBytes(iface.bytes_sent)}</span>
                    </div>
                    <div class="iface-stat">
                        <span class="iface-stat-label">RX Packets</span>
                        <span class="iface-stat-value">${iface.packets_recv.toLocaleString()}</span>
                    </div>
                    <div class="iface-stat">
                        <span class="iface-stat-label">TX Packets</span>
                        <span class="iface-stat-value">${iface.packets_sent.toLocaleString()}</span>
                    </div>
                </div>
                ${iface.name === data.capture_interface ? '<div style="margin-top:12px;"><span class="severity severity-4">CAPTURE</span></div>' : ''}
                ${iface.name === data.management_interface ? '<div style="margin-top:12px;"><span class="severity severity-3">MANAGEMENT</span></div>' : ''}
            </div>
        `).join('');

        // Bind identify buttons
        container.querySelectorAll('.identify-port-btn').forEach(btn => {
            btn.addEventListener('click', () => identifyPort(btn));
        });

        // Table
        const tbody = document.getElementById('iface-table-body');
        if (!tbody) return;
        tbody.innerHTML = ifaces.map(i => `
            <tr>
                <td><strong>${escapeHtml(i.name)}</strong></td>
                <td><span class="status-dot ${i.state === 'up' ? 'online' : 'offline'}" style="display:inline-block"></span> ${i.state}</td>
                <td style="font-family:monospace;font-size:0.8rem">${i.mac || 'N/A'}</td>
                <td>${i.speed ? i.speed + ' Mbps' : 'N/A'}</td>
                <td>${formatBytes(i.bytes_recv)}</td>
                <td>${formatBytes(i.bytes_sent)}</td>
                <td>${i.packets_recv.toLocaleString()}</td>
                <td>${i.packets_sent.toLocaleString()}</td>
                <td>${i.errors_in + i.errors_out}</td>
                <td>${i.drops_in + i.drops_out}</td>
            </tr>
        `).join('');
    }

    async function switchMode(newMode) {
        if (!confirm(`Switch to ${newMode.toUpperCase()} mode? This will restart capture services.`)) {
            return;
        }

        try {
            const result = await api('/api/config/mode', {
                method: 'PUT',
                body: { mode: newMode },
            });
            toast(result.message, result.success ? 'success' : 'error');
            if (result.success) {
                await refresh();
            }
        } catch (e) {
            toast('Mode switch failed: ' + e.message, 'error');
        }
    }

    async function identifyPort(btn) {
        const iface = btn.dataset.iface;
        const origText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="pulse" style="display:inline-block">Blinking...</span>';

        try {
            const result = await api('/api/system/identify-port', {
                method: 'POST',
                body: { interface: iface, duration: 5 },
            });
            toast(result.message, result.success ? 'success' : 'warning');
        } catch (e) {
            toast('Identify failed: ' + e.message, 'error');
        } finally {
            // Re-enable after the blink duration
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = origText;
            }, 5000);
        }
    }

    return { render, selectSSID };
})();
