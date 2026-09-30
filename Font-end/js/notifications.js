/**
 * notifications.js - Custom Toast and Alert Feedback Suite
 */

const Notifications = {
    _container: null,

    getContainer() {
        if (!this._container || !document.body.contains(this._container)) {
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                document.body.appendChild(container);
            }
            this._container = container;
        }
        return this._container;
    },

    /**
     * Show modern floating toast
     * @param {string} message
     * @param {'success'|'danger'|'warning'|'info'|'gold'} type
     * @param {number} duration
     * @param {string} title
     */
    showToast(message, type = 'info', duration = 3500, title = '') {
        const container = this.getContainer();
        const toast = document.createElement('div');
        toast.className = `custom-toast toast-${type}`;

        const icons = {
            success: 'bi-check-circle-fill',
            danger: 'bi-exclamation-triangle-fill',
            warning: 'bi-exclamation-circle-fill',
            info: 'bi-info-circle-fill',
            gold: 'bi-stars'
        };

        const defaultTitles = {
            success: 'Success',
            danger: 'Error',
            warning: 'Notice',
            info: 'Information',
            gold: 'System'
        };

        const toastTitle = title || defaultTitles[type] || 'Notice';
        const iconClass = icons[type] || icons.info;

        toast.innerHTML = `
            <i class="bi ${iconClass} custom-toast-icon"></i>
            <div class="custom-toast-body">
                <div class="custom-toast-title">${toastTitle}</div>
                <div class="custom-toast-message">${message}</div>
            </div>
            <button type="button" class="btn-close btn-close-white ms-auto" style="font-size: 0.65rem;" aria-label="Close"></button>
        `;

        const closeBtn = toast.querySelector('.btn-close');
        const removeToast = () => {
            toast.classList.add('hide');
            setTimeout(() => {
                if (toast.parentNode) toast.remove();
            }, 250);
        };

        closeBtn.addEventListener('click', removeToast);
        container.appendChild(toast);

        if (duration > 0) {
            setTimeout(removeToast, duration);
        }

        return toast;
    },

    /**
     * Toggle button loading spinner state
     * @param {HTMLElement|string} button
     * @param {boolean} isLoading
     * @param {string} loadingText
     */
    showLoadingSpinner(button, isLoading, loadingText = 'Processing...') {
        const btn = typeof button === 'string' ? document.querySelector(button) : button;
        if (!btn) return;

        if (isLoading) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                <span>${loadingText}</span>
            `;
        } else {
            btn.disabled = false;
            if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
            }
        }
    }
};

// Global shortcuts
window.Notifications = Notifications;
window.showToast = (msg, type = 'info', duration = 3500, title = '') => Notifications.showToast(msg, type, duration, title);
window.showLoadingSpinner = (btn, isLoading, text) => Notifications.showLoadingSpinner(btn, isLoading, text);
