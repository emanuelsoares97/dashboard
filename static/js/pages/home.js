document.addEventListener('DOMContentLoaded', () => {
    const homeCard = document.querySelector('[data-page="home"]');
    if (!homeCard) {
        return;
    }

    homeCard.classList.add('is-ready');
});
