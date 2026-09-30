/**
 * pagination.js - Client-Side Table & List Pagination Manager
 */

class PaginationManager {
    /**
     * @param {Object} options
     * @param {Array} options.data
     * @param {number} options.pageSize
     * @param {Function} options.onPageChange - callback receiving (pageData, state)
     * @param {HTMLElement|string} options.container - container for pagination buttons
     */
    constructor(options = {}) {
        this.data = options.data || [];
        this.pageSize = options.pageSize || 10;
        this.currentPage = 1;
        this.onPageChange = options.onPageChange || (() => {});
        this.container = typeof options.container === 'string' ? document.querySelector(options.container) : options.container;
        
        this.init();
    }

    setData(newData) {
        this.data = newData || [];
        this.currentPage = 1;
        this.render();
    }

    getTotalPages() {
        return Math.max(1, Math.ceil(this.data.length / this.pageSize));
    }

    getCurrentPageData() {
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        return this.data.slice(start, end);
    }

    goToPage(page) {
        const total = this.getTotalPages();
        if (page < 1) page = 1;
        if (page > total) page = total;
        this.currentPage = page;
        this.render();
    }

    nextPage() {
        if (this.currentPage < this.getTotalPages()) {
            this.goToPage(this.currentPage + 1);
        }
    }

    prevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    }

    render() {
        const pageData = this.getCurrentPageData();
        const state = {
            currentPage: this.currentPage,
            totalPages: this.getTotalPages(),
            totalItems: this.data.length,
            pageSize: this.pageSize,
            startItem: this.data.length === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1,
            endItem: Math.min(this.currentPage * this.pageSize, this.data.length)
        };

        // Trigger user callback
        this.onPageChange(pageData, state);

        // Render UI Controls
        if (this.container) {
            this.renderControls(state);
        }
    }

    renderControls(state) {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="pagination-wrapper">
                <div class="pagination-info">
                    Showing <span class="fw-semibold text-white">${state.startItem}</span> to 
                    <span class="fw-semibold text-white">${state.endItem}</span> of 
                    <span class="fw-semibold text-white">${state.totalItems}</span> entries
                </div>
                <div class="pagination-controls">
                    <button class="pagination-btn" id="pagination-first" ${state.currentPage === 1 ? 'disabled' : ''} title="First Page">
                        <i class="bi bi-chevron-double-left"></i>
                    </button>
                    <button class="pagination-btn" id="pagination-prev" ${state.currentPage === 1 ? 'disabled' : ''} title="Previous Page">
                        <i class="bi bi-chevron-left"></i> Previous
                    </button>
                    <div class="d-none d-md-flex align-items-center gap-1">
                        ${this._buildPageNumberButtons(state)}
                    </div>
                    <button class="pagination-btn" id="pagination-next" ${state.currentPage === state.totalPages ? 'disabled' : ''} title="Next Page">
                        Next <i class="bi bi-chevron-right"></i>
                    </button>
                    <button class="pagination-btn" id="pagination-last" ${state.currentPage === state.totalPages ? 'disabled' : ''} title="Last Page">
                        <i class="bi bi-chevron-double-right"></i>
                    </button>
                </div>
            </div>
        `;

        // Attach event listeners
        this.container.querySelector('#pagination-first')?.addEventListener('click', () => this.goToPage(1));
        this.container.querySelector('#pagination-prev')?.addEventListener('click', () => this.prevPage());
        this.container.querySelector('#pagination-next')?.addEventListener('click', () => this.nextPage());
        this.container.querySelector('#pagination-last')?.addEventListener('click', () => this.goToPage(state.totalPages));

        this.container.querySelectorAll('[data-page-num]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const pageNum = parseInt(e.currentTarget.dataset.pageNum, 10);
                if (pageNum) this.goToPage(pageNum);
            });
        });
    }

    _buildPageNumberButtons(state) {
        let buttonsHtml = '';
        const maxVisible = 5;
        let startPage = Math.max(1, state.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(state.totalPages, startPage + maxVisible - 1);

        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === state.currentPage ? 'active' : '';
            buttonsHtml += `<button class="pagination-btn ${activeClass}" data-page-num="${i}">${i}</button>`;
        }
        return buttonsHtml;
    }

    init() {
        this.render();
    }
}

// Global exposure
window.PaginationManager = PaginationManager;
window.paginate = (data, pageSize = 10) => {
    return data.slice(0, pageSize);
};
