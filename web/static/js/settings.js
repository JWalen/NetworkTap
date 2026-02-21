/* NetworkTap - Settings View with Users & Backup */

const Settings = (() => {
    const CRED_KEY = 'networktap_creds';
    let currentTab = 'auth';
    let currentUserRole = 'admin';
    let currentConfigSection = 'capture';

    function getCredentials() {
        try {
            const stored = localStorage.getItem(CRED_KEY);
            if (stored) return JSON.parse(stored);
        } catch {}
        return null;
    }

    function hasCredentials() {
        return getCredentials() !== null;
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
            <div class="settings-layout">
                <nav class="settings-nav">
                    <div class="settings-nav-section">Account</div>
                    <button class="settings-nav-item active" data-tab="auth">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        </svg>
                        Authentication
                    </button>
                    <button class="settings-nav-item" data-tab="users">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                            <circle cx="9" cy="7" r="4"/>
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                        </svg>
                        Users
                    </button>

                    <div class="settings-nav-section">Data</div>
                    <button class="settings-nav-item" data-tab="backup">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                        Backup & Restore
                    </button>

                    <div class="settings-nav-section">System</div>
                    <button class="settings-nav-item" data-tab="system">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M18.36 6.64A9 9 0 1 1 5.64 6.64"/>
                            <line x1="12" y1="2" x2="12" y2="12"/>
                        </svg>
                        Power
                    </button>
                    <button class="settings-nav-item" data-tab="config">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <circle cx="12" cy="12" r="3"/>
                            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
                        </svg>
                        Configuration
                    </button>
                </nav>
                <div class="settings-body" id="settings-content"></div>
            </div>
        `;

        container.querySelectorAll('.settings-nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.settings-nav-item').forEach(b => b.classList.remove('active'));
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
            case 'system': renderSystemTab(container); break;
            case 'config': await renderConfigTab(container); break;
        }
    }

    // ── Auth Tab ─────────────────────────────────────────────────

    function renderAuthTab(container) {
        const creds = getCredentials();
        container.innerHTML = `
            <div class="settings-section">
                <h2 class="settings-section-title">Browser Credentials</h2>
                <p class="settings-section-desc">Stored locally in your browser for API authentication.</p>
                <div class="settings-form-row">
                    <div class="form-group">
                        <label class="form-label">Username</label>
                        <input type="text" id="set-user" value="${escapeHtml(creds.user)}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" id="set-pass" value="${escapeHtml(creds.pass)}">
                    </div>
                </div>
                <button class="btn btn-primary" id="btn-save-creds">Save to Browser</button>
            </div>

            <div class="settings-divider"></div>

            <div class="settings-section">
                <h2 class="settings-section-title">Change Server Password</h2>
                <p class="settings-section-desc">Updates the password on the server. Your browser credentials will be updated automatically.</p>
                <div class="settings-form-row">
                    <div class="form-group">
                        <label class="form-label">Current Password</label>
                        <input type="password" id="old-password">
                    </div>
                    <div class="form-group">
                        <label class="form-label">New Password</label>
                        <input type="password" id="new-password">
                    </div>
                </div>
                <button class="btn btn-primary" id="btn-change-password">Change Password</button>
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
                const creds = getCredentials();
                saveCredentials(creds.user, newPass);
            }
        } catch (e) {
            toast('Failed to change password: ' + e.message, 'error');
        }
    }

    // ── Users Tab ────────────────────────────────────────────────

    async function renderUsersTab(container) {
        container.innerHTML = `
            <div class="settings-section">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <div>
                        <h2 class="settings-section-title" style="margin-bottom:0">User Management</h2>
                        <p class="settings-section-desc">Manage who can access the dashboard.</p>
                    </div>
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
                        <tr><th>Username</th><th>Role</th><th>Created</th>${currentUserRole === 'admin' ? '<th style="text-align:right">Actions</th>' : ''}</tr>
                    </thead>
                    <tbody>
                        ${data.users.map(u => `
                            <tr>
                                <td><strong>${escapeHtml(u.username)}</strong></td>
                                <td><span class="role-badge role-${u.role}">${u.role}</span></td>
                                <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}</td>
                                ${currentUserRole === 'admin' ? `
                                    <td style="text-align:right">
                                        <button class="btn btn-sm btn-secondary" onclick="Settings.editUser('${escapeHtml(u.username)}', '${u.role}')">Edit</button>
                                        <button class="btn btn-sm btn-secondary" onclick="Settings.deleteUser('${escapeHtml(u.username)}')" style="color:var(--red)">Delete</button>
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

    // ── Backup Tab ───────────────────────────────────────────────

    async function renderBackupTab(container) {
        container.innerHTML = `
            <div class="settings-section">
                <h2 class="settings-section-title">Create Backup</h2>
                <p class="settings-section-desc">Includes configuration, user accounts, Suricata/Zeek settings, and TLS certificates.</p>
                <div class="settings-form-row">
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Description (optional)</label>
                        <input type="text" id="backup-description" placeholder="e.g., Before upgrade">
                    </div>
                </div>
                <button class="btn btn-primary" id="btn-create-backup">Create & Download</button>
            </div>

            <div class="settings-divider"></div>

            <div class="settings-section">
                <h2 class="settings-section-title">Restore Backup</h2>
                <p class="settings-section-desc">Upload a backup file to restore. A pre-restore backup will be created automatically.</p>
                <div class="settings-form-row">
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Backup File</label>
                        <input type="file" id="backup-file" accept=".tar.gz">
                    </div>
                </div>
                <button class="btn btn-secondary" id="btn-restore-backup">Restore</button>
            </div>

            <div class="settings-divider"></div>

            <div class="settings-section">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <div>
                        <h2 class="settings-section-title" style="margin-bottom:0">Backup History</h2>
                    </div>
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
            const result = await api('/api/backup/', {
                method: 'POST',
                body: { description: desc },
            });

            if (result.success && result.filename) {
                const creds = getCredentials();
                const response = await fetch(`/api/backup/${result.filename}/download`, {
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
            const uploadResp = await fetch('/api/backup/upload', {
                method: 'POST',
                headers: { 'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass) },
                body: formData,
            });
            const uploadResult = await uploadResp.json();
            if (!uploadResult.success || !uploadResult.filename) {
                toast(uploadResult.message || uploadResult.detail || 'Upload failed', 'error');
                return;
            }
            const restoreResp = await fetch(`/api/backup/${encodeURIComponent(uploadResult.filename)}/restore`, {
                method: 'POST',
                headers: { 'Authorization': 'Basic ' + btoa(creds.user + ':' + creds.pass) },
            });
            const result = await restoreResp.json();
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
            const data = await api('/api/backup/');
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
        const response = await fetch(`/api/backup/${encodeURIComponent(filename)}/download`, {
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

    // ── System / Power Tab ────────────────────────────────────────

    function renderSystemTab(container) {
        container.innerHTML = `
            <div class="settings-section">
                <h2 class="settings-section-title">Power Management</h2>
                <p class="settings-section-desc">Reboot the appliance. All active captures will stop and resume after restart.</p>
                <div style="margin-top:16px;">
                    <button class="btn btn-primary" id="btn-reboot" style="background:var(--red);border-color:var(--red);">Reboot Appliance</button>
                </div>
            </div>
        `;

        document.getElementById('btn-reboot').addEventListener('click', async () => {
            if (!confirm('Are you sure you want to reboot the appliance? All active captures will be interrupted.')) return;
            if (!confirm('This will reboot the device immediately. Continue?')) return;

            const btn = document.getElementById('btn-reboot');
            btn.disabled = true;
            btn.textContent = 'Rebooting...';
            try {
                await api('/api/system/reboot', { method: 'POST' });
                toast('Rebooting — the device will be back online shortly', 'success');
            } catch (e) {
                toast('Failed to reboot: ' + e.message, 'error');
                btn.disabled = false;
                btn.textContent = 'Reboot Appliance';
            }
        });
    }

    // ── Config Tab ───────────────────────────────────────────────

    const CONFIG_SECTIONS = [
        { id: 'interfaces', label: 'Interfaces', icon: 'M1 4h22v16H1zM1 10h22' },
        { id: 'capture',  label: 'Capture',    icon: 'M12 2a10 10 0 110 20 10 10 0 010-20zM12 8a4 4 0 110 8 4 4 0 010-8z' },
        { id: 'retention', label: 'Retention',  icon: 'M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2' },
        { id: 'suricata', label: 'Suricata',    icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
        { id: 'zeek',     label: 'Zeek',        icon: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M16 13H8M16 17H8' },
        { id: 'web',      label: 'Web',         icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10A15.3 15.3 0 0112 2z' },
        { id: 'tls',      label: 'TLS',         icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
        { id: 'syslog',   label: 'Syslog',      icon: 'M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z' },
        { id: 'logging',  label: 'Logging',     icon: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6' },
        { id: 'wifi',     label: 'WiFi Capture', icon: 'M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0M12 20h.01' },
        { id: 'display',  label: 'Display',      icon: 'M2 3h20v14H2zM8 21h8M12 17v4' },
        { id: 'ai',       label: 'AI / Anomaly', icon: 'M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z' },
    ];

    function cfgToggle(id, label, value) {
        return `<div class="form-group">
            <label class="form-label">${label}</label>
            <select id="${id}" data-cfg="${id}">
                <option value="true" ${value ? 'selected' : ''}>Enabled</option>
                <option value="false" ${!value ? 'selected' : ''}>Disabled</option>
            </select>
        </div>`;
    }

    function cfgInput(id, label, value, type = 'text', help = '') {
        const h = help ? `<p class="form-help">${help}</p>` : '';
        return `<div class="form-group">
            <label class="form-label">${label}</label>
            <input type="${type}" id="${id}" data-cfg="${id}" value="${escapeHtml(String(value ?? ''))}">
            ${h}
        </div>`;
    }

    function cfgSelect(id, label, value, options) {
        const opts = options.map(o => `<option value="${o}" ${value === o ? 'selected' : ''}>${o}</option>`).join('');
        return `<div class="form-group">
            <label class="form-label">${label}</label>
            <select id="${id}" data-cfg="${id}">${opts}</select>
        </div>`;
    }

    function renderConfigSectionContent(id, c) {
        switch (id) {
            case 'interfaces': return `
                <p class="settings-section-desc">Assign which physical interface is used for capture and management.</p>
                <div class="settings-form-grid">
                    <div class="form-group">
                        <label class="form-label">Capture Interface</label>
                        <select id="nic1" data-cfg="nic1">
                            <option value="${escapeHtml(c.nic1 || '')}">${escapeHtml(c.nic1 || '?')}</option>
                        </select>
                        <p class="form-help">Monitors traffic in promiscuous mode (no IP)</p>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Management Interface</label>
                        <select id="nic2" data-cfg="nic2">
                            <option value="${escapeHtml(c.nic2 || '')}">${escapeHtml(c.nic2 || '?')}</option>
                        </select>
                        <p class="form-help">Provides SSH and web UI access (DHCP or static IP)</p>
                    </div>
                </div>
                <p class="form-help" style="margin-top:8px;">Saving will reconfigure networking. The capture interface will have no IP address and run in promiscuous mode.</p>`;
            case 'capture': return `
                <p class="settings-section-desc">Packet capture settings for tcpdump.</p>
                <div class="settings-form-grid">
                    ${cfgInput('capture_dir', 'Capture Directory', c.capture_dir)}
                    <div class="form-group">
                        <label class="form-label">Capture Interface</label>
                        <select id="capture_iface" data-cfg="capture_iface" class="iface-select">
                            <option value="${escapeHtml(c.capture_iface || 'auto')}">${escapeHtml(c.capture_iface || 'auto')}</option>
                        </select>
                        <p class="form-help">"auto" uses the NIC1 assignment</p>
                    </div>
                    ${cfgInput('capture_rotate_seconds', 'Rotation Interval (sec)', c.capture_rotate_seconds, 'number')}
                    ${cfgInput('capture_file_limit', 'Max Rotated Files', c.capture_file_limit, 'number', '0 = unlimited')}
                    ${cfgInput('capture_snaplen', 'Snap Length', c.capture_snaplen, 'number', '0 = full packet')}
                    ${cfgInput('capture_filter', 'BPF Filter', c.capture_filter, 'text', 'Empty = capture all')}
                    ${cfgToggle('capture_compress', 'Compress Rotated PCAPs', c.capture_compress)}
                </div>`;
            case 'retention': return `
                <p class="settings-section-desc">How long to keep captured data and when to trigger cleanup.</p>
                <div class="settings-form-grid">
                    ${cfgInput('retention_days', 'Retention Days', c.retention_days, 'number')}
                    ${cfgInput('min_free_disk_pct', 'Min Free Disk %', c.min_free_disk_pct, 'number', 'Emergency cleanup threshold')}
                </div>`;
            case 'suricata': return `
                <p class="settings-section-desc">Suricata intrusion detection system.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('suricata_enabled', 'Enabled', c.suricata_enabled)}
                    <div class="form-group">
                        <label class="form-label">Interface</label>
                        <select id="suricata_iface" data-cfg="suricata_iface" class="iface-select">
                            <option value="${escapeHtml(c.suricata_iface || 'auto')}">${escapeHtml(c.suricata_iface || 'auto')}</option>
                        </select>
                        <p class="form-help">"auto" uses the NIC1 assignment</p>
                    </div>
                </div>`;
            case 'zeek': return `
                <p class="settings-section-desc">Zeek network analysis framework.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('zeek_enabled', 'Enabled', c.zeek_enabled)}
                    <div class="form-group">
                        <label class="form-label">Interface</label>
                        <select id="zeek_iface" data-cfg="zeek_iface" class="iface-select">
                            <option value="${escapeHtml(c.zeek_iface || 'auto')}">${escapeHtml(c.zeek_iface || 'auto')}</option>
                        </select>
                        <p class="form-help">"auto" uses the NIC1 assignment</p>
                    </div>
                </div>`;
            case 'web': return `
                <p class="settings-section-desc">Web dashboard server settings.</p>
                <div class="settings-form-grid">
                    ${cfgInput('web_host', 'Listen Host', c.web_host)}
                    ${cfgInput('web_port', 'Listen Port', c.web_port, 'number')}
                </div>`;
            case 'tls': return `
                <p class="settings-section-desc">HTTPS encryption for the web dashboard.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('tls_enabled', 'Enabled', c.tls_enabled)}
                    ${cfgInput('tls_cert', 'Certificate Path', c.tls_cert)}
                    ${cfgInput('tls_key', 'Private Key Path', c.tls_key)}
                </div>`;
            case 'syslog': return `
                <p class="settings-section-desc">Forward alerts and logs to an external syslog server.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('syslog_enabled', 'Enabled', c.syslog_enabled)}
                    ${cfgInput('syslog_server', 'Server', c.syslog_server)}
                    ${cfgInput('syslog_port', 'Port', c.syslog_port, 'number')}
                    ${cfgSelect('syslog_protocol', 'Protocol', c.syslog_protocol, ['udp', 'tcp'])}
                    ${cfgSelect('syslog_format', 'Format', c.syslog_format, ['syslog', 'json'])}
                </div>`;
            case 'logging': return `
                <p class="settings-section-desc">Application logging verbosity.</p>
                <div class="settings-form-grid">
                    ${cfgSelect('log_level', 'Log Level', c.log_level, ['DEBUG', 'INFO', 'WARNING', 'ERROR'])}
                </div>`;
            case 'wifi': return `
                <p class="settings-section-desc">WiFi monitor mode capture settings.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('wifi_capture_enabled', 'Enabled', c.wifi_capture_enabled)}
                    ${cfgSelect('wifi_capture_channel', 'Channel', String(c.wifi_capture_channel || 1), ['1','2','3','4','5','6','7','8','9','10','11','12','13','14'])}
                    ${cfgInput('wifi_capture_max_size_mb', 'Max File Size (MB)', c.wifi_capture_max_size_mb, 'number')}
                    ${cfgInput('wifi_capture_max_files', 'Max Files', c.wifi_capture_max_files, 'number')}
                    ${cfgInput('wifi_capture_filter', 'BPF Filter', c.wifi_capture_filter, 'text', 'Empty = capture all')}
                </div>`;
            case 'display': return `
                <p class="settings-section-desc">FR202 front panel display settings. Changes take effect within 60 seconds (or restart the display service).</p>
                <div class="settings-form-grid">
                    ${cfgToggle('display_enabled', 'Display Enabled', c.display_enabled)}
                    ${cfgInput('display_refresh', 'Refresh Interval (sec)', c.display_refresh, 'number', 'How often the screen redraws (1-60)')}
                    ${cfgInput('display_backlight_timeout', 'Backlight Timeout (sec)', c.display_backlight_timeout, 'number', '0 = never dim, 30-600 recommended')}
                    ${cfgSelect('display_default_page', 'Default Page', c.display_default_page, ['dashboard', 'network', 'services', 'alerts', 'system'])}
                    ${cfgToggle('display_screensaver', 'Screensaver', c.display_screensaver)}
                </div>
                <div class="settings-form-grid" style="margin-top:12px;">
                    <div class="form-group">
                        <label class="form-label">Screensaver Color</label>
                        <div style="display:flex;gap:8px;align-items:center;">
                            <input type="color" id="display_screensaver_color" data-cfg="display_screensaver_color" value="${escapeHtml(c.display_screensaver_color || '#00d4aa')}" style="width:48px;height:36px;padding:2px;border:1px solid var(--border);border-radius:6px;background:var(--bg-secondary);cursor:pointer;">
                            <span id="color-hex-label" style="color:var(--text-secondary);font-family:var(--font-mono);font-size:0.85rem;">${escapeHtml(c.display_screensaver_color || '#00d4aa')}</span>
                        </div>
                        <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;" id="color-presets">
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#00d4aa" style="padding:4px 8px;" title="Teal (default)"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#00d4aa;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#3b82f6" style="padding:4px 8px;" title="Blue"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#3b82f6;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#a855f7" style="padding:4px 8px;" title="Purple"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#a855f7;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#f97316" style="padding:4px 8px;" title="Orange"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#f97316;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#ef4444" style="padding:4px 8px;" title="Red"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ef4444;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#22c55e" style="padding:4px 8px;" title="Green"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#22c55e;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#eab308" style="padding:4px 8px;" title="Yellow"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#eab308;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#ec4899" style="padding:4px 8px;" title="Pink"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ec4899;vertical-align:middle;"></span></button>
                            <button type="button" class="btn btn-sm btn-secondary color-preset" data-color="#ffffff" style="padding:4px 8px;" title="White"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ffffff;border:1px solid var(--border);vertical-align:middle;"></span></button>
                        </div>
                    </div>
                </div>
                <p class="form-help" style="margin-top:8px;">When screensaver is enabled, the display shows a pulsing logo with clock after the backlight timeout. When disabled, the backlight simply turns off.</p>
                <div style="margin-top:12px;">
                    <button class="btn btn-secondary btn-sm" id="btn-restart-display">Restart Display Service</button>
                </div>`;
            case 'ai': return `
                <p class="settings-section-desc">AI assistant and anomaly detection settings.</p>
                <div class="settings-form-grid">
                    ${cfgToggle('anomaly_detection_enabled', 'Anomaly Detection', c.anomaly_detection_enabled)}
                    ${cfgSelect('anomaly_sensitivity', 'Sensitivity', c.anomaly_sensitivity, ['low', 'medium', 'high'])}
                    ${cfgInput('anomaly_interval', 'Check Interval (sec)', c.anomaly_interval, 'number')}
                    ${cfgToggle('ai_assistant_enabled', 'AI Assistant', c.ai_assistant_enabled)}
                    ${cfgInput('ollama_url', 'Ollama URL', c.ollama_url)}
                    ${cfgInput('ollama_model', 'Ollama Model', c.ollama_model)}
                </div>`;
            default: return '';
        }
    }

    async function renderConfigTab(container) {
        let c = {};
        try {
            c = await api('/api/config/');
        } catch {}

        container.innerHTML = `
            <!-- System info banner -->
            <div class="settings-system-info">
                <div class="settings-system-item">
                    <span class="settings-system-label">Mode</span>
                    <span class="settings-system-value">${escapeHtml(c.mode || '?')}</span>
                </div>
                <div class="settings-system-item">
                    <span class="settings-system-label">Capture</span>
                    <span class="settings-system-value">${escapeHtml(c.capture_interface || '?')}</span>
                </div>
                <div class="settings-system-item">
                    <span class="settings-system-label">Mgmt</span>
                    <span class="settings-system-value">${escapeHtml(c.management_interface || '?')}</span>
                </div>
            </div>

            <form id="config-form">
                <div class="config-layout">
                    <nav class="config-nav">
                        ${CONFIG_SECTIONS.map((s, i) => `
                            <button type="button" class="config-nav-item ${i === 0 ? 'active' : ''}" data-section="${s.id}">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                    <path d="${s.icon}"/>
                                </svg>
                                ${s.label}
                            </button>
                        `).join('')}
                    </nav>
                    <div class="config-panel">
                        ${CONFIG_SECTIONS.map((s, i) => `
                            <div class="config-section ${i === 0 ? 'active' : ''}" data-section="${s.id}">
                                <h2 class="settings-section-title">${s.label}</h2>
                                ${renderConfigSectionContent(s.id, c)}
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="config-save-bar">
                    <button type="submit" class="btn btn-primary" id="cfg-save-btn">Save Configuration</button>
                    <span id="cfg-save-status" style="color:var(--text-secondary);font-size:0.85rem;"></span>
                    <p class="form-help" style="margin:0;margin-left:auto;">Some changes require a service restart.</p>
                </div>
            </form>
        `;

        // Config section nav switching
        container.querySelectorAll('.config-nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.config-nav-item').forEach(b => b.classList.remove('active'));
                container.querySelectorAll('.config-section').forEach(s => s.classList.remove('active'));
                btn.classList.add('active');
                container.querySelector(`.config-section[data-section="${btn.dataset.section}"]`).classList.add('active');
                bindSectionButtons();
            });
        });

        function bindSectionButtons() {
            const restartBtn = document.getElementById('btn-restart-display');
            if (restartBtn && !restartBtn.dataset.bound) {
                restartBtn.dataset.bound = '1';
                restartBtn.addEventListener('click', async () => {
                    restartBtn.disabled = true;
                    restartBtn.textContent = 'Restarting...';
                    try {
                        await api('/api/system/service/networktap-display/restart', { method: 'POST' });
                        toast('Display service restarted', 'success');
                    } catch (e) {
                        toast('Failed to restart display: ' + e.message, 'error');
                    } finally {
                        restartBtn.disabled = false;
                        restartBtn.textContent = 'Restart Display Service';
                    }
                });
            }

            // Color picker sync
            const colorInput = document.getElementById('display_screensaver_color');
            const colorLabel = document.getElementById('color-hex-label');
            if (colorInput && !colorInput.dataset.bound) {
                colorInput.dataset.bound = '1';
                colorInput.addEventListener('input', () => {
                    if (colorLabel) colorLabel.textContent = colorInput.value;
                });
            }

            // Color preset buttons
            const presets = document.getElementById('color-presets');
            if (presets && !presets.dataset.bound) {
                presets.dataset.bound = '1';
                presets.querySelectorAll('.color-preset').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const color = btn.dataset.color;
                        if (colorInput) colorInput.value = color;
                        if (colorLabel) colorLabel.textContent = color;
                    });
                });
            }
        }

        // Populate all interface dropdowns with available interfaces
        async function populateIfaceDropdowns() {
            try {
                const data = await api('/api/system/interfaces');
                const ifaces = (data.interfaces || [])
                    .map(i => i.name)
                    .filter(n => n !== 'lo' && !n.startsWith('br'));

                // NIC1/NIC2 selects (no "auto" option)
                for (const id of ['nic1', 'nic2']) {
                    const sel = document.getElementById(id);
                    if (!sel) continue;
                    const current = sel.value;
                    sel.innerHTML = ifaces.map(name =>
                        `<option value="${escapeHtml(name)}" ${name === current ? 'selected' : ''}>${escapeHtml(name)}</option>`
                    ).join('');
                    if (current && !ifaces.includes(current)) {
                        sel.insertAdjacentHTML('afterbegin',
                            `<option value="${escapeHtml(current)}" selected>${escapeHtml(current)}</option>`);
                    }
                }

                // Interface selects with "auto" option (capture, suricata, zeek)
                document.querySelectorAll('.iface-select').forEach(sel => {
                    const current = sel.value;
                    const opts = ['auto', ...ifaces];
                    sel.innerHTML = opts.map(name =>
                        `<option value="${escapeHtml(name)}" ${name === current ? 'selected' : ''}>${escapeHtml(name)}</option>`
                    ).join('');
                    if (current && current !== 'auto' && !ifaces.includes(current)) {
                        sel.insertAdjacentHTML('beforeend',
                            `<option value="${escapeHtml(current)}" selected>${escapeHtml(current)}</option>`);
                    }
                });
            } catch {}
        }
        populateIfaceDropdowns();

        // Track original NIC values to detect changes
        const origNic1 = c.nic1 || '';
        const origNic2 = c.nic2 || '';

        // Save handler
        document.getElementById('config-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('cfg-save-btn');
            const statusEl = document.getElementById('cfg-save-status');

            const body = {};
            document.querySelectorAll('[data-cfg]').forEach(el => {
                const key = el.dataset.cfg;
                let val = el.value;
                if (val === 'true') val = true;
                else if (val === 'false') val = false;
                else if (el.type === 'number' && val !== '') val = Number(val);
                body[key] = val;
            });

            // Warn if NIC assignments changed — this reconfigures networking
            const nicChanged = body.nic1 !== origNic1 || body.nic2 !== origNic2;
            if (nicChanged) {
                if (!confirm('Changing NIC assignments will reconfigure networking (IP addresses, promiscuous mode). This may briefly disconnect you. Continue?')) {
                    return;
                }
            }

            btn.disabled = true;
            btn.textContent = nicChanged ? 'Reconfiguring...' : 'Saving...';
            statusEl.textContent = '';

            try {
                const result = await api('/api/config/', {
                    method: 'PUT',
                    body: body,
                });
                if (result.warning) {
                    toast(result.warning, 'warning');
                }
                if (result.success) {
                    toast(result.message, 'success');
                    statusEl.textContent = 'Saved';
                } else {
                    toast(result.message || 'Save failed', 'error');
                    if (result.errors) statusEl.textContent = result.errors.join('; ');
                }
            } catch (err) {
                toast('Failed to save: ' + err.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Save Configuration';
            }
        });
    }

    return {
        render,
        getCredentials,
        hasCredentials,
        saveCredentials,
        editUser,
        deleteUser,
        closeModal,
        downloadBackup
    };
})();
