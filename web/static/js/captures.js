/* NetworkTap - Capture Management View */

const Captures = (() => {

    async function render(container) {
        container.innerHTML = `
            <div class="stat-grid">
                <div class="stat-card">
                    <span class="stat-label">Capture Status</span>
                    <span class="stat-value" id="cap-status">--</span>
                    <span class="stat-sub" id="cap-iface"></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Capture Files</span>
                    <span class="stat-value" id="cap-count">--</span>
                    <span class="stat-sub" id="cap-size"></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Rotation</span>
                    <span class="stat-value" id="cap-rotate">--</span>
                    <span class="stat-sub" id="cap-compress"></span>
                </div>
            </div>

            <div class="card" style="margin-bottom:24px">
                <div class="card-header">
                    <span class="card-title">Capture Control</span>
                    <div style="display:flex;gap:8px">
                        <button class="btn btn-primary" id="btn-start-capture">Start Capture</button>
                        <button class="btn btn-danger" id="btn-stop-capture">Stop Capture</button>
                    </div>
                </div>
                <p id="cap-filter-info" style="color:var(--text-muted);font-size:0.85rem;"></p>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Recent Capture Files</span>
                    <div style="display:flex;gap:8px">
                        <button class="btn btn-sm btn-secondary" id="btn-refresh-files">Refresh</button>
                        <button class="btn btn-sm btn-danger" id="btn-delete-all">Delete All</button>
                    </div>
                </div>
                <div id="cap-files">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>
        `;

        document.getElementById('btn-start-capture').addEventListener('click', startCapture);
        document.getElementById('btn-stop-capture').addEventListener('click', stopCapture);
        document.getElementById('btn-refresh-files').addEventListener('click', refresh);
        document.getElementById('btn-delete-all').addEventListener('click', deleteAllFiles);

        await refresh();
        App.setRefresh(refresh, 5000);
    }

    async function refresh() {
        try {
            const status = await api('/api/capture/status');
            updateStatus(status);
        } catch (e) {
            // retry next interval
        }
    }

    function updateStatus(status) {
        const statusEl = document.getElementById('cap-status');
        statusEl.textContent = status.running ? 'Active' : 'Stopped';
        statusEl.style.color = status.running ? 'var(--green)' : 'var(--text-muted)';

        document.getElementById('cap-iface').textContent = `Interface: ${status.interface} (${status.mode} mode)`;
        document.getElementById('cap-count').textContent = status.file_count;
        document.getElementById('cap-size').textContent = formatBytes(status.total_size);
        document.getElementById('cap-rotate').textContent = formatDuration(status.rotation_seconds);
        document.getElementById('cap-compress').textContent = status.compress ? 'Compression: ON' : 'Compression: OFF';

        const filterInfo = document.getElementById('cap-filter-info');
        filterInfo.textContent = status.filter
            ? `BPF Filter: ${status.filter}`
            : 'Capturing all traffic (no BPF filter)';

        // Update buttons
        document.getElementById('btn-start-capture').disabled = status.running;
        document.getElementById('btn-stop-capture').disabled = !status.running;

        // Recent files
        const filesEl = document.getElementById('cap-files');
        if (!status.recent_files || status.recent_files.length === 0) {
            filesEl.innerHTML = '<div class="empty-state"><h3>No capture files yet</h3></div>';
            return;
        }

        filesEl.innerHTML = status.recent_files.map(f => `
            <div class="file-item">
                <div class="file-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                </div>
                <div class="file-info">
                    <div class="file-name">${escapeHtml(f.name)}</div>
                    <div class="file-meta">${formatBytes(f.size)} &middot; ${formatDate(f.modified)}</div>
                </div>
                <div class="file-actions">
                    <a href="/api/pcap/download/${encodeURIComponent(f.name)}" class="btn btn-sm btn-secondary" title="Download">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </a>
                    <button class="btn btn-sm btn-danger delete-file-btn" data-filename="${escapeHtml(f.name)}" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6l-2 14H7L5 6"/>
                            <path d="M10 11v6"/>
                            <path d="M14 11v6"/>
                            <path d="M9 6V4h6v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');

        // Bind delete buttons
        filesEl.querySelectorAll('.delete-file-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteFile(btn.dataset.filename));
        });
    }

    async function startCapture() {
        try {
            const result = await api('/api/capture/start', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            await refresh();
        } catch (e) {
            toast('Failed to start capture: ' + e.message, 'error');
        }
    }

    async function stopCapture() {
        try {
            const result = await api('/api/capture/stop', { method: 'POST' });
            toast(result.message, result.success ? 'success' : 'error');
            await refresh();
        } catch (e) {
            toast('Failed to stop capture: ' + e.message, 'error');
        }
    }

    function formatDuration(seconds) {
        if (seconds >= 3600) return (seconds / 3600) + 'h';
        if (seconds >= 60) return (seconds / 60) + 'm';
        return seconds + 's';
    }

    async function deleteFile(filename) {
        if (!confirm(`Delete ${filename}?`)) return;

        try {
            const result = await api(`/api/capture/files/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });
            toast(result.message, result.success ? 'success' : 'error');
            await refresh();
        } catch (e) {
            toast('Failed to delete file: ' + e.message, 'error');
        }
    }

    async function deleteAllFiles() {
        if (!confirm('Delete ALL capture files? This cannot be undone.')) return;

        try {
            const result = await api('/api/capture/files', { method: 'DELETE' });
            toast(result.message, result.success ? 'success' : 'error');
            await refresh();
        } catch (e) {
            toast('Failed to delete files: ' + e.message, 'error');
        }
    }

    return { render };
})();
