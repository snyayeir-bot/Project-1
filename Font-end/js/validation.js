/**
 * validation.js - Form & Data Validation Suite for Project-1
 */

const Validator = {
    /**
     * Check if email is valid according to standard RFC pattern
     * @param {string} email
     * @returns {boolean}
     */
    validateEmail(email) {
        if (!email || typeof email !== 'string') return false;
        const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return re.test(email.trim());
    },

    /**
     * Check if password meets minimum length requirement
     * @param {string} password
     * @param {number} minLength
     * @returns {boolean}
     */
    validatePassword(password, minLength = 6) {
        return Boolean(password && typeof password === 'string' && password.length >= minLength);
    },

    /**
     * Calculate password strength score (0 to 4)
     * 0: Empty/Too short, 1: Weak, 2: Fair, 3: Good, 4: Strong
     * @param {string} password
     * @returns {{ score: number, label: string, color: string, percent: number }}
     */
    getPasswordStrength(password) {
        if (!password) {
            return { score: 0, label: 'None', color: 'transparent', percent: 0 };
        }
        let score = 0;
        if (password.length >= 6) score++;
        if (password.length >= 8) score++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
        if (/[0-9]/.test(password)) score++;
        if (/[^a-zA-Z0-9]/.test(password)) score++;

        // Normalize score between 1 and 4
        const normalized = Math.min(4, Math.max(1, score - (password.length < 6 ? 1 : 0)));

        const tiers = {
            1: { score: 1, label: 'Weak', color: 'var(--color-danger, #ef4444)', percent: 25 },
            2: { score: 2, label: 'Fair', color: 'var(--color-warning, #f59e0b)', percent: 50 },
            3: { score: 3, label: 'Good', color: 'var(--color-info, #3b82f6)', percent: 75 },
            4: { score: 4, label: 'Strong', color: 'var(--color-success, #10b981)', percent: 100 }
        };

        return tiers[normalized] || tiers[1];
    },

    /**
     * Validate phone number format (Cambodian & International formats)
     * @param {string} phone
     * @returns {boolean}
     */
    validatePhone(phone) {
        if (!phone) return false;
        const cleaned = phone.replace(/[\s\-\(\)\.]/g, '');
        return /^(\+?855|0)[1-9][0-9]{7,8}$/.test(cleaned) || /^\+?[1-9]\d{7,14}$/.test(cleaned);
    },

    /**
     * Validate ISO or display Date string
     * @param {string} dateStr
     * @returns {boolean}
     */
    validateDate(dateStr) {
        if (!dateStr) return false;
        const d = new Date(dateStr);
        return !isNaN(d.getTime());
    },

    /**
     * Validate required non-empty field
     * @param {any} value
     * @returns {boolean}
     */
    validateRequired(value) {
        if (value === null || value === undefined) return false;
        if (typeof value === 'string') return value.trim().length > 0;
        return true;
    },

    /**
     * Validate Student / Teacher ID format (e.g. STD-2026-001, TCH-2026-001)
     * @param {string} id
     * @returns {boolean}
     */
    validateID(id) {
        if (!id) return false;
        return /^(STD|TCH|CLS|SUB|EXM)-\d{4}-\d{3,}$/i.test(id.trim()) || id.trim().length >= 3;
    },

    /**
     * Attach real-time validation handler to a form input
     * @param {HTMLInputElement} inputEl
     * @param {Function} validatorFn
     * @param {HTMLElement} errorEl
     * @param {string} errorMessage
     */
    bindInputValidation(inputEl, validatorFn, errorEl, errorMessage) {
        if (!inputEl) return;
        const validate = () => {
            const isValid = validatorFn(inputEl.value);
            if (!isValid && inputEl.value.trim().length > 0) {
                inputEl.classList.add('is-invalid');
                inputEl.classList.remove('is-valid');
                if (errorEl) {
                    errorEl.textContent = errorMessage;
                    errorEl.classList.add('show');
                }
            } else if (isValid) {
                inputEl.classList.remove('is-invalid');
                inputEl.classList.add('is-valid');
                if (errorEl) {
                    errorEl.classList.remove('show');
                }
            } else {
                inputEl.classList.remove('is-invalid', 'is-valid');
                if (errorEl) errorEl.classList.remove('show');
            }
            return isValid;
        };

        inputEl.addEventListener('input', validate);
        inputEl.addEventListener('blur', validate);
        return validate;
    }
};

// Expose globally
window.Validator = Validator;
window.validateEmail = Validator.validateEmail;
window.validatePassword = Validator.validatePassword;
window.getPasswordStrength = Validator.getPasswordStrength;
window.validatePhone = Validator.validatePhone;
window.validateDate = Validator.validateDate;
window.validateRequired = Validator.validateRequired;
