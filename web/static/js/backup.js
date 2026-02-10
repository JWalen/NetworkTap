/* NetworkTap - Backup & Restore Page */

const Backup = (() => {
    async function render(container) {
        container.innerHTML = `
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Create Backup</span>
                    </div>
                    <p class="form-help" style="margin-bottom:16px">
                        Create a backup of all NetworkTap configuration files, including:<br>
                        • Main configuration (networktap.conf)<br>
                        • User accounts<br>
                        • Suricata/Zeek settings<br>
                        • TLS certificates
                    </p>
                    <div class="form-group">
                        <label class="form-label">Description (optional)</label>
                        <input type="text" id="backup-description" placeholder="e.g., Before upgrade" style="width:100%">
                    </div>
                    <button class="btn btn-primary" id="btn-create-backup">Create Backup</button>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Restore from Backup</span>
                    </div>
                    <p class="form-help" style="margin-bottom:16px">
                        Upload a previously downloaded backup to restore configuration.
                        A pre-restore backup will be created automatically.
                    </p>
                    <div class="form-group">
                        <label class="form-label">Upload Backup File</label>
                        <input type="file" id="backup-file" accept=".tar.gz" style="width:100%">
                    </div>
                    <button class="btn btn-secondary" id="btn-upload-backup">Upload & Preview</button>
                </div>
            </div>

            <div class="card" style="margin-top:20px">
                <div class="card-header">
                    <span class="card-title">Available Backups</span>
                </div>
                <div id="backups-list">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>

            <!-- Restore Preview Modal -->
            <div class="modal" id="restore-modal" style="display:none">
                <div class="modal-content">
                    <div class="modal-header">
                        <span class="modal-title">Restore Preview</span>
                        <button class="modal-close" id="close-restore-modal">&times;</button>
                    </div>
                    <div id="restore-preview">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>
        `;

        loadBackups();
        setupEventListeners();
    }

    function setupEventListeners() {
        document.getElementById('btn-create-backup').addEventListener('click', createBackup);
        document.getElementById('btn-upload-backup').addEventListener('click', uploadBackup);
        document.getElementById('close-restore-modal').addEventListener('click', () => {
            document.getElementById('restore-modal').style.display = 'none';
        });
    }

    async function loadBackups() {
        const container = document.getElementById('backups-list');

        try {
            const data = await api('/api/backup/');

            if (data.backups.length === 0) {
                container.innerHTML = '<p class="form-help">No backups available. Create one to get started.</p>';
                return;
            }

            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Filename</th>
                            <th>Created</th>
                            <th>Size</th>
                            <th>Description</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.backups.map(b => `
                            <tr>
                                <td style="font-family:monospace;font-size:0.85rem">${escapeHtml(b.filename)}</td>
                                <td>${formatDate(b.created_at)}</td>
                                <td>${formatBytes(b.size)}</td>
                                <td>${escapeHtml(b.description) || '-'}</td>
                                <td>
                                    <a href="/api/backup/${encodeURIComponent(b.filename)}/download" class="btn btn-sm btn-secondary" download>Download</a>
                                    <button class="btn btn-sm btn-primary" onclick="Backup.previewRestore('${escapeHtml(b.filename)}')">Restore</button>
                                    <button class="btn btn-sm btn-danger" onclick="Backup.deleteBackup('${escapeHtml(b.filename)}')">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            container.innerHTML = `<p class="form-help" style="color:var(--red)">Error: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function createBackup() {
        const description = document.getElementById('backup-description').value.trim();
        const btn = document.getElementById('btn-create-backup');
        
        btn.disabled = true;
        btn.textContent = 'Creating...';

        try {
            const result = await api('/api/backup/', {
                method: 'POST',
                body: { description }
            });

            toast('Backup created: ' + result.filename, 'success');
            document.getElementById('backup-description').value = '';
            loadBackups();
        } catch (e) {
            toast('Failed to create backup: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create Backup';
        }
    }

    async function uploadBackup() {
        const fileInput = document.getElementById('backup-file');
        const file = fileInput.files[0];

        if (!file) {
            toast('Please select a backup file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const creds = Settings.getCredentials();
            const resp = await fetch('/api/backup/upload', {
                method: 'POST',
                headers: {
                    'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass)
                },
                body: formData
            });

            if (!resp.ok) {
                const error = await resp.text();
                throw new Error(error);
            }

            toast('Backup uploaded successfully', 'success');
            fileInput.value = '';
            loadBackups();
        } catch (e) {
            toast('Upload failed: ' + e.message, 'error');
        }
    }

    async function previewRestore(filename) {
        const modal = document.getElementById('restore-modal');
        const preview = document.getElementById('restore-preview');
        
        modal.style.display = 'flex';
        preview.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const result = await api(`/api/backup/${encodeURIComponent(filename)}/restore?dry_run=true`, {
                method: 'POST'
            });

            preview.innerHTML = `
                <p style="margin-bottom:16px">The following files will be restored:</p>
                <div style="max-height:300px;overflow-y:auto;background:var(--bg-input);padding:12px;border-radius:var(--radius);font-family:monospace;font-size:0.85rem">
                    ${result.restored_files.map(f => `<div>${escapeHtml(f)}</div>`).join('')}
                </div>
                <div class="form-help" style="margin-top:16px;color:var(--yellow)">
                    ⚠️ Warning: This will overwrite existing configuration files. A pre-restore backup will be created automatically.
                </div>
                <div style="display:flex;gap:12px;margin-top:20px">
                    <button class="btn btn-danger" onclick="Backup.doRestore('${escapeHtml(filename)}')">Restore Now</button>
                    <button class="btn btn-secondary" onclick="document.getElementById('restore-modal').style.display='none'">Cancel</button>
                </div>
            `;
        } catch (e) {
            preview.innerHTML = `<p style="color:var(--red)">Error: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function doRestore(filename) {
        try {
            const result = await api(`/api/backup/${encodeURIComponent(filename)}/restore`, {
                method: 'POST'
            });

            document.getElementById('restore-modal').style.display = 'none';
            toast(`Restored ${result.restored_files.length} files. Restart services to apply changes.`, 'success');
            loadBackups();
        } catch (e) {
            toast('Restore failed: ' + e.message, 'error');
        }
    }

    async function deleteBackup(filename) {
        if (!confirm(`Delete backup "${filename}"? This cannot be undone.`)) {
            return;
        }

        try {
            await api(`/api/backup/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });

            toast('Backup deleted', 'success');
            loadBackups();
        } catch (e) {
            toast('Failed to delete backup: ' + e.message, 'error');
        }
    }

    return { render, previewRestore, doRestore, deleteBackup };
})();
