// Auto-Update Management Page
const Updates = (() => {
    let updateInterval = null;
    let currentStatus = null;

    async function render(container) {
        container.innerHTML = `
            <div class="page-header">
                <h1>System Updates</h1>
                <p>Manage NetworkTap software updates from GitHub releases</p>
            </div>

            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Current Version</div>
                    <div id="current-version">Loading...</div>
                </div>

                <div class="card">
                    <div class="card-header">Update Status</div>
                    <div id="update-status">Loading...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Available Updates</div>
                <button class="btn btn-primary" onclick="Updates.checkForUpdates()">
                    <i class="icon">🔍</i> Check for Updates
                </button>
                <div id="update-check" style="margin-top: 1rem;">
                    Click "Check for Updates" to see if a new version is available
                </div>
            </div>

            <div class="card" id="update-actions-card" style="display: none;">
                <div class="card-header">Update Actions</div>
                <div class="button-group">
                    <button class="btn btn-success" onclick="Updates.performUpdate()">
                        <i class="icon">⬆️</i> Update Now
                    </button>
                    <button class="btn btn-primary" onclick="Updates.downloadOnly()">
                        <i class="icon">⬇️</i> Download Only
                    </button>
                </div>
                <div id="update-progress" style="margin-top: 1rem;"></div>
            </div>

            <div class="card">
                <div class="card-header">Update History</div>
                <button class="btn btn-secondary" onclick="Updates.loadHistory()">
                    <i class="icon">🔄</i> Refresh History
                </button>
                <div id="update-history" style="margin-top: 1rem;">Loading...</div>
            </div>

            <div class="card">
                <div class="card-header">Rollback</div>
                <p class="help-text">If an update causes issues, you can rollback to the previous version</p>
                <button class="btn btn-warning" onclick="Updates.rollback()">
                    <i class="icon">↩️</i> Rollback to Previous Version
                </button>
                <div id="rollback-status" style="margin-top: 1rem;"></div>
            </div>
        `;

        loadCurrentVersion();
        loadUpdateStatus();
        loadHistory();
        startPolling();
    }

    function startPolling() {
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(() => {
            loadUpdateStatus();
        }, 5000);
    }

    async function loadCurrentVersion() {
        try {
            const result = await api('/api/update/current');
            const html = `
                <div class="stat-row">
                    <span>Version:</span>
                    <span><strong>${result.version || 'unknown'}</strong></span>
                </div>
                <div class="stat-row">
                    <span>Installed:</span>
                    <span>${result.installed_date ? new Date(result.installed_date).toLocaleDateString() : 'Unknown'}</span>
                </div>
                ${result.commit_hash ? `
                    <div class="stat-row">
                        <span>Commit:</span>
                        <span><code>${result.commit_hash.substring(0, 8)}</code></span>
                    </div>
                ` : ''}
                <div class="stat-row">
                    <span>Repository:</span>
                    <span><code>${result.repository || 'JWalen/NetworkTap'}</code></span>
                </div>
            `;
            document.getElementById('current-version').innerHTML = html;
        } catch (error) {
            document.getElementById('current-version').innerHTML = 
                '<div class="status-error">Error loading version info</div>';
        }
    }

    async function loadUpdateStatus() {
        try {
            const result = await api('/api/update/status');
            currentStatus = result;

            let statusHtml = '';
            
            if (result.in_progress) {
                statusHtml = `
                    <div class="status-warn">
                        <strong>Update in Progress</strong>
                    </div>
                    <div class="stat-row">
                        <span>Operation:</span>
                        <span>${result.operation || 'Unknown'}</span>
                    </div>
                    <div class="stat-row">
                        <span>Progress:</span>
                        <span>${result.progress || 0}%</span>
                    </div>
                    ${result.message ? `<p style="margin-top: 0.5rem;">${result.message}</p>` : ''}
                `;
                
                // Show progress in update actions card
                const progressEl = document.getElementById('update-progress');
                if (progressEl) {
                    progressEl.innerHTML = `
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${result.progress || 0}%"></div>
                        </div>
                        <p>${result.message || 'Processing...'}</p>
                    `;
                }
            } else {
                statusHtml = '<div class="status-good">No update in progress</div>';
                
                const progressEl = document.getElementById('update-progress');
                if (progressEl) {
                    progressEl.innerHTML = '';
                }
            }

            document.getElementById('update-status').innerHTML = statusHtml;
        } catch (error) {
            document.getElementById('update-status').innerHTML = 
                '<div class="status-off">Idle</div>';
        }
    }

    async function loadHistory() {
        try {
            const result = await api('/api/update/history');
            
            if (!result.history || result.history.length === 0) {
                document.getElementById('update-history').innerHTML = 
                    '<div class="empty-state">No update history available</div>';
                return;
            }

            const historyHtml = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Version</th>
                            <th>From Version</th>
                            <th>Status</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.history.map(h => `
                            <tr>
                                <td>${new Date(h.timestamp).toLocaleString()}</td>
                                <td><strong>${h.version}</strong></td>
                                <td>${h.previous_version || 'N/A'}</td>
                                <td>
                                    <span class="badge badge-${h.success ? 'success' : 'danger'}">
                                        ${h.success ? 'Success' : 'Failed'}
                                    </span>
                                </td>
                                <td>${h.notes || ''}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            document.getElementById('update-history').innerHTML = historyHtml;
        } catch (error) {
            document.getElementById('update-history').innerHTML = 
                '<div class="status-error">Error loading update history</div>';
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // User Actions
    // ═══════════════════════════════════════════════════════════════════════

    window.Updates = window.Updates || {};

    window.Updates.checkForUpdates = async function() {
        const checkEl = document.getElementById('update-check');
        const actionsCard = document.getElementById('update-actions-card');
        
        checkEl.innerHTML = '<div class="loading">Checking for updates...</div>';
        
        try {
            const result = await api('/api/update/check');
            
            if (result.update_available) {
                checkEl.innerHTML = `
                    <div class="alert alert-info">
                        <h3>Update Available!</h3>
                        <div class="stat-row">
                            <span>Current Version:</span>
                            <span><strong>${result.current_version}</strong></span>
                        </div>
                        <div class="stat-row">
                            <span>Latest Version:</span>
                            <span><strong style="color: var(--accent);">${result.latest_version}</strong></span>
                        </div>
                        <div class="stat-row">
                            <span>Release Date:</span>
                            <span>${new Date(result.published_at).toLocaleDateString()}</span>
                        </div>
                        ${result.release_notes ? `
                            <div style="margin-top: 1rem;">
                                <strong>Release Notes:</strong>
                                <pre style="max-height: 200px; overflow-y: auto; margin-top: 0.5rem; padding: 0.5rem; background: rgba(0,0,0,0.3); border-radius: 4px;">${result.release_notes}</pre>
                            </div>
                        ` : ''}
                    </div>
                `;
                
                actionsCard.style.display = 'block';
            } else {
                checkEl.innerHTML = `
                    <div class="status-good">
                        <strong>You're up to date!</strong>
                        <p>Running version ${result.current_version} (latest: ${result.latest_version})</p>
                    </div>
                `;
                
                actionsCard.style.display = 'none';
            }
        } catch (error) {
            checkEl.innerHTML = `
                <div class="status-error">
                    Failed to check for updates: ${error.message}
                </div>
            `;
        }
    };

    window.Updates.downloadOnly = async function() {
        if (currentStatus && currentStatus.in_progress) {
            toast('An update operation is already in progress', 'warning');
            return;
        }

        if (!confirm('Download the latest version? (This will not install it yet)')) {
            return;
        }

        const progressEl = document.getElementById('update-progress');
        progressEl.innerHTML = '<div class="loading">Starting download...</div>';

        try {
            const result = await api('/api/update/download', { method: 'POST' });
            
            if (result.success) {
                toast('Download started! Check status above.', 'success');
                
                // Poll for completion
                const checkDownload = setInterval(async () => {
                    const status = await api('/api/update/status');
                    if (!status.in_progress) {
                        clearInterval(checkDownload);
                        toast('Download complete!', 'success');
                        progressEl.innerHTML = '<div class="status-good">Download complete. Ready to install.</div>';
                    }
                }, 2000);
            } else {
                toast(result.message || 'Download failed', 'error');
                progressEl.innerHTML = `<div class="status-error">${result.message}</div>`;
            }
        } catch (error) {
            toast('Download failed: ' + error.message, 'error');
            progressEl.innerHTML = `<div class="status-error">Download failed: ${error.message}</div>`;
        }
    };

    window.Updates.performUpdate = async function() {
        if (currentStatus && currentStatus.in_progress) {
            toast('An update operation is already in progress', 'warning');
            return;
        }

        if (!confirm('⚠️ This will update NetworkTap and restart all services. Continue?')) {
            return;
        }

        const progressEl = document.getElementById('update-progress');
        progressEl.innerHTML = '<div class="loading">Starting update process...</div>';

        try {
            const result = await api('/api/update/update', { method: 'POST' });
            
            if (result.success) {
                toast('Update started! This may take several minutes.', 'success');
                progressEl.innerHTML = `
                    <div class="alert alert-info">
                        <strong>Update in Progress</strong>
                        <p>The system will restart services when complete.</p>
                        <p>This page will automatically refresh.</p>
                    </div>
                `;
                
                // Poll for completion and refresh when done
                let pollCount = 0;
                const checkUpdate = setInterval(async () => {
                    try {
                        const status = await api('/api/update/status');
                        if (!status.in_progress) {
                            clearInterval(checkUpdate);
                            toast('Update complete! Reloading...', 'success');
                            setTimeout(() => location.reload(), 2000);
                        }
                    } catch (error) {
                        pollCount++;
                        if (pollCount > 30) { // 30 * 3 = 90 seconds
                            clearInterval(checkUpdate);
                            progressEl.innerHTML = `
                                <div class="alert alert-warning">
                                    <strong>Update may be complete</strong>
                                    <p>Unable to check status. Please refresh the page manually.</p>
                                    <button class="btn btn-primary" onclick="location.reload()">Reload Page</button>
                                </div>
                            `;
                        }
                    }
                }, 3000);
            } else {
                toast(result.message || 'Update failed', 'error');
                progressEl.innerHTML = `<div class="status-error">${result.message}</div>`;
            }
        } catch (error) {
            toast('Update failed: ' + error.message, 'error');
            progressEl.innerHTML = `<div class="status-error">Update failed: ${error.message}</div>`;
        }
    };

    window.Updates.rollback = async function() {
        if (currentStatus && currentStatus.in_progress) {
            toast('An update operation is in progress. Please wait.', 'warning');
            return;
        }

        if (!confirm('⚠️ Rollback to the previous version? This will restart all services.')) {
            return;
        }

        const statusEl = document.getElementById('rollback-status');
        statusEl.innerHTML = '<div class="loading">Rolling back...</div>';

        try {
            const result = await api('/api/update/rollback', { method: 'POST' });
            
            if (result.success) {
                toast('Rollback successful! Reloading...', 'success');
                statusEl.innerHTML = `
                    <div class="status-good">
                        Rollback complete. Rolled back to version ${result.rolled_back_to || 'previous'}.
                    </div>
                `;
                setTimeout(() => location.reload(), 2000);
            } else {
                toast(result.message || 'Rollback failed', 'error');
                statusEl.innerHTML = `<div class="status-error">${result.message}</div>`;
            }
        } catch (error) {
            toast('Rollback failed: ' + error.message, 'error');
            statusEl.innerHTML = `<div class="status-error">Rollback failed: ${error.message}</div>`;
        }
    };

    window.Updates.loadHistory = loadHistory;

    function cleanup() {
        if (updateInterval) {
            clearInterval(updateInterval);
            updateInterval = null;
        }
    }

    return { render, cleanup };
})();
