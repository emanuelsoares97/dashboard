document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.querySelector('[data-page="imports"] form');
    if (!uploadForm) {
        return;
    }

    uploadForm.addEventListener('submit', () => {
        const submitButton = uploadForm.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Importando...';
        }
    });
});
