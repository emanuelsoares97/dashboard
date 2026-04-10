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

    const mobileBreakpoint = window.matchMedia('(max-width: 720px)');
    const menuToggle = dashboard.querySelector('[data-dashboard-menu-toggle]');
    const menu = dashboard.querySelector('[data-dashboard-menu]');

    const closeDashboardMenu = () => {
        if (!menuToggle || !menu) {
            return;
        }
        menu.classList.remove('is-open');
        menuToggle.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
    };

    const openDashboardMenu = () => {
        if (!menuToggle || !menu) {
            return;
        }
        menu.classList.add('is-open');
        menuToggle.classList.add('is-open');
        menuToggle.setAttribute('aria-expanded', 'true');
    };

    if (menuToggle && menu) {
        menuToggle.addEventListener('click', () => {
            if (menu.classList.contains('is-open')) {
                closeDashboardMenu();
                return;
            }
            openDashboardMenu();
        });

        menu.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', () => {
                if (mobileBreakpoint.matches) {
                    closeDashboardMenu();
                }
            });
        });

        if (!mobileBreakpoint.matches) {
            openDashboardMenu();
        }

        mobileBreakpoint.addEventListener('change', (event) => {
            if (event.matches) {
                closeDashboardMenu();
                return;
            }
            openDashboardMenu();
        });
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
        const headers = Array.from(table.querySelectorAll('thead th'));
        const tbody = table.querySelector('tbody');
        if (!tbody || !headers.length) {
            return;
        }

        const normalizeNumericText = (value) => {
            return String(value || '')
                .trim()
                .replace(/\s+/g, '')
                .replace('%', '')
                .replace(/\.(?=\d{3}(\D|$))/g, '')
                .replace(',', '.');
        };

        const parseDateValue = (value) => {
            const text = String(value || '').trim();

            // dd/mm/yyyy [hh:mm]
            const ptDateTime = text.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?$/);
            if (ptDateTime) {
                const [, day, month, year, hour = '00', minute = '00'] = ptDateTime;
                const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
                return Number.isNaN(date.getTime()) ? null : date.getTime();
            }

            // yyyy-mm-dd [hh:mm]
            const isoDateTime = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2}))?$/);
            if (isoDateTime) {
                const [, year, month, day, hour = '00', minute = '00'] = isoDateTime;
                const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
                return Number.isNaN(date.getTime()) ? null : date.getTime();
            }

            return null;
        };

        const readCellSortValue = (row, columnIndex) => {
            const cell = row.children[columnIndex];
            if (!cell) {
                return { type: 'text', value: '' };
            }

            const raw = cell.dataset.sortValue || cell.textContent || '';
            const parsedDate = parseDateValue(raw);
            if (parsedDate !== null) {
                return { type: 'number', value: parsedDate };
            }

            const numeric = Number(normalizeNumericText(raw));
            if (!Number.isNaN(numeric)) {
                return { type: 'number', value: numeric };
            }

            return { type: 'text', value: String(raw).trim().toLocaleLowerCase('pt-PT') };
        };

        const sortRows = (columnIndex, order) => {
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const dataRows = rows.filter((row) => !row.querySelector('.table-empty'));

            dataRows.sort((rowA, rowB) => {
                const valueA = readCellSortValue(rowA, columnIndex);
                const valueB = readCellSortValue(rowB, columnIndex);

                if (valueA.type === 'number' && valueB.type === 'number') {
                    return order === 'asc' ? valueA.value - valueB.value : valueB.value - valueA.value;
                }

                return order === 'asc'
                    ? String(valueA.value).localeCompare(String(valueB.value), 'pt-PT')
                    : String(valueB.value).localeCompare(String(valueA.value), 'pt-PT');
            });

            dataRows.forEach((row) => tbody.appendChild(row));
            applyMetricHighlights(table);
        };

        const resolveDefaultSort = () => {
            const explicitIndex = Number(table.dataset.defaultSortColumn || 0);
            if (explicitIndex > 0 && explicitIndex <= headers.length) {
                return {
                    index: explicitIndex - 1,
                    order: table.dataset.defaultSortOrder === 'asc' ? 'asc' : 'desc',
                };
            }

            const headerTexts = headers.map((header) => (header.textContent || '').trim().toLowerCase());

            const findHeader = (predicate) => headerTexts.findIndex(predicate);
            const retentionIdx = findHeader((text) => text.includes('taxa reten'));
            if (retentionIdx >= 0) {
                return { index: retentionIdx, order: 'desc' };
            }

            const errorIdx = findHeader((text) => text.includes('erro') || text.includes('inconsist') || text.includes('flags'));
            if (errorIdx >= 0) {
                return { index: errorIdx, order: 'desc' };
            }

            const scoreIdx = findHeader((text) => text.includes('score'));
            if (scoreIdx >= 0) {
                return { index: scoreIdx, order: 'desc' };
            }

            const volumeIdx = findHeader((text) => text.includes('total') || text.includes('chamada') || text.includes('volume'));
            if (volumeIdx >= 0) {
                return { index: volumeIdx, order: 'desc' };
            }

            return { index: 0, order: 'asc' };
        };

        headers.forEach((header, columnIndex) => {
            header.classList.add('is-sortable');
            header.addEventListener('click', () => {
                const currentOrder = header.dataset.sortOrder === 'asc' ? 'asc' : header.dataset.sortOrder === 'desc' ? 'desc' : null;
                const nextOrder = currentOrder === 'asc' ? 'desc' : 'asc';

                headers.forEach((item) => {
                    item.removeAttribute('data-sort-order');
                });
                header.dataset.sortOrder = nextOrder;
                sortRows(columnIndex, nextOrder);
            });
        });

        const defaultSort = resolveDefaultSort();
        headers.forEach((item) => {
            item.removeAttribute('data-sort-order');
        });
        headers[defaultSort.index].dataset.sortOrder = defaultSort.order;
        sortRows(defaultSort.index, defaultSort.order);

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
