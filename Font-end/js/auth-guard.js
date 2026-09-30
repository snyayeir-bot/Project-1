/**
 * auth-guard.js
 * Universal Client-Side Authentication & Role Verification Guard
 * Enforces JWT Token validation and strict Role-Based Access Control (RBAC)
 */

(function (window) {
    const AuthGuard = {
        /**
         * Get the stored JWT token
         */
        getToken() {
            return localStorage.getItem('auth_token') || localStorage.getItem('token') || '';
        },

        /**
         * Get the stored user object
         */
        getCurrentUser() {
            try {
                const userStr = localStorage.getItem('user');
                return userStr ? JSON.parse(userStr) : null;
            } catch (e) {
                return null;
            }
        },

        /**
         * Clear auth state and redirect to login immediately
         */
        logout(reason = null) {
            const token = this.getToken();
            if (token) {
                try {
                    fetch('/api/logout', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    }).catch(() => {});
                } catch (e) {}
            }

            // Clear all credentials synchronously
            try {
                localStorage.removeItem('auth_token');
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                sessionStorage.clear();
            } catch (e) {}

            if (reason) {
                console.warn('[AuthGuard]', reason);
            }

            // Immediate redirect to login
            window.location.replace('/');
        },

        /**
         * Check authentication and verify role against required role(s)
         * @param {Object} options - { requiredRole: 'Admin' | 'Teacher' | ['Admin', 'Teacher'] }
         */
        async checkAuth(options = {}) {
            const requiredRoles = Array.isArray(options.requiredRole)
                ? options.requiredRole
                : options.requiredRole
                    ? [options.requiredRole]
                    : [];

            const token = this.getToken();

            // 1. If no token is found, redirect immediately to login
            if (!token) {
                console.warn('[AuthGuard] No token found. Redirecting to login...');
                this.logout('No authentication token found.');
                return false;
            }

            // Immediately apply cached user info if present
            const cachedUser = this.getCurrentUser();
            if (cachedUser) {
                this.updateUIWithUserInfo(cachedUser);
            }

            try {
                // 2. Call backend /api/verify_token to validate token & role
                const rolesParam = requiredRoles.join(',');
                const verifyUrl = `/api/verify_token${rolesParam ? `?required_role=${encodeURIComponent(rolesParam)}` : ''}`;

                const response = await fetch(verifyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ token: token, required_role: rolesParam })
                });

                const data = await response.json();

                if (!response.ok || data.status !== 'success') {
                    // Token invalid or role mismatch
                    if (response.status === 403) {
                        // Role mismatch (e.g. Teacher trying to access Admin portal)
                        const userRole = data.user?.role || '';
                        alert(`⚠️ ការចូលដំណើរការត្រូវបានកំណត់ (Access Restricted)!\nគណនីរបស់អ្នកមានតួនាទីជា "${userRole}" ប៉ុន្តែទំព័រនេះទាមទារសិទ្ធិជា "${requiredRoles.join(' ឬ ')}"។`);
                        
                        // Redirect to the appropriate portal according to their actual role
                        if (userRole.toLowerCase() === 'teacher') {
                            window.location.href = '/teachers-desbord';
                        } else if (userRole.toLowerCase() === 'admin') {
                            window.location.href = '/admin-desbord';
                        } else {
                            this.logout('Unauthorized role');
                        }
                        return false;
                    } else {
                        // Token expired or invalid
                        console.warn('[AuthGuard] Token verification failed:', data.message);
                        alert(data.message || 'Session expired. Please log in again.');
                        this.logout('Session expired or invalid token');
                        return false;
                    }
                }

                // 3. Update localStorage user info with fresh data from server
                if (data.user) {
                    localStorage.setItem('user', JSON.stringify(data.user));
                    this.updateUIWithUserInfo(data.user);
                }

                return true;
            } catch (err) {
                console.error('[AuthGuard] Network error verifying token:', err);
                // Fallback to local user validation if offline/error
                const localUser = this.getCurrentUser();
                if (!localUser) {
                    this.logout('Failed to verify token');
                    return false;
                }
                this.updateUIWithUserInfo(localUser);
                return true;
            }
        },

        /**
         * Update username, role badges, and bind logout buttons on the page
         */
        updateUIWithUserInfo(user) {
            if (!user) return;

            const applyUI = () => {
                const displayName = user.username || user.name || 'Admin User';
                const displayRole = user.role || 'Admin';

                // Update user name in elements with auth-user-name or common identifiers
                const nameElems = document.querySelectorAll('.auth-user-name, #sidebar-user-name, #topbar-user-name, #current-user-name, #admin-user-name, .profile-pill .fw-bold, [data-user-name]');
                nameElems.forEach(el => {
                    if (el && !el.classList.contains('no-auth-override')) {
                        el.textContent = displayName;
                    }
                });

                // Update role badge in elements
                const roleElems = document.querySelectorAll('.auth-user-role, #sidebar-user-role, #topbar-user-role, #current-user-role, #admin-user-role, [data-user-role]');
                roleElems.forEach(el => {
                    if (el) {
                        el.textContent = displayRole;
                    }
                });

                this.bindLogoutButtons();
            };

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', applyUI);
            } else {
                applyUI();
            }
        },

        /**
         * Bind click handlers to all logout buttons
         */
        bindLogoutButtons() {
            const logoutBtns = document.querySelectorAll('.btn-signout, .btn-logout, [data-action="logout"]');
            logoutBtns.forEach(btn => {
                btn.onclick = (e) => {
                    if (e) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                    AuthGuard.logout();
                };
            });
        }
    };

    // Auto-bind on DOMContentLoaded and apply cached user
    if (typeof document !== 'undefined') {
        const onDomReady = () => {
            const user = AuthGuard.getCurrentUser();
            if (user) {
                AuthGuard.updateUIWithUserInfo(user);
            }
            AuthGuard.bindLogoutButtons();
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', onDomReady);
        } else {
            onDomReady();
        }
    }

    // Expose globally
    window.AuthGuard = AuthGuard;
    window.checkAuth = AuthGuard.checkAuth.bind(AuthGuard);
    window.logout = function () {
        AuthGuard.logout();
    };

})(window);
