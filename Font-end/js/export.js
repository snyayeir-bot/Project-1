/**
 * export.js - Client-Side Data Exporting Suite (CSV, Table Export, Print)
 */

const ExportManager = {
    /**
     * Export JSON array to CSV and trigger instant download
     * @param {Array<Object>} data
     * @param {string} filename
     * @param {Array<{ key: string, label: string }>} columns
     */
    exportToCSV(data, filename = 'export.csv', columns = null) {
        if (!data || !data.length) {
            if (window.showToast) window.showToast('No data available to export.', 'warning');
            return;
        }

        const keys = columns ? columns.map(c => c.key) : Object.keys(data[0]);
        const headers = columns ? columns.map(c => c.label) : keys;

        const csvRows = [];
        // Add header row
        csvRows.push(headers.map(h => `"${String(h).replace(/"/g, '""')}"`).join(','));

        // Add data rows
        for (const row of data) {
            const values = keys.map(k => {
                const val = row[k] !== null && row[k] !== undefined ? row[k] : '';
                return `"${String(val).replace(/"/g, '""')}"`;
            });
            csvRows.push(values.join(','));
        }

        const csvString = '\uFEFF' + csvRows.join('\r\n'); // Add BOM for Excel UTF-8 support
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        if (window.showToast) {
            window.showToast(`Exported "${filename}" successfully!`, 'success');
        }
    },

    /**
     * Export HTML Table element directly to CSV
     * @param {string|HTMLTableElement} tableSelector
     * @param {string} filename
     */
    exportTableToCSV(tableSelector, filename = 'table_export.csv') {
        const table = typeof tableSelector === 'string' ? document.querySelector(tableSelector) : tableSelector;
        if (!table) return;

        const rows = Array.from(table.querySelectorAll('tr'));
        const csvContent = rows.map(row => {
            const cols = Array.from(row.querySelectorAll('th, td'));
            return cols.map(c => `"${c.innerText.trim().replace(/"/g, '""')}"`).join(',');
        }).join('\r\n');

        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * Open dedicated clean print dialog for specific DOM element
     * @param {string|HTMLElement} elementSelector
     * @param {string} title
     */
    printData(elementSelector, title = 'Report') {
        const target = typeof elementSelector === 'string' ? document.querySelector(elementSelector) : elementSelector;
        if (!target) return;

        const printWindow = window.open('', '_blank', 'height=700,width=900');
        if (!printWindow) return;

        printWindow.document.write(`
            <html>
                <head>
                    <title>${title}</title>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
                    <style>
                        body { background: #fff; color: #000; padding: 20px; font-family: sans-serif; }
                        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
                        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
                        th { background-color: #f2f2f2; }
                    </style>
                </head>
                <body>
                    <h2 class="mb-3">${title}</h2>
                    <div>${target.outerHTML}</div>
                    <script>
                        window.onload = function() {
                            window.print();
                            window.close();
                        };
                    </script>
                </body>
            </html>
        `);
        printWindow.document.close();
    }
};

// Global shortcuts
window.ExportManager = ExportManager;
window.exportToCSV = ExportManager.exportToCSV;
window.exportTableToCSV = ExportManager.exportTableToCSV;
window.printData = ExportManager.printData;
