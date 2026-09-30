/**
 * format.js - Data Formatting Utilities (Date, Currency, Text)
 */

const Formatter = {
    /**
     * Format a date string into readable format (e.g. DD/MM/YYYY, YYYY-MM-DD, Month DD, YYYY)
     * @param {string|Date} dateVal
     * @param {string} format
     * @returns {string}
     */
    formatDate(dateVal, format = 'DD/MM/YYYY') {
        if (!dateVal) return '-';
        const d = new Date(dateVal);
        if (isNaN(d.getTime())) return String(dateVal);

        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        if (format === 'DD/MM/YYYY') return `${day}/${month}/${year}`;
        if (format === 'YYYY-MM-DD') return `${year}-${month}-${day}`;
        if (format === 'MM/DD/YYYY') return `${month}/${day}/${year}`;
        if (format === 'readable') return `${monthNames[d.getMonth()]} ${day}, ${year}`;

        return `${day}/${month}/${year}`;
    },

    /**
     * Format time to 12-hour AM/PM format
     * @param {string|Date} dateVal
     * @returns {string}
     */
    formatTime(dateVal) {
        if (!dateVal) return '-';
        const d = new Date(dateVal);
        if (isNaN(d.getTime())) return String(dateVal);

        let hours = d.getHours();
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12; // hour '0' should be '12'
        return `${String(hours).padStart(2, '0')}:${minutes} ${ampm}`;
    },

    /**
     * Format currency (default USD $)
     * @param {number|string} amount
     * @param {string} currency
     * @returns {string}
     */
    formatCurrency(amount, currency = 'USD') {
        const num = parseFloat(amount);
        if (isNaN(num)) return '$0.00';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2
        }).format(num);
    },

    /**
     * Capitalize first letter of each word
     * @param {string} str
     * @returns {string}
     */
    capitalizeString(str) {
        if (!str || typeof str !== 'string') return '';
        return str.toLowerCase().replace(/\b\w/g, char => char.toUpperCase());
    }
};

// Global shortcuts
window.Formatter = Formatter;
window.formatDate = Formatter.formatDate;
window.formatTime = Formatter.formatTime;
window.formatCurrency = Formatter.formatCurrency;
window.capitalizeString = Formatter.capitalizeString;
