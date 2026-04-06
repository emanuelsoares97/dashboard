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
    const navBackdrop = document.querySelector('[data-nav-backdrop]');

    if (!header || !navToggle || !navMenu) {
        return;
    }

    const closeMenu = () => {
        header.classList.remove('is-menu-open');
        document.body.classList.remove('is-nav-open');
        navToggle.setAttribute('aria-expanded', 'false');
    };

    navToggle.addEventListener('click', () => {
        const isOpen = header.classList.toggle('is-menu-open');
        document.body.classList.toggle('is-nav-open', isOpen);
        navToggle.setAttribute('aria-expanded', String(isOpen));
    });

    if (navBackdrop) {
        navBackdrop.addEventListener('click', closeMenu);
    }

    navMenu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                closeMenu();
            }
        });
    });

    document.addEventListener('click', (event) => {
        const clickedInsideHeader = header.contains(event.target);
        if (clickedInsideHeader || !header.classList.contains('is-menu-open')) {
            return;
        }

        closeMenu();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && header.classList.contains('is-menu-open')) {
            closeMenu();
        }
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && header.classList.contains('is-menu-open')) {
            closeMenu();
        }
    });

});
