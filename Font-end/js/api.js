/**
 * api.js - Centralized Asynchronous API Client with Toast Error Handling
 */

const ApiClient = {
    /**
     * General Fetch Helper
     * @param {string} endpoint
     * @param {RequestInit} options
     * @returns {Promise<any>}
     */
    async request(endpoint, options = {}) {
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };

        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...(options.headers || {})
            }
        };

        try {
            const response = await fetch(endpoint, config);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const errorMsg = data.error || data.message || `Request failed with status ${response.status}`;
                throw new Error(errorMsg);
            }

            return data;
        } catch (error) {
            this.handleError(error);
            throw error;
        }
    },

    /**
     * GET request
     * @param {string} endpoint
     * @param {Object} params
     */
    async get(endpoint, params = null) {
        let url = endpoint;
        if (params) {
            const searchParams = new URLSearchParams();
            Object.keys(params).forEach(key => {
                if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                    searchParams.append(key, params[key]);
                }
            });
            const queryString = searchParams.toString();
            if (queryString) {
                url += (url.includes('?') ? '&' : '?') + queryString;
            }
        }
        return this.request(url, { method: 'GET' });
    },

    /**
     * POST request
     * @param {string} endpoint
     * @param {any} data
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT request
     * @param {string} endpoint
     * @param {any} data
     */
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE request
     * @param {string} endpoint
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    /**
     * Global Error Handler
     * @param {Error} error
     */
    handleError(error) {
        console.error('[API Error]:', error);
        if (window.showToast) {
            window.showToast(error.message || 'An unexpected error occurred.', 'danger', 4000, 'API Error');
        }
    }
};

// Global shortcuts
window.ApiClient = ApiClient;
window.fetchFromAPI = (endpoint, options) => ApiClient.request(endpoint, options);
window.postToAPI = (endpoint, data) => ApiClient.post(endpoint, data);
window.putToAPI = (endpoint, data) => ApiClient.put(endpoint, data);
window.deleteFromAPI = (endpoint) => ApiClient.delete(endpoint);
window.handleAPIError = (err) => ApiClient.handleError(err);
