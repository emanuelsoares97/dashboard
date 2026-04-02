document.addEventListener('DOMContentLoaded', () => {
    const appName = document.body.dataset.app;
    if (!appName) {
        return;
    }

    // Central point for global hooks shared by all pages.
    document.body.classList.add('is-ready');
});
