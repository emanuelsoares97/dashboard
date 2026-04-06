document.addEventListener('DOMContentLoaded', () => {
    const dashboard = document.querySelector('[data-page="dashboard"]');
    if (!dashboard) {
        return;
    }

    dashboard.classList.add('is-ready');

    const payloadNode = document.getElementById('dashboard-data');
    const payload = payloadNode ? JSON.parse(payloadNode.textContent) : null;

    const presetField = document.getElementById('date_preset');
    const startDateField = document.getElementById('start_date');
    const endDateField = document.getElementById('end_date');

    const syncDateInputs = () => {
        const isCustom = !presetField || presetField.value === 'custom';
        [startDateField, endDateField].forEach((field) => {
            if (!field) {
                return;
            }
            field.disabled = !isCustom;
        });
    };

    if (presetField) {
        presetField.addEventListener('change', syncDateInputs);
        syncDateInputs();
    }

    const chartDefaults = {
        plugins: {
            legend: {
                labels: {
                    color: '#374151',
                    boxWidth: 12,
                },
            },
            tooltip: {
                backgroundColor: '#111827',
                titleColor: '#ffffff',
                bodyColor: '#ffffff',
            },
        },
        maintainAspectRatio: false,
        responsive: true,
    };

    const markChartReady = (canvasId) => {
        const canvas = document.getElementById(canvasId);
        const shell = canvas?.closest('.chart-shell');
        if (shell) {
            shell.classList.remove('has-message');
            shell.classList.add('is-ready');
        }
        if (canvas) {
            canvas.style.display = '';
        }
        return canvas;
    };

    const showChartMessage = (canvasId, message) => {
        const canvas = document.getElementById(canvasId);
        const shell = canvas?.closest('.chart-shell');
        const loading = shell?.querySelector('.chart-loading');
        if (!shell || !loading) {
            return;
        }

        if (canvas) {
            canvas.style.display = 'none';
        }
        loading.textContent = message;
        shell.classList.add('has-message');
        shell.classList.add('is-ready');
    };

    const getChartState = (chartKey) => {
        return payload?.chart_states?.[chartKey] || {
            has_data: true,
            empty_message: 'Sem dados suficientes para apresentar o gráfico.',
        };
    };

    const renderOutcomesChart = () => {
        if (!payload?.outcomes_chart || typeof Chart === 'undefined') {
            return;
        }
        const chartState = getChartState('outcomes_chart');
        if (!chartState.has_data) {
            showChartMessage('outcomes-chart', chartState.empty_message);
            return;
        }
        const canvas = markChartReady('outcomes-chart');
        if (!canvas) {
            return;
        }

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: payload.outcomes_chart.labels,
                datasets: [
                    {
                        data: payload.outcomes_chart.datasets[0].data,
                        backgroundColor: ['#1f8a5b', '#cf3f3f', '#c8801e'],
                        borderColor: '#ffffff',
                        borderWidth: 3,
                    },
                ],
            },
            options: {
                ...chartDefaults,
                cutout: '62%',
            },
        });
    };

    const renderTemporalChart = () => {
        if (!payload?.temporal_chart || typeof Chart === 'undefined') {
            return;
        }
        const chartState = getChartState('temporal_chart');
        if (!chartState.has_data) {
            showChartMessage('temporal-chart', chartState.empty_message);
            return;
        }
        const canvas = markChartReady('temporal-chart');
        if (!canvas) {
            return;
        }

        const palette = ['#0f4c81', '#cf3f3f', '#c8801e'];
        new Chart(canvas, {
            type: 'line',
            data: {
                labels: payload.temporal_chart.labels,
                datasets: payload.temporal_chart.datasets.map((dataset, index) => ({
                    ...dataset,
                    borderColor: palette[index],
                    backgroundColor: palette[index],
                    tension: 0.28,
                    fill: false,
                })),
            },
            options: {
                ...chartDefaults,
                scales: {
                    x: {
                        ticks: { color: '#6b7280' },
                        grid: { color: '#eef2f7' },
                    },
                    y: {
                        ticks: { color: '#6b7280' },
                        grid: { color: '#eef2f7' },
                    },
                },
            },
        });
    };

    const renderBarChart = (canvasId, chartKey, color) => {
        if (!payload?.[chartKey] || typeof Chart === 'undefined') {
            return;
        }
        const chartState = getChartState(chartKey);
        if (!chartState.has_data) {
            showChartMessage(canvasId, chartState.empty_message);
            return;
        }
        const canvas = markChartReady(canvasId);
        if (!canvas) {
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: payload[chartKey].labels,
                datasets: payload[chartKey].datasets.map((dataset) => ({
                    ...dataset,
                    backgroundColor: color,
                    borderRadius: 8,
                })),
            },
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ticks: { color: '#6b7280' },
                        grid: { display: false },
                    },
                    y: {
                        ticks: { color: '#6b7280' },
                        grid: { color: '#eef2f7' },
                    },
                },
            },
        });
    };

    renderOutcomesChart();
    renderTemporalChart();
    renderBarChart('churn-chart', 'churn_chart', '#9aa7b8');
    renderBarChart('actions-chart', 'actions_chart', '#0f4c81');

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
                applyMetricHighlights(table);
            });
        });

        applyMetricHighlights(table);
    });

    function applyMetricHighlights(table) {
        const highlightColumn = Number(table.dataset.highlightColumn);
        if (Number.isNaN(highlightColumn)) {
            return;
        }

        const rows = Array.from(table.querySelectorAll('tbody tr')).filter(
            (row) => !row.querySelector('.table-empty')
        );
        const cells = rows
            .map((row) => row.children[highlightColumn - 1])
            .filter(Boolean);

        cells.forEach((cell) => {
            cell.classList.remove('metric-good', 'metric-bad');
        });

        const values = cells
            .map((cell) => Number((cell.textContent || '').trim().replace('%', '').replace(',', '.')))
            .filter((value) => !Number.isNaN(value));

        if (!values.length) {
            return;
        }

        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);

        cells.forEach((cell) => {
            const value = Number((cell.textContent || '').trim().replace('%', '').replace(',', '.'));
            if (Number.isNaN(value)) {
                return;
            }
            if (value === maxValue) {
                cell.classList.add('metric-good');
            }
            if (value === minValue) {
                cell.classList.add('metric-bad');
            }
        });
    }
});
