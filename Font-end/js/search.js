/**
 * search.js - Real-time Search, Multi-criteria Filtering & Sorting Suite
 */

const SearchManager = {
    /**
     * Search an array of objects by keyword across specific fields
     * @param {Array<Object>} data
     * @param {string} query
     * @param {Array<string>} fields
     * @returns {Array<Object>}
     */
    searchData(data, query, fields = []) {
        if (!data || !Array.isArray(data)) return [];
        if (!query || query.trim() === '') return data;

        const cleanQuery = query.toLowerCase().trim();

        return data.filter(item => {
            if (!fields || fields.length === 0) {
                // Search all string/number fields by default
                return Object.values(item).some(val => 
                    val !== null && val !== undefined && String(val).toLowerCase().includes(cleanQuery)
                );
            }

            return fields.some(field => {
                const val = item[field];
                return val !== null && val !== undefined && String(val).toLowerCase().includes(cleanQuery);
            });
        });
    },

    /**
     * Filter items by exact or matched status
     * @param {Array<Object>} data
     * @param {string} status
     * @param {string} statusField
     * @returns {Array<Object>}
     */
    filterByStatus(data, status, statusField = 'status') {
        if (!data || !Array.isArray(data)) return [];
        if (!status || status === 'All' || status === 'all' || status === '') return data;

        const target = String(status).toLowerCase();
        return data.filter(item => {
            const val = item[statusField];
            return val && String(val).toLowerCase() === target;
        });
    },

    /**
     * Filter records by Date range
     * @param {Array<Object>} data
     * @param {string|Date} startDate
     * @param {string|Date} endDate
     * @param {string} dateField
     * @returns {Array<Object>}
     */
    filterByDateRange(data, startDate, endDate, dateField = 'date') {
        if (!data || !Array.isArray(data)) return [];
        if (!startDate && !endDate) return data;

        const start = startDate ? new Date(startDate).getTime() : 0;
        const end = endDate ? new Date(endDate).getTime() : Infinity;

        return data.filter(item => {
            const itemDate = new Date(item[dateField]).getTime();
            if (isNaN(itemDate)) return true;
            return itemDate >= start && itemDate <= end;
        });
    },

    /**
     * Sort array of objects by field in ascending or descending order
     * @param {Array<Object>} data
     * @param {string} field
     * @param {'asc'|'desc'} order
     * @returns {Array<Object>}
     */
    sortData(data, field, order = 'asc') {
        if (!data || !Array.isArray(data)) return [];
        if (!field) return data;

        return [...data].sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            // Normalize numbers if applicable
            if (typeof valA === 'number' && typeof valB === 'number') {
                return order === 'asc' ? valA - valB : valB - valA;
            }

            // String comparison
            valA = valA !== null && valA !== undefined ? String(valA).toLowerCase() : '';
            valB = valB !== null && valB !== undefined ? String(valB).toLowerCase() : '';

            if (valA < valB) return order === 'asc' ? -1 : 1;
            if (valA > valB) return order === 'asc' ? 1 : -1;
            return 0;
        });
    }
};

// Global Exposure
window.SearchManager = SearchManager;
window.searchData = SearchManager.searchData;
window.filterByStatus = SearchManager.filterByStatus;
window.filterByDateRange = SearchManager.filterByDateRange;
window.sortData = SearchManager.sortData;
