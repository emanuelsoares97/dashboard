document.addEventListener('DOMContentLoaded', () => {
    const dashboard = document.querySelector('[data-page="dashboard"]');
    if (!dashboard) {
        return;
    }

    dashboard.classList.add('is-ready');

    const sortableTables = document.querySelectorAll('.table-sortable');
    sortableTables.forEach((table) => {
        const headers = table.querySelectorAll('thead th');
        headers.forEach((header, columnIndex) => {
            header.classList.add('is-sortable');
            header.addEventListener('click', () => {
                const currentOrder = header.dataset.sortOrder === 'asc' ? 'asc' : 'desc';
                const nextOrder = currentOrder === 'asc' ? 'desc' : 'asc';

                headers.forEach((item) => {
                    item.removeAttribute('data-sort-order');
                });
                header.dataset.sortOrder = nextOrder;

                const tbody = table.querySelector('tbody');
                if (!tbody) {
                    return;
                }

                const rows = Array.from(tbody.querySelectorAll('tr'));
                const dataRows = rows.filter((row) => !row.querySelector('.table-empty'));

                dataRows.sort((rowA, rowB) => {
                    const cellA = rowA.children[columnIndex]?.textContent?.trim() || '';
                    const cellB = rowB.children[columnIndex]?.textContent?.trim() || '';

                    const numA = Number(cellA.replace('%', '').replace(',', '.'));
                    const numB = Number(cellB.replace('%', '').replace(',', '.'));
                    const isNumeric = !Number.isNaN(numA) && !Number.isNaN(numB);

                    if (isNumeric) {
                        return nextOrder === 'asc' ? numA - numB : numB - numA;
                    }

                    return nextOrder === 'asc'
                        ? cellA.localeCompare(cellB, 'pt-PT')
                        : cellB.localeCompare(cellA, 'pt-PT');
                });

                dataRows.forEach((row) => tbody.appendChild(row));
            });
        });
    });
});
