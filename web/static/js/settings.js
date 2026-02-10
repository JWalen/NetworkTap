/* NetworkTap - Settings View with Users & Backup */

const Settings = (() => {
    const CRED_KEY = 'networktap_creds';
    let currentTab = 'auth';
    let currentUserRole = 'admin';

    function getCredentials() {
        try {
            const stored = localStorage.getItem(CRED_KEY);
            if (stored) return JSON.parse(stored);
        } catch {}
        return { user: 'admin', pass: 'networktap' };
    }

    function saveCredentials(user, pass) {
        localStorage.setItem(CRED_KEY, JSON.stringify({ user, pass }));
    }

    async function render(container) {
        // Get current user's role
        try {
            const roleData = await api('/api/users/me/role');
            currentUserRole = roleData.role;
        } catch (e) {
            currentUserRole = 'admin';
        }

        container.innerHTML = `
            <div class="settings-tabs" style="display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap;">
                <button class="btn btn-secondary settings-tab active" data-tab="auth">Authentication</button>
                <button class="btn btn-secondary settings-tab" data-tab="users">Users</button>
                <button class="btn btn-secondary settings-tab" data-tab="backup">Backup</button>
                <button class="btn btn-secondary settings-tab" data-tab="config">Configuration</button>
            </div>
            <div id="settings-content"></div>
        `;

        container.querySelectorAll('.settings-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.settings-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTab = btn.dataset.tab;
                renderTab(container.querySelector('#settings-content'));
            });
        });

        renderTab(container.querySelector('#settings-content'));
    }

    async function renderTab(container) {
        switch (currentTab) {
            case 'auth': renderAuthTab(container); break;
            case 'users': await renderUsersTab(container); break;
            case 'backup': await renderBackupTab(container); break;
            case 'config': await renderConfigTab(container); break;
        }
    }

    function renderAuthTab(container) {
        const creds = getCredentials();
        container.innerHTML = `
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Browser Credentials</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Username</label>
                        <input type="text" id="set-user" value="${escapeHtml(creds.user)}" style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" id="set-pass" value="${escapeHtml(creds.pass)}" style="width:100%">
                    </div>
                    <button class="btn btn-primary" id="btn-save-creds">Save to Browser</button>
                    <p class="form-help">These credentials are stored locally in your browser for API authentication.</p>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Change Your Password</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Current Password</label>
                        <input type="password" id="old-password" style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">New Password</label>
                        <input type="password" id="new-password" style="width:100%">
                    </div>
                    <button class="btn btn-primary" id="btn-change-password">Change Password</button>
                </div>
            </div>
        `;

        document.getElementById('btn-save-creds').addEventListener('click', () => {
            const user = document.getElementById('set-user').value.trim();
            const pass = document.getElementById('set-pass').value;
            if (!user || !pass) {
                toast('Username and password required', 'error');
                return;
            }
            saveCredentials(user, pass);
            toast('Credentials saved to browser', 'success');
        });

        document.getElementById('btn-change-password').addEventListener('click', changePassword);
    }

    async function changePassword() {
        const oldPass = document.getElementById('old-password').value;
        const newPass = document.getElementById('new-password').value;

        if (!oldPass || !newPass) {
            toast('Both passwords are required', 'error');
            return;
        }

        try {
            const result = await api('/api/users/me/password', {
                method: 'PUT',
                body: { current_password: oldPass, new_password: newPass },
            });
            toast(result.message || 'Password changed', result.success !== false ? 'success' : 'error');
            if (result.success !== false) {
                document.getElementById('old-password').value = '';
                document.getElementById('new-password').value = '';
                // Update stored credentials
                const creds = getCredentials();
                saveCredentials(creds.user, newPass);
            }
        } catch (e) {
            toast('Failed to change password: ' + e.message, 'error');
        }
    }

    async function renderUsersTab(container) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">User Management</span>
                    ${currentUserRole === 'admin' ? '<button class="btn btn-primary btn-sm" id="btn-add-user">Add User</button>' : ''}
                </div>
                <div id="users-list">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>
            <div class="modal" id="user-modal" style="display:none"></div>
        `;

        if (currentUserRole === 'admin') {
            document.getElementById('btn-add-user').addEventListener('click', () => showUserModal());
        }
        await loadUsers();
    }

    async function loadUsers() {
        const listEl = document.getElementById('users-list');
        try {
            const data = await api('/api/users/');
            if (!data.users || data.users.length === 0) {
                listEl.innerHTML = '<div class="empty-state"><h3>No users configured</h3><p>Using default credentials from config file.</p></div>';
                return;
            }

            listEl.innerHTML = `
                <table>
                    <thead>
                        <tr><th>Username</th><th>Role</th><th>Created</th>${currentUserRole === 'admin' ? '<th>Actions</th>' : ''}</tr>
                    </thead>
                    <tbody>
                        ${data.users.map(u => `
                            <tr>
                                <td><strong>${escapeHtml(u.username)}</strong></td>
                                <td><span class="role-badge role-${u.role}">${u.role}</span></td>
                                <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}</td>
                                ${currentUserRole === 'admin' ? `
                                    <td>
                                        <button class="btn btn-sm btn-secondary" onclick="Settings.editUser('${escapeHtml(u.username)}', '${u.role}')">Edit</button>
                                        <button class="btn btn-sm btn-danger" onclick="Settings.deleteUser('${escapeHtml(u.username)}')">Delete</button>
                                    </td>
                                ` : ''}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            listEl.innerHTML = `<div class="empty-state"><h3>Unable to load users</h3><p>${escapeHtml(e.message)}</p></div>`;
        }
    }

    function showUserModal(username = '', role = 'viewer') {
        const isEdit = !!username;
        const modal = document.getElementById('user-modal');
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <span class="modal-title">${isEdit ? 'Edit User' : 'Add User'}</span>
                    <button class="modal-close" onclick="Settings.closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Username</label>
                    <input type="text" id="modal-username" value="${escapeHtml(username)}" ${isEdit ? 'readonly' : ''} style="width:100%">
                </div>
                ${!isEdit ? `
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" id="modal-password" style="width:100%">
                    </div>
                ` : ''}
                <div class="form-group">
                    <label class="form-label">Role</label>
                    <select id="modal-role" style="width:100%">
                        <option value="admin" ${role === 'admin' ? 'selected' : ''}>Admin (full access)</option>
                        <option value="viewer" ${role === 'viewer' ? 'selected' : ''}>Viewer (read-only)</option>
                    </select>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
                    <button class="btn btn-secondary" onclick="Settings.closeModal()">Cancel</button>
                    <button class="btn btn-primary" id="btn-save-user">${isEdit ? 'Save' : 'Create'}</button>
                </div>
            </div>
        `;

        document.getElementById('btn-save-user').addEventListener('click', () => saveUser(isEdit));
    }

    async function saveUser(isEdit) {
        const username = document.getElementById('modal-username').value.trim();
        const role = document.getElementById('modal-role').value;
        const password = isEdit ? null : document.getElementById('modal-password')?.value;

        if (!username) {
            toast('Username required', 'error');
            return;
        }

        try {
            if (isEdit) {
                await api(`/api/users/${encodeURIComponent(username)}`, {
                    method: 'PUT',
                    body: { role },
                });
                toast('User updated', 'success');
            } else {
                if (!password) {
                    toast('Password required', 'error');
                    return;
                }
                await api('/api/users/', {
                    method: 'POST',
                    body: { username, password, role },
                });
                toast('User created', 'success');
            }
            closeModal();
            await loadUsers();
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    }

    function editUser(username, role) {
        showUserModal(username, role);
    }

    async function deleteUser(username) {
        if (!confirm(`Delete user "${username}"?`)) return;
        try {
            await api(`/api/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
            toast('User deleted', 'success');
            await loadUsers();
        } catch (e) {
            toast('Delete failed: ' + e.message, 'error');
        }
    }

    function closeModal() {
        document.getElementById('user-modal').style.display = 'none';
    }

    async function renderBackupTab(container) {
        container.innerHTML = `
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Create Backup</span>
                    </div>
                    <p class="form-help" style="margin-bottom:16px">
                        Backup includes: configuration, user accounts, Suricata/Zeek settings, TLS certificates.
                    </p>
                    <div class="form-group">
                        <label class="form-label">Description (optional)</label>
                        <input type="text" id="backup-description" placeholder="e.g., Before upgrade" style="width:100%">
                    </div>
                    <button class="btn btn-primary" id="btn-create-backup">Create & Download</button>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Restore Backup</span>
                    </div>
                    <p class="form-help" style="margin-bottom:16px">
                        Upload a backup file to restore. A pre-restore backup will be created automatically.
                    </p>
                    <div class="form-group">
                        <label class="form-label">Backup File</label>
                        <input type="file" id="backup-file" accept=".tar.gz" style="width:100%">
                    </div>
                    <button class="btn btn-secondary" id="btn-restore-backup">Restore</button>
                </div>
            </div>

            <div class="card" style="margin-top:24px">
                <div class="card-header">
                    <span class="card-title">Backup History</span>
                    <button class="btn btn-sm btn-secondary" id="btn-refresh-backups">Refresh</button>
                </div>
                <div id="backup-list">
                    <div class="loading"><div class="spinner"></div></div>
                </div>
            </div>
        `;

        document.getElementById('btn-create-backup').addEventListener('click', createBackup);
        document.getElementById('btn-restore-backup').addEventListener('click', restoreBackup);
        document.getElementById('btn-refresh-backups').addEventListener('click', loadBackups);
        await loadBackups();
    }

    async function createBackup() {
        const desc = document.getElementById('backup-description').value.trim();
        const btn = document.getElementById('btn-create-backup');
        btn.disabled = true;
        btn.textContent = 'Creating...';

        try {
            const result = await api('/api/backup/create', {
                method: 'POST',
                body: { description: desc },
            });

            if (result.success && result.filename) {
                // Download the backup
                const creds = getCredentials();
                const response = await fetch(`/api/backup/download/${result.filename}`, {
                    headers: { 'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass) }
                });
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = result.filename;
                a.click();
                URL.revokeObjectURL(url);
                toast('Backup created and downloaded', 'success');
            } else {
                toast(result.message || 'Backup failed', 'error');
            }
        } catch (e) {
            toast('Backup failed: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create & Download';
            await loadBackups();
        }
    }

    async function restoreBackup() {
        const fileInput = document.getElementById('backup-file');
        const file = fileInput.files[0];
        if (!file) {
            toast('Select a backup file first', 'error');
            return;
        }

        if (!confirm('This will overwrite current configuration. Continue?')) return;

        const btn = document.getElementById('btn-restore-backup');
        btn.disabled = true;
        btn.textContent = 'Restoring...';

        try {
            const formData = new FormData();
            formData.append('file', file);

            const creds = getCredentials();
            const response = await fetch('/api/backup/restore', {
                method: 'POST',
                headers: { 'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass) },
                body: formData,
            });

            const result = await response.json();
            toast(result.message || 'Restore complete', result.success ? 'success' : 'error');
            fileInput.value = '';
        } catch (e) {
            toast('Restore failed: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Restore';
            await loadBackups();
        }
    }

    async function loadBackups() {
        const listEl = document.getElementById('backup-list');
        try {
            const data = await api('/api/backup/list');
            if (!data.backups || data.backups.length === 0) {
                listEl.innerHTML = '<div class="empty-state"><h3>No backups found</h3></div>';
                return;
            }

            listEl.innerHTML = data.backups.map(b => `
                <div class="file-item">
                    <div class="file-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </div>
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(b.filename)}</div>
                        <div class="file-meta">${escapeHtml(b.description || '')} &middot; ${formatBytes(b.size)}</div>
                    </div>
                    <button class="btn btn-sm btn-secondary" onclick="Settings.downloadBackup('${escapeHtml(b.filename)}')">Download</button>
                </div>
            `).join('');
        } catch (e) {
            listEl.innerHTML = `<div class="empty-state"><h3>Unable to load backups</h3></div>`;
        }
    }

    async function downloadBackup(filename) {
        const creds = getCredentials();
        const response = await fetch(`/api/backup/download/${encodeURIComponent(filename)}`, {
            headers: { 'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass) }
        });
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    async function renderConfigTab(container) {
        let config = {};
        try {
            config = await api('/api/config/');
        } catch {}

        container.innerHTML = `
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">System</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Operating Mode</label>
                        <input type="text" value="${escapeHtml(config.mode || 'unknown')}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Capture Interface</label>
                        <input type="text" value="${escapeHtml(config.capture_interface || 'auto')}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Management Interface</label>
                        <input type="text" value="${escapeHtml(config.management_interface || 'auto')}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Web Port</label>
                        <input type="text" value="${config.web_port || 8443}" readonly style="width:100%">
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Capture</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Capture Directory</label>
                        <input type="text" value="${escapeHtml(config.capture_dir || '/var/lib/networktap/captures')}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Rotation Interval</label>
                        <input type="text" value="${config.capture_rotate_seconds || 3600}s" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Compression</label>
                        <input type="text" value="${config.capture_compress ? 'Enabled' : 'Disabled'}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Retention</label>
                        <input type="text" value="${config.retention_days || 7} days" readonly style="width:100%">
                    </div>
                </div>
            </div>

            <div class="grid-2" style="margin-top:24px">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">IDS Status</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Suricata</label>
                        <input type="text" value="${config.suricata_enabled ? 'Enabled' : 'Disabled'}" readonly style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Zeek</label>
                        <input type="text" value="${config.zeek_enabled ? 'Enabled' : 'Disabled'}" readonly style="width:100%">
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Edit Config</span>
                    </div>
                    <p class="form-help">
                        To modify settings, edit the configuration file on the server:<br><br>
                        <code>sudo nano /etc/networktap.conf</code><br><br>
                        Then restart the web service:<br><br>
                        <code>sudo systemctl restart networktap-web</code>
                    </p>
                </div>
            </div>
        `;
    }

    return { 
        render, 
        getCredentials, 
        editUser, 
        deleteUser, 
        closeModal,
        downloadBackup
    };
})();
