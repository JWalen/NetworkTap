/* NetworkTap - WebSocket Connection Manager */

const WS = (() => {
    let ws = null;
    let reconnectTimer = null;
    let reconnectDelay = 1000;
    const MAX_RECONNECT_DELAY = 30000;
    let pingTimer = null;

    // Callback for alert pages
    let onAlert = null;

    function connect() {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/ws/alerts`;

        try {
            ws = new WebSocket(url);
        } catch (e) {
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            updateStatusDot(true);
            reconnectDelay = 1000;

            // Start ping interval
            if (pingTimer) clearInterval(pingTimer);
            pingTimer = setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                }
            }, 30000);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data && data.source) {
                    // It's an alert
                    if (typeof onAlert === 'function') {
                        onAlert(data);
                    }
                }
            } catch {
                // Ignore non-JSON messages (like "pong")
            }
        };

        ws.onclose = () => {
            updateStatusDot(false);
            cleanup();
            scheduleReconnect();
        };

        ws.onerror = () => {
            updateStatusDot(false);
        };
    }

    function disconnect() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        cleanup();
        if (ws) {
            ws.close();
            ws = null;
        }
        updateStatusDot(false);
    }

    function cleanup() {
        if (pingTimer) {
            clearInterval(pingTimer);
            pingTimer = null;
        }
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
            connect();
        }, reconnectDelay);
    }

    function updateStatusDot(connected) {
        const dot = document.querySelector('#status-ws .status-dot');
        if (dot) {
            dot.className = 'status-dot ' + (connected ? 'online' : 'offline');
        }
    }

    function isConnected() {
        return ws && ws.readyState === WebSocket.OPEN;
    }

    return {
        connect,
        disconnect,
        isConnected,
        get onAlert() { return onAlert; },
        set onAlert(fn) { onAlert = fn; },
    };
})();
