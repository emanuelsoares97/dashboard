document.addEventListener('DOMContentLoaded', () => {
    const dashboard = document.querySelector('[data-page="dashboard"]');
    if (!dashboard) {
        return;
    }

    dashboard.classList.add('is-ready');
});
