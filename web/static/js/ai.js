/* NetworkTap - AI Features Page */

const AI = (() => {
    let chatHistory = [];
    let isStreaming = false;

    async function render(container) {
        container.innerHTML = `
            <div class="grid-2" style="margin-bottom:24px">
                <!-- Anomaly Detection Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">🔍 Anomaly Detection</span>
                        <label class="toggle">
                            <input type="checkbox" id="anomaly-toggle">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div id="anomaly-status" style="margin-bottom:16px">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                    <div id="anomaly-stats" style="font-size:0.85rem;color:var(--text-muted)"></div>
                </div>

                <!-- AI Assistant Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">🤖 AI Assistant</span>
                        <span id="ai-status-badge" class="severity severity-4">Checking...</span>
                    </div>
                    <div id="ai-status" style="margin-bottom:16px">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                    <div id="ai-model-info" style="font-size:0.85rem;color:var(--text-muted)"></div>
                </div>
            </div>

            <!-- Recent Anomalies -->
            <div class="card" style="margin-bottom:24px">
                <div class="card-header">
                    <span class="card-title">Recent Anomalies</span>
                    <button class="btn btn-sm btn-secondary" id="btn-refresh-anomalies">Refresh</button>
                </div>
                <div id="anomalies-list" style="max-height:300px;overflow-y:auto">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <!-- AI Chat Interface -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">AI Analysis Chat</span>
                    <div style="display:flex;gap:8px">
                        <button class="btn btn-sm btn-secondary" id="btn-summarize">Summarize Alerts</button>
                        <button class="btn btn-sm btn-secondary" id="btn-clear-chat">Clear</button>
                    </div>
                </div>
                <div id="chat-container" style="height:400px;display:flex;flex-direction:column">
                    <div id="chat-messages" style="flex:1;overflow-y:auto;padding:16px;background:var(--bg-secondary);border-radius:8px;margin-bottom:12px">
                        <div class="chat-welcome" style="text-align:center;color:var(--text-muted);padding:40px">
                            <div style="font-size:2rem;margin-bottom:12px">🤖</div>
                            <h3 style="margin-bottom:8px">AI Network Analyst</h3>
                            <p style="font-size:0.9rem">Ask questions about your network traffic, alerts, or security events.</p>
                            <div style="margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center">
                                <button class="btn btn-sm btn-secondary quick-prompt" data-prompt="What are the main security concerns right now?">Security overview</button>
                                <button class="btn btn-sm btn-secondary quick-prompt" data-prompt="Which IPs are generating the most traffic?">Top talkers</button>
                                <button class="btn btn-sm btn-secondary quick-prompt" data-prompt="Are there any suspicious connection patterns?">Suspicious patterns</button>
                            </div>
                        </div>
                    </div>
                    <div style="display:flex;gap:8px">
                        <input type="text" id="chat-input" placeholder="Ask about your network..." style="flex:1" disabled>
                        <button class="btn btn-primary" id="btn-send" disabled>Send</button>
                    </div>
                </div>
            </div>
        `;

        // Event handlers
        document.getElementById('anomaly-toggle').addEventListener('change', toggleAnomalyDetection);
        document.getElementById('btn-refresh-anomalies').addEventListener('click', loadAnomalies);
        document.getElementById('btn-summarize').addEventListener('click', summarizeAlerts);
        document.getElementById('btn-clear-chat').addEventListener('click', clearChat);
        document.getElementById('btn-send').addEventListener('click', sendMessage);
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Quick prompts
        document.querySelectorAll('.quick-prompt').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('chat-input').value = btn.dataset.prompt;
                sendMessage();
            });
        });

        // Load initial data
        await Promise.all([
            loadAISettings(),
            loadAnomalies(),
        ]);

        App.setRefresh(() => {
            loadAnomalies();
        }, 30000);
    }

    async function loadAISettings() {
        try {
            const data = await api('/api/ai/settings');

            // Anomaly detection status
            const anomalyToggle = document.getElementById('anomaly-toggle');
            const anomalyStatus = document.getElementById('anomaly-status');
            const anomalyStats = document.getElementById('anomaly-stats');

            anomalyToggle.checked = data.anomaly_detection.running;
            
            if (data.anomaly_detection.running) {
                anomalyStatus.innerHTML = `
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="status-dot online"></span>
                        <span style="color:var(--text)">Running</span>
                    </div>
                `;
            } else {
                anomalyStatus.innerHTML = `
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="status-dot offline"></span>
                        <span style="color:var(--text-muted)">Stopped</span>
                    </div>
                `;
            }

            anomalyStats.innerHTML = `
                Sensitivity: ${data.anomaly_detection.sensitivity} · 
                Interval: ${data.anomaly_detection.interval_seconds}s
            `;

            // AI Assistant status
            const aiStatus = document.getElementById('ai-status');
            const aiBadge = document.getElementById('ai-status-badge');
            const aiModelInfo = document.getElementById('ai-model-info');
            const chatInput = document.getElementById('chat-input');
            const sendBtn = document.getElementById('btn-send');

            if (data.ai_assistant.available) {
                aiBadge.textContent = 'Available';
                aiBadge.className = 'severity severity-4';
                aiStatus.innerHTML = `
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="status-dot online"></span>
                        <span style="color:var(--text)">Ready</span>
                    </div>
                `;
                aiModelInfo.textContent = `Model: ${data.ai_assistant.model}`;
                chatInput.disabled = false;
                sendBtn.disabled = false;
            } else {
                aiBadge.textContent = 'Unavailable';
                aiBadge.className = 'severity severity-2';
                aiStatus.innerHTML = `
                    <div style="color:var(--text-muted)">
                        ${escapeHtml(data.ai_assistant.status_detail || 'Ollama not running')}
                    </div>
                    <button class="btn btn-sm btn-primary" id="btn-setup-ollama" style="margin-top:12px">
                        Setup Ollama
                    </button>
                `;
                aiModelInfo.textContent = '';
                chatInput.disabled = true;
                chatInput.placeholder = 'AI Assistant unavailable - run setup first';
                sendBtn.disabled = true;

                document.getElementById('btn-setup-ollama')?.addEventListener('click', showOllamaSetup);
            }

        } catch (e) {
            console.error('Failed to load AI settings:', e);
        }
    }

    async function loadAnomalies() {
        const container = document.getElementById('anomalies-list');
        try {
            const data = await api('/api/ai/anomalies?limit=20');
            
            if (!data.anomalies || data.anomalies.length === 0) {
                container.innerHTML = `
                    <div class="empty-state" style="padding:40px">
                        <h3>No anomalies detected</h3>
                        <p>The system is monitoring for unusual patterns</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = data.anomalies.reverse().map(a => `
                <div class="alert-item" style="padding:12px;border-bottom:1px solid var(--border)">
                    <div style="display:flex;justify-content:space-between;align-items:start">
                        <div>
                            <span class="severity severity-${a.severity}">${getAnomalyTypeLabel(a.anomaly_type)}</span>
                            <strong style="margin-left:8px">${escapeHtml(a.title)}</strong>
                        </div>
                        <span style="font-size:0.75rem;color:var(--text-muted)">${formatTime(a.timestamp)}</span>
                    </div>
                    <p style="margin:8px 0 0;font-size:0.85rem;color:var(--text-muted)">${escapeHtml(a.description)}</p>
                    ${a.source_ip ? `<span style="font-size:0.75rem;font-family:monospace">${escapeHtml(a.source_ip)}${a.dest_ip ? ' → ' + escapeHtml(a.dest_ip) : ''}${a.dest_port ? ':' + a.dest_port : ''}</span>` : ''}
                </div>
            `).join('');

        } catch (e) {
            container.innerHTML = `<div class="empty-state"><p>Failed to load anomalies</p></div>`;
        }
    }

    function getAnomalyTypeLabel(type) {
        const labels = {
            'volume_anomaly': 'Volume',
            'rare_destination': 'New Dest',
            'port_scan': 'Port Scan',
            'host_scan': 'Host Scan',
            'beaconing': 'Beaconing',
            'dns_dga': 'DNS/DGA',
            'dns_tunneling': 'DNS Tunnel',
        };
        return labels[type] || type;
    }

    async function toggleAnomalyDetection() {
        const toggle = document.getElementById('anomaly-toggle');
        const enabled = toggle.checked;

        try {
            const result = await api('/api/ai/anomalies/toggle', {
                method: 'POST',
                body: { enabled },
            });
            toast(result.message, 'success');
        } catch (e) {
            toast('Failed to toggle anomaly detection', 'error');
            toggle.checked = !enabled; // Revert
        }
    }

    async function sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message || isStreaming) return;

        input.value = '';
        addChatMessage('user', message);

        isStreaming = true;
        const responseDiv = addChatMessage('assistant', '');
        responseDiv.innerHTML = '<span class="typing-indicator">Thinking...</span>';

        try {
            const data = await api('/api/ai/assistant/chat', {
                method: 'POST',
                body: { message, include_context: true },
            });

            responseDiv.innerHTML = formatMarkdown(data.response);
        } catch (e) {
            responseDiv.innerHTML = `<span style="color:var(--red)">Error: ${escapeHtml(e.message)}</span>`;
        } finally {
            isStreaming = false;
        }

        // Scroll to bottom
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addChatMessage(role, content) {
        const chatMessages = document.getElementById('chat-messages');
        
        // Remove welcome message if present
        const welcome = chatMessages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        const div = document.createElement('div');
        div.className = `chat-message chat-${role}`;
        div.style.cssText = `
            margin-bottom: 16px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            ${role === 'user' 
                ? 'background: var(--accent); color: var(--bg); margin-left: auto;' 
                : 'background: var(--bg); border: 1px solid var(--border);'}
        `;
        div.innerHTML = content ? formatMarkdown(content) : '';
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    }

    function formatMarkdown(text) {
        // Simple markdown formatting
        return escapeHtml(text)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code style="background:var(--bg-secondary);padding:2px 6px;border-radius:4px">$1</code>')
            .replace(/\n/g, '<br>');
    }

    async function summarizeAlerts() {
        const input = document.getElementById('chat-input');
        input.value = 'Summarize the recent security alerts and anomalies. What should I be concerned about?';
        sendMessage();
    }

    function clearChat() {
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = `
            <div class="chat-welcome" style="text-align:center;color:var(--text-muted);padding:40px">
                <div style="font-size:2rem;margin-bottom:12px">🤖</div>
                <h3 style="margin-bottom:8px">AI Network Analyst</h3>
                <p style="font-size:0.9rem">Ask questions about your network traffic, alerts, or security events.</p>
            </div>
        `;
        chatHistory = [];
    }

    function showOllamaSetup() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal" style="max-width:500px">
                <div class="modal-header">
                    <h3>Setup AI Assistant</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                </div>
                <div class="modal-body">
                    <p>To use the AI Assistant, Ollama needs to be installed and running.</p>
                    <h4 style="margin-top:16px">Option 1: Run setup script</h4>
                    <p style="font-size:0.9rem;color:var(--text-muted)">SSH into your device and run:</p>
                    <pre style="background:var(--bg-secondary);padding:12px;border-radius:8px;overflow-x:auto">sudo bash /opt/networktap/setup/configure_ai.sh</pre>
                    
                    <h4 style="margin-top:16px">Option 2: Manual install</h4>
                    <pre style="background:var(--bg-secondary);padding:12px;border-radius:8px;overflow-x:auto">curl -fsSL https://ollama.com/install.sh | sh
ollama pull tinyllama</pre>
                    
                    <p style="margin-top:16px;font-size:0.85rem;color:var(--text-muted)">
                        After installation, restart the web service or reload this page.
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
                    <button class="btn btn-primary" onclick="location.reload()">Refresh Page</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    function formatTime(isoTime) {
        try {
            const d = new Date(isoTime);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return isoTime;
        }
    }

    return { render };
})();
