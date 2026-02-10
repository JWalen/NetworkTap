/* NetworkTap - Users Management Page */

const Users = (() => {
    let currentUserRole = 'viewer';

    async function render(container) {
        // Get current user's role
        try {
            const roleData = await api('/api/users/me/role');
            currentUserRole = roleData.role;
        } catch (e) {
            currentUserRole = 'admin'; // Fallback for legacy auth
        }

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

            <div class="card" style="margin-top:20px">
                <div class="card-header">
                    <span class="card-title">Change Password</span>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label class="form-label">Current Password</label>
                        <input type="password" id="old-password" style="width:100%">
                    </div>
                    <div class="form-group">
                        <label class="form-label">New Password</label>
                        <input type="password" id="new-password" style="width:100%">
                    </div>
                </div>
                <button class="btn btn-primary" id="btn-change-password">Change Password</button>
            </div>

            <!-- Add User Modal -->
            <div class="modal" id="add-user-modal" style="display:none">
                <div class="modal-content">
                    <div class="modal-header">
                        <span class="modal-title">Add User</span>
                        <button class="modal-close" id="close-add-modal">&times;</button>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Username</label>
                        <input type="text" id="new-username" style="width:100%" minlength="3">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" id="new-user-password" style="width:100%" minlength="8">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Role</label>
                        <select id="new-user-role" style="width:100%">
                            <option value="viewer">Viewer (read-only)</option>
                            <option value="admin">Admin (full access)</option>
                        </select>
                    </div>
                    <button class="btn btn-primary" id="btn-create-user">Create User</button>
                </div>
            </div>
        `;

        loadUsers();
        setupEventListeners();
    }

    async function loadUsers() {
        const container = document.getElementById('users-list');
        
        if (currentUserRole !== 'admin') {
            container.innerHTML = '<p class="form-help">Only administrators can view the user list.</p>';
            return;
        }

        try {
            const data = await api('/api/users/');
            
            if (data.users.length === 0) {
                container.innerHTML = '<p class="form-help">No users configured. Using config-based authentication.</p>';
                return;
            }

            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Role</th>
                            <th>Enabled</th>
                            <th>Last Login</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.users.map(u => `
                            <tr>
                                <td>${escapeHtml(u.username)}</td>
                                <td><span class="role-badge role-${u.role}">${u.role}</span></td>
                                <td>${u.enabled ? '<span class="status-dot online"></span> Yes' : '<span class="status-dot offline"></span> No'}</td>
                                <td>${u.last_login ? formatDate(u.last_login) : 'Never'}</td>
                                <td>
                                    <button class="btn btn-sm btn-secondary" onclick="Users.toggleUser('${escapeHtml(u.username)}', ${!u.enabled})">${u.enabled ? 'Disable' : 'Enable'}</button>
                                    <button class="btn btn-sm btn-danger" onclick="Users.deleteUser('${escapeHtml(u.username)}')">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            container.innerHTML = `<p class="form-help" style="color:var(--red)">Error loading users: ${escapeHtml(e.message)}</p>`;
        }
    }

    function setupEventListeners() {
        // Add user button
        const addBtn = document.getElementById('btn-add-user');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                document.getElementById('add-user-modal').style.display = 'flex';
            });
        }

        // Close modal
        const closeBtn = document.getElementById('close-add-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                document.getElementById('add-user-modal').style.display = 'none';
            });
        }

        // Create user
        const createBtn = document.getElementById('btn-create-user');
        if (createBtn) {
            createBtn.addEventListener('click', createUser);
        }

        // Change password
        document.getElementById('btn-change-password').addEventListener('click', changePassword);
    }

    async function createUser() {
        const username = document.getElementById('new-username').value.trim();
        const password = document.getElementById('new-user-password').value;
        const role = document.getElementById('new-user-role').value;

        if (!username || username.length < 3) {
            toast('Username must be at least 3 characters', 'error');
            return;
        }

        if (!password || password.length < 8) {
            toast('Password must be at least 8 characters', 'error');
            return;
        }

        try {
            await api('/api/users/', {
                method: 'POST',
                body: { username, password, role }
            });

            toast('User created successfully', 'success');
            document.getElementById('add-user-modal').style.display = 'none';
            document.getElementById('new-username').value = '';
            document.getElementById('new-user-password').value = '';
            loadUsers();
        } catch (e) {
            toast('Failed to create user: ' + e.message, 'error');
        }
    }

    async function toggleUser(username, enabled) {
        try {
            await api(`/api/users/${encodeURIComponent(username)}`, {
                method: 'PUT',
                body: { enabled }
            });

            toast(`User ${enabled ? 'enabled' : 'disabled'}`, 'success');
            loadUsers();
        } catch (e) {
            toast('Failed to update user: ' + e.message, 'error');
        }
    }

    async function deleteUser(username) {
        if (!confirm(`Delete user "${username}"? This cannot be undone.`)) {
            return;
        }

        try {
            await api(`/api/users/${encodeURIComponent(username)}`, {
                method: 'DELETE'
            });

            toast('User deleted', 'success');
            loadUsers();
        } catch (e) {
            toast('Failed to delete user: ' + e.message, 'error');
        }
    }

    async function changePassword() {
        const oldPassword = document.getElementById('old-password').value;
        const newPassword = document.getElementById('new-password').value;

        if (!oldPassword || !newPassword) {
            toast('Both passwords are required', 'error');
            return;
        }

        if (newPassword.length < 8) {
            toast('New password must be at least 8 characters', 'error');
            return;
        }

        try {
            await api('/api/users/change-password', {
                method: 'POST',
                body: { old_password: oldPassword, new_password: newPassword }
            });

            toast('Password changed successfully. Please update your saved credentials.', 'success');
            document.getElementById('old-password').value = '';
            document.getElementById('new-password').value = '';
        } catch (e) {
            toast('Failed to change password: ' + e.message, 'error');
        }
    }

    return { render, toggleUser, deleteUser };
})();
