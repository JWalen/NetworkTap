/* NetworkTap - Terminal & Log Viewer */

const Terminal = (() => {
    let ws = null;
    let cmdHistory = [];
    let historyIdx = -1;
    let lineCount = 0;
    const MAX_LINES = 1000;

    // Log viewer state
    let logSource = 'syslog';
    let logLines = 100;
    let logFilter = '';
    let logAutoRefresh = false;
    let logRefreshTimer = null;

    async function render(container) {
        container.innerHTML = `
            <div class="terminal-tabs">
                <button class="terminal-tab active" data-tab="terminal">Terminal</button>
                <button class="terminal-tab" data-tab="logs">Logs</button>
            </div>
            <div id="tab-terminal">
                <div class="quick-commands" id="quick-commands">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
                <div class="terminal-output" id="terminal-output"><span class="system-msg">Connecting...</span>\n</div>
                <div class="terminal-input-row">
                    <span class="terminal-prompt">$</span>
                    <input type="text" class="terminal-input" id="terminal-input" placeholder="Type a command..." autocomplete="off" disabled>
                    <button class="btn btn-primary btn-sm" id="terminal-send" disabled>Run</button>
                </div>
            </div>
            <div id="tab-logs" style="display:none">
                <div class="log-controls">
                    <div class="log-sources" id="log-sources"></div>
                    <select id="log-line-count" style="width:auto">
                        <option value="50">50 lines</option>
                        <option value="100" selected>100 lines</option>
                        <option value="200">200 lines</option>
                        <option value="500">500 lines</option>
                    </select>
                    <input type="text" id="log-filter" placeholder="Filter..." style="max-width:200px">
                    <label class="log-auto-refresh">
                        <input type="checkbox" id="log-auto-refresh-chk"> Auto-refresh
                    </label>
                </div>
                <div class="log-output" id="log-output"><span class="system-msg">Select a log source above</span></div>
            </div>
        `;

        setupTabs();
        setupTerminal();
        setupLogViewer();
        loadQuickCommands();
        connectTerminalWs();
    }

    /* ── Tab Switching ─────────────────────────────────── */

    function setupTabs() {
        document.querySelectorAll('.terminal-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.terminal-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                const target = tab.dataset.tab;
                document.getElementById('tab-terminal').style.display = target === 'terminal' ? '' : 'none';
                document.getElementById('tab-logs').style.display = target === 'logs' ? '' : 'none';
            });
        });
    }

    /* ── Terminal ──────────────────────────────────────── */

    function setupTerminal() {
        const input = document.getElementById('terminal-input');
        const sendBtn = document.getElementById('terminal-send');

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                sendCommand();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (historyIdx < cmdHistory.length - 1) {
                    historyIdx++;
                    input.value = cmdHistory[cmdHistory.length - 1 - historyIdx];
                }
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (historyIdx > 0) {
                    historyIdx--;
                    input.value = cmdHistory[cmdHistory.length - 1 - historyIdx];
                } else {
                    historyIdx = -1;
                    input.value = '';
                }
            }
        });

        sendBtn.addEventListener('click', sendCommand);
    }

    function sendCommand(cmdOverride) {
        const input = document.getElementById('terminal-input');
        const cmd = typeof cmdOverride === 'string' ? cmdOverride : input.value.trim();
        if (!cmd || !ws || ws.readyState !== WebSocket.OPEN) return;

        // Add to history
        if (!cmdOverride) {
            cmdHistory.push(cmd);
            if (cmdHistory.length > 100) cmdHistory.shift();
            historyIdx = -1;
            input.value = '';
        }

        appendOutput(`$ ${cmd}\n`, 'cmd-line');
        ws.send(JSON.stringify({ cmd }));
    }

    function appendOutput(text, className) {
        const output = document.getElementById('terminal-output');
        if (!output) return;

        const span = document.createElement('span');
        span.className = className || '';
        span.textContent = text;
        output.appendChild(span);

        lineCount++;
        // Trim scrollback
        while (lineCount > MAX_LINES && output.firstChild) {
            output.removeChild(output.firstChild);
            lineCount--;
        }

        output.scrollTop = output.scrollHeight;
    }

    async function loadQuickCommands() {
        try {
            const data = await api('/api/terminal/quick-commands');
            const el = document.getElementById('quick-commands');
            if (!el) return;
            el.innerHTML = data.commands.map(c =>
                `<button class="quick-cmd-btn" data-cmd="${escapeHtml(c.cmd)}">${escapeHtml(c.label)}</button>`
            ).join('');

            el.querySelectorAll('.quick-cmd-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    sendCommand(btn.dataset.cmd);
                });
            });
        } catch (e) {
            const el = document.getElementById('quick-commands');
            if (el) el.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem">Failed to load quick commands</span>';
        }
    }

    /* ── Terminal WebSocket ────────────────────────────── */

    function connectTerminalWs() {
        const creds = Settings.getCredentials();
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws/terminal`);

        ws.onopen = () => {
            ws.send(JSON.stringify({ user: creds.user, pass: creds.pass }));
        };

        ws.onmessage = (e) => {
            let msg;
            try { msg = JSON.parse(e.data); } catch { return; }

            if (msg.type === 'auth') {
                if (msg.data === 'ok') {
                    appendOutput('Connected. Type a command or use quick commands above.\n', 'system-msg');
                    document.getElementById('terminal-input').disabled = false;
                    document.getElementById('terminal-send').disabled = false;
                    document.getElementById('terminal-input').focus();
                } else {
                    appendOutput('Authentication failed. Check credentials in Settings.\n', 'stderr-line');
                }
            } else if (msg.type === 'stdout') {
                appendOutput(msg.data, 'stdout-line');
            } else if (msg.type === 'stderr') {
                appendOutput(msg.data, 'stderr-line');
            } else if (msg.type === 'exit') {
                const cls = msg.code === 0 ? 'exit-ok' : 'exit-err';
                appendOutput(`[exit ${msg.code}]\n`, cls);
            }
        };

        ws.onclose = () => {
            appendOutput('Disconnected.\n', 'system-msg');
            document.getElementById('terminal-input').disabled = true;
            document.getElementById('terminal-send').disabled = true;
            // Reconnect after 3s
            setTimeout(() => {
                if (document.getElementById('terminal-output')) {
                    connectTerminalWs();
                }
            }, 3000);
        };

        ws.onerror = () => {
            // onclose will fire after onerror
        };
    }

    /* ── Log Viewer ────────────────────────────────────── */

    function setupLogViewer() {
        // Load sources
        loadLogSources();

        document.getElementById('log-line-count').addEventListener('change', (e) => {
            logLines = parseInt(e.target.value, 10);
            fetchLogs();
        });

        document.getElementById('log-filter').addEventListener('input', (e) => {
            logFilter = e.target.value.toLowerCase();
            applyLogFilter();
        });

        document.getElementById('log-auto-refresh-chk').addEventListener('change', (e) => {
            logAutoRefresh = e.target.checked;
            if (logAutoRefresh) {
                logRefreshTimer = setInterval(fetchLogs, 5000);
            } else if (logRefreshTimer) {
                clearInterval(logRefreshTimer);
                logRefreshTimer = null;
            }
        });
    }

    async function loadLogSources() {
        try {
            const data = await api('/api/system/logs/sources');
            const el = document.getElementById('log-sources');
            if (!el) return;
            el.innerHTML = data.sources.map(s => {
                const cls = s.name === logSource ? 'log-source-btn active' : 'log-source-btn';
                const disabled = !s.available ? ' style="opacity:0.4"' : '';
                return `<button class="${cls}" data-source="${s.name}"${disabled}>${s.name.charAt(0).toUpperCase() + s.name.slice(1)}</button>`;
            }).join('');

            el.querySelectorAll('.log-source-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    el.querySelectorAll('.log-source-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    logSource = btn.dataset.source;
                    fetchLogs();
                });
            });

            fetchLogs();
        } catch (e) {
            const el = document.getElementById('log-sources');
            if (el) el.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem">Failed to load log sources</span>';
        }
    }

    async function fetchLogs() {
        const output = document.getElementById('log-output');
        if (!output) return;
        output.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const data = await api(`/api/system/logs?source=${encodeURIComponent(logSource)}&lines=${logLines}`);
            if (!data.available) {
                output.innerHTML = `<span class="system-msg">Log file not found: ${escapeHtml(data.path || 'unknown')}</span>`;
                return;
            }

            const lines = data.lines || [];
            output.innerHTML = lines.map(l =>
                `<div class="log-line">${escapeHtml(l)}</div>`
            ).join('');

            if (lines.length === 0) {
                output.innerHTML = '<span class="system-msg">No log entries</span>';
            }

            applyLogFilter();
            output.scrollTop = output.scrollHeight;
        } catch (e) {
            output.innerHTML = `<span class="stderr-line">Error: ${escapeHtml(e.message)}</span>`;
        }
    }

    function applyLogFilter() {
        const output = document.getElementById('log-output');
        if (!output) return;
        const lines = output.querySelectorAll('.log-line');
        lines.forEach(line => {
            if (!logFilter || line.textContent.toLowerCase().includes(logFilter)) {
                line.style.display = '';
            } else {
                line.style.display = 'none';
            }
        });
    }

    return { render };
})();
