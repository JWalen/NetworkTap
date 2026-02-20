/* NetworkTap - Main SPA Router & Init */

const App = (() => {
    const pages = {
        dashboard: Dashboard,
        captures: Pcaps,
        alerts: Alerts,
        network: Network,
        pcaps: Pcaps,
        terminal: Terminal,
        wifi: WiFi,
        updates: Updates,
        settings: Settings,
        stats: Stats,
        rules: Rules,
        zeek: Zeek,
        suricata: Suricata,
        ai: AI,
        backup: Backup,
        users: Users,
        help: Help,
    };

    let currentPage = null;
    let refreshInterval = null;

    function init() {
        try {
            // Load theme preference
            loadTheme();

            // Navigation
            document.querySelectorAll('.nav-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    const page = item.dataset.page;
                    navigate(page);
                });
            });

            // Sidebar toggle (mobile)
            const sidebarToggle = document.getElementById('sidebar-toggle');
            if (sidebarToggle) {
                sidebarToggle.addEventListener('click', () => {
                    document.getElementById('sidebar').classList.toggle('open');
                });
            }

            // Close sidebar on content click (mobile)
            const content = document.querySelector('.content');
            if (content) {
                content.addEventListener('click', () => {
                    document.getElementById('sidebar').classList.remove('open');
                });
            }

            // Theme toggle
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) {
                themeToggle.addEventListener('click', toggleTheme);
            }

            // Hash-based routing
            window.addEventListener('hashchange', () => {
                const page = location.hash.slice(1) || 'dashboard';
                navigate(page, false);
            });

            // Connect WebSocket
            WS.connect();

            // Initial navigation
            const page = location.hash.slice(1) || 'dashboard';
            navigate(page, false);

            // Start global status polling
            updateGlobalStatus();
            setInterval(updateGlobalStatus, 10000);

            console.log('✓ NetworkTap initialized successfully');
        } catch (error) {
            console.error('Failed to initialize NetworkTap:', error);
            toast('Failed to initialize application', 'error');
        }
    }

    function navigate(page, pushHash = true) {
        if (!pages[page]) page = 'dashboard';

        // Update hash
        if (pushHash) location.hash = page;

        // Update nav active state
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Update title
        const titles = {
            dashboard: 'Dashboard',
            captures: 'Captures & PCAPs',
            alerts: 'IDS Alerts',
            network: 'Network',
            pcaps: 'Captures & PCAPs',
            terminal: 'Terminal',
            settings: 'Settings',
            stats: 'Traffic Statistics',
            rules: 'Suricata Rules',
            zeek: 'Zeek Logs',
            suricata: 'Suricata Logs',
            ai: 'AI Analysis',
            help: 'Help',
        };
        document.getElementById('page-title').textContent = titles[page] || page;

        // Clear previous refresh
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }

        // Call cleanup on previous page if it has one
        if (currentPage && pages[currentPage] && typeof pages[currentPage].cleanup === 'function') {
            try { pages[currentPage].cleanup(); } catch (e) { /* ignore */ }
        }

        // Render page
        currentPage = page;
        const container = document.getElementById('content');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        pages[page].render(container);

        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
    }

    function setRefresh(fn, ms) {
        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(() => {
            if (document.visibilityState === 'visible') fn();
        }, ms);
    }

    async function updateGlobalStatus() {
        try {
            const resp = await api('/api/system/status');
            const services = resp.services || [];

            // Update status dots in topbar
            for (const svc of services) {
                let el = null;
                if (svc.name === 'networktap-capture') el = document.querySelector('#status-capture .status-dot');
                if (svc.name === 'networktap-suricata') el = document.querySelector('#status-suricata .status-dot');
                if (svc.name === 'networktap-zeek') el = document.querySelector('#status-zeek .status-dot');
                if (el) {
                    el.className = 'status-dot ' + (svc.running ? 'online' : 'offline');
                }
            }

            // Update mode indicator
            const modeText = document.querySelector('.mode-text');
            if (modeText) {
                modeText.textContent = (resp.mode || 'span').toUpperCase() + ' Mode';
            }
        } catch (e) {
            // Silently fail status updates
        }
    }

    return { init, navigate, setRefresh };
})();

/* ── API Helper ─────────────────────────────────────── */
let activeRequests = 0;

async function api(url, options = {}) {
    const config = Settings.getCredentials();
    const headers = {
        'Authorization': 'Basic ' + btoa(config.user + ':' + config.pass),
        ...options.headers,
    };

    if (options.body && typeof options.body === 'object') {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    // Show loading indicator
    activeRequests++;
    updateLoadingIndicator();

    try {
        const resp = await fetch(url, { ...options, headers });

        if (resp.status === 401) {
            toast('Authentication failed. Check credentials in Settings.', 'error');
            throw new Error('Unauthorized');
        }

        if (resp.status === 403) {
            toast('Access forbidden. Insufficient permissions.', 'error');
            throw new Error('Forbidden');
        }

        if (resp.status === 404) {
            toast('Resource not found.', 'error');
            throw new Error('Not Found');
        }

        if (resp.status >= 500) {
            toast('Server error. Please try again later.', 'error');
            throw new Error('Server Error');
        }

        if (!resp.ok) {
            const text = await resp.text();
            toast(text || resp.statusText, 'error');
            throw new Error(text || resp.statusText);
        }

        return await resp.json();
    } catch (error) {
        // Network error or other fetch failure
        if (error.message === 'Failed to fetch') {
            toast('Network error. Check connection to server.', 'error');
        }
        throw error;
    } finally {
        activeRequests--;
        updateLoadingIndicator();
    }
}

function updateLoadingIndicator() {
    // Add/remove loading state class to body for global loading indicator
    // Note: uses 'is-loading' to avoid conflict with .loading CSS (display:flex)
    if (activeRequests > 0) {
        document.body.classList.add('is-loading');
    } else {
        document.body.classList.remove('is-loading');
    }
}

/* ── Toast Notifications ────────────────────────────── */
function toast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateX(100%)';
        setTimeout(() => el.remove(), 300);
    }, 4000);
}

/* ── Utility Functions ──────────────────────────────── */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function formatTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(ts);
        return d.toLocaleTimeString();
    } catch {
        return ts;
    }
}

function formatDate(ts) {
    if (!ts) return '';
    try {
        const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
        return d.toLocaleString();
    } catch {
        return ts;
    }
}

function barColor(pct) {
    if (pct >= 90) return 'red';
    if (pct >= 70) return 'orange';
    if (pct >= 50) return 'yellow';
    return 'green';
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// Safe innerHTML replacement - use this instead of innerHTML
function setHtml(element, html) {
    element.innerHTML = html;
}

// Create element with safe text content
function createElement(tag, text = '', className = '') {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (className) el.className = className;
    return el;
}

/* ── Start ──────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', App.init);

/* ── Theme Management ───────────────────────────────── */
function loadTheme() {
    const theme = localStorage.getItem('networktap_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('networktap_theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.innerHTML = theme === 'dark'
            ? '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
            : '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    }
}

/* ── Skeleton Loading Helpers ──────────────────────── */
function skeleton(type, count = 1) {
    const templates = {
        text: '<div class="skeleton skeleton-text"></div>',
        stat: '<div class="skeleton skeleton-stat"></div>',
        chart: '<div class="skeleton skeleton-chart"></div>',
        row: '<div class="skeleton skeleton-row"></div>',
    };
    return (templates[type] || templates.text).repeat(count);
}

function skeletonTable(rows = 5, cols = 4) {
    let html = '<table><thead><tr>';
    for (let i = 0; i < cols; i++) {
        html += '<th><div class="skeleton skeleton-text" style="width:80%"></div></th>';
    }
    html += '</tr></thead><tbody>';
    for (let i = 0; i < rows; i++) {
        html += '<tr>';
        for (let j = 0; j < cols; j++) {
            html += '<td><div class="skeleton skeleton-text"></div></td>';
        }
        html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
}

/* ── Animated Number Updates ───────────────────────── */
function animateValue(element, newValue, format = v => v) {
    if (!element) return;

    const currentText = element.textContent;
    const formattedNew = format(newValue);

    if (currentText === formattedNew) return;

    element.classList.add('updating');

    setTimeout(() => {
        element.textContent = formattedNew;
        element.classList.remove('updating');
    }, 100);
}

/* ── Chart Tooltip System ──────────────────────────── */
const ChartTooltip = (() => {
    let tooltip = null;

    function init() {
        if (tooltip) return;
        tooltip = document.createElement('div');
        tooltip.className = 'chart-tooltip';
        document.body.appendChild(tooltip);
    }

    function show(x, y, label, value) {
        init();
        tooltip.innerHTML = `
            <div class="chart-tooltip-label">${escapeHtml(label)}</div>
            <div class="chart-tooltip-value">${escapeHtml(value)}</div>
        `;

        // Position with viewport bounds check
        const rect = tooltip.getBoundingClientRect();
        const pad = 10;

        let left = x + pad;
        let top = y - pad - 40;

        if (left + 200 > window.innerWidth) {
            left = x - 200 - pad;
        }
        if (top < 10) {
            top = y + pad;
        }

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.classList.add('visible');
    }

    function hide() {
        if (tooltip) {
            tooltip.classList.remove('visible');
        }
    }

    return { show, hide };
})();

/* ── Pagination Helper ─────────────────────────────── */
function renderPagination(container, currentPage, totalPages, onPageChange) {
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '<div class="pagination">';

    // Prev button
    html += `<button class="pagination-btn" ${currentPage <= 1 ? 'disabled' : ''} data-page="${currentPage - 1}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
        </svg>
    </button>`;

    // Page numbers
    const range = 2;
    let start = Math.max(1, currentPage - range);
    let end = Math.min(totalPages, currentPage + range);

    if (start > 1) {
        html += `<button class="pagination-btn" data-page="1">1</button>`;
        if (start > 2) html += `<span class="pagination-info">...</span>`;
    }

    for (let i = start; i <= end; i++) {
        html += `<button class="pagination-btn ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
    }

    if (end < totalPages) {
        if (end < totalPages - 1) html += `<span class="pagination-info">...</span>`;
        html += `<button class="pagination-btn" data-page="${totalPages}">${totalPages}</button>`;
    }

    // Next button
    html += `<button class="pagination-btn" ${currentPage >= totalPages ? 'disabled' : ''} data-page="${currentPage + 1}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
        </svg>
    </button>`;

    html += '</div>';
    container.innerHTML = html;

    container.querySelectorAll('.pagination-btn:not(:disabled)').forEach(btn => {
        btn.addEventListener('click', () => onPageChange(parseInt(btn.dataset.page)));
    });
}

/* ── Duration Formatting ───────────────────────────── */
function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '-';
    if (seconds < 1) return (seconds * 1000).toFixed(0) + 'ms';
    if (seconds < 60) return seconds.toFixed(2) + 's';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + Math.floor(seconds % 60) + 's';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h + 'h ' + m + 'm';
}

/* ── Relative Time ─────────────────────────────────── */
function formatRelativeTime(timestamp) {
    if (!timestamp) return '';
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = (now - date) / 1000;

        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
        return date.toLocaleDateString();
    } catch {
        return timestamp;
    }
}

/* ── Debounce Helper ───────────────────────────────── */
function debounce(fn, delay) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), delay);
    };
}
