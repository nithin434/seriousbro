/**
 * Authentication Management Module
 * Handles token storage, refresh, and session management
 */
class AuthManager {
    constructor() {
        this.ACCESS_TOKEN_KEY = 'syntexa_access_token';
        this.REFRESH_TOKEN_KEY = 'syntexa_refresh_token';
        this.USER_DATA_KEY = 'syntexa_user_data';
        this.refreshPromise = null;
        this.isRefreshing = false;
    }

    /**
     * Store authentication tokens and user data
     */
    storeAuth(accessToken, refreshToken, userData) {
        localStorage.setItem(this.ACCESS_TOKEN_KEY, accessToken);
        localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
        localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(userData));
        
        // Also store in cookies for better session management
        this.setCookie(this.ACCESS_TOKEN_KEY, accessToken, 1); // 1 hour
        this.setCookie(this.REFRESH_TOKEN_KEY, refreshToken, 30); // 30 days
    }

    /**
     * Get access token
     */
    getAccessToken() {
        return localStorage.getItem(this.ACCESS_TOKEN_KEY) || this.getCookie(this.ACCESS_TOKEN_KEY);
    }

    /**
     * Get refresh token
     */
    getRefreshToken() {
        return localStorage.getItem(this.REFRESH_TOKEN_KEY) || this.getCookie(this.REFRESH_TOKEN_KEY);
    }

    /**
     * Get user data
     */
    getUserData() {
        const userData = localStorage.getItem(this.USER_DATA_KEY);
        return userData ? JSON.parse(userData) : null;
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.getAccessToken();
    }

    /**
     * Clear all authentication data
     */
    clearAuth() {
        localStorage.removeItem(this.ACCESS_TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
        localStorage.removeItem(this.USER_DATA_KEY);
        
        // Clear cookies
        this.deleteCookie(this.ACCESS_TOKEN_KEY);
        this.deleteCookie(this.REFRESH_TOKEN_KEY);
    }

    /**
     * Refresh access token
     */
    async refreshToken() {
        // Prevent multiple simultaneous refresh attempts
        if (this.isRefreshing) {
            return this.refreshPromise;
        }

        this.isRefreshing = true;
        
        this.refreshPromise = new Promise(async (resolve, reject) => {
            try {
                const refreshToken = this.getRefreshToken();
                
                if (!refreshToken) {
                    throw new Error('No refresh token available');
                }

                const response = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        refresh_token: refreshToken
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // Update stored tokens
                    localStorage.setItem(this.ACCESS_TOKEN_KEY, data.access_token);
                    this.setCookie(this.ACCESS_TOKEN_KEY, data.access_token, 1);
                    
                    resolve(data.access_token);
                } else {
                    throw new Error(data.error || 'Token refresh failed');
                }
            } catch (error) {
                console.error('Token refresh failed:', error);
                this.clearAuth();
                reject(error);
            } finally {
                this.isRefreshing = false;
                this.refreshPromise = null;
            }
        });

        return this.refreshPromise;
    }

    /**
     * Make authenticated HTTP request with automatic token refresh
     */
    async authFetch(url, options = {}) {
        const makeRequest = async (token) => {
            const headers = {
                ...options.headers
            };

            // Only set Content-Type to application/json if it's not FormData
            if (!(options.body instanceof FormData) && !headers['Content-Type']) {
                headers['Content-Type'] = 'application/json';
            }

            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            return fetch(url, {
                ...options,
                headers
            });
        };

        try {
            let accessToken = this.getAccessToken();
            
            if (!accessToken) {
                throw new Error('No access token available');
            }

            let response = await makeRequest(accessToken);

            // If token expired, try to refresh
            if (response.status === 401) {
                const responseData = await response.json();
                
                if (responseData.requires_refresh) {
                    try {
                        accessToken = await this.refreshToken();
                        response = await makeRequest(accessToken);
                    } catch (refreshError) {
                        console.error('Token refresh failed:', refreshError);
                        this.redirectToLogin();
                        throw refreshError;
                    }
                } else {
                    this.redirectToLogin();
                    throw new Error('Authentication failed');
                }
            }

            return response;
        } catch (error) {
            console.error('Auth fetch failed:', error);
            throw error;
        }
    }

    /**
     * Logout user
     */
    async logout() {
        try {
            const accessToken = this.getAccessToken();
            
            if (accessToken) {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${accessToken}`,
                        'Content-Type': 'application/json'
                    }
                });
            }
        } catch (error) {
            console.error('Logout API call failed:', error);
        } finally {
            this.clearAuth();
            this.redirectToLogin();
        }
    }

    /**
     * Redirect to login page
     */
    redirectToLogin() {
        const currentPath = window.location.pathname;
        
        // Don't redirect if already on login or signup page
        if (currentPath === '/login' || currentPath === '/signup') {
            return;
        }
        
        // Store current path for redirect after login
        sessionStorage.setItem('redirect_after_login', window.location.href);
        window.location.href = '/login';
    }

    /**
     * Redirect after successful login
     */
    redirectAfterLogin() {
        const redirectUrl = sessionStorage.getItem('redirect_after_login');
        sessionStorage.removeItem('redirect_after_login');
        
        if (redirectUrl && !redirectUrl.includes('/login') && !redirectUrl.includes('/signup')) {
            window.location.href = redirectUrl;
        } else {
            // Default redirect to upload page for new users
            window.location.href = '/upload';
        }
    }

    /**
     * Set cookie
     */
    setCookie(name, value, hours) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (hours * 60 * 60 * 1000));
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
    }

    /**
     * Get cookie
     */
    getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    /**
     * Delete cookie
     */
    deleteCookie(name) {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    }

    /**
     * Check if token is expired (client-side check)
     */
    isTokenExpired(token) {
        if (!token) return true;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const now = Date.now() / 1000;
            return payload.exp < now;
        } catch (error) {
            return true;
        }
    }

    /**
     * Initialize authentication state
     */
    async init() {
        const accessToken = this.getAccessToken();
        
        if (accessToken && this.isTokenExpired(accessToken)) {
            try {
                await this.refreshToken();
            } catch (error) {
                console.error('Initial token refresh failed:', error);
                this.clearAuth();
            }
        }
    }
}

// Global auth manager instance
const authManager = new AuthManager();

// Global authFetch function for backwards compatibility
window.authFetch = authManager.authFetch.bind(authManager);

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await authManager.init();
});

// Export for use in other modules
window.authManager = authManager;
