document.addEventListener('DOMContentLoaded', () => {
    const appName = document.body.dataset.app;
    if (!appName) {
        return;
    }

    // Central point for global hooks shared by all pages.
    document.body.classList.add('is-ready');

    const header = document.querySelector('.site-header');
    const navToggle = document.querySelector('[data-nav-toggle]');
    const navMenu = document.querySelector('[data-nav-menu]');

    if (!header || !navToggle || !navMenu) {
        return;
    }

    navToggle.addEventListener('click', () => {
        const isOpen = header.classList.toggle('is-menu-open');
        navToggle.setAttribute('aria-expanded', String(isOpen));
    });

    document.addEventListener('click', (event) => {
        const clickedInsideHeader = header.contains(event.target);
        if (clickedInsideHeader || !header.classList.contains('is-menu-open')) {
            return;
        }

        header.classList.remove('is-menu-open');
        navToggle.setAttribute('aria-expanded', 'false');
    });
});
