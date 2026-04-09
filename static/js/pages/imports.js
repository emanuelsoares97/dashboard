document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.querySelector('[data-page="imports"] form');
    if (!uploadForm) {
        return;
    }

    const fileInput = uploadForm.querySelector('input[type="file"]');
    const progressRoot = uploadForm.querySelector('[data-import-progress]');
    const progressBar = uploadForm.querySelector('[data-import-progress-bar]');
    const progressValue = uploadForm.querySelector('[data-import-progress-value]');
    const progressLabel = uploadForm.querySelector('[data-import-progress-label]');

    const updateProgress = (percent, labelText) => {
        if (!progressRoot || !progressBar || !progressValue) {
            return;
        }

        const bounded = Math.max(0, Math.min(100, Math.round(percent)));
        progressRoot.hidden = false;
        progressBar.style.width = `${bounded}%`;
        progressValue.textContent = `${bounded}%`;

        const track = progressRoot.querySelector('.import-progress-track');
        if (track) {
            track.setAttribute('aria-valuenow', String(bounded));
        }

        if (progressLabel && labelText) {
            progressLabel.textContent = labelText;
        }
    };

    uploadForm.addEventListener('submit', (event) => {
        if (uploadForm.dataset.readingInProgress === 'true') {
            return;
        }

        const submitButton = uploadForm.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'A importar...';
        }

        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            return;
        }

        const file = fileInput.files[0];
        if (!file || file.size <= 0) {
            return;
        }

        event.preventDefault();
        uploadForm.dataset.readingInProgress = 'true';
        updateProgress(0, 'A ler o ficheiro local...');

        const reader = new FileReader();

        reader.onprogress = (progressEvent) => {
            if (!progressEvent.lengthComputable) {
                return;
            }
            const percent = (progressEvent.loaded / progressEvent.total) * 100;
            updateProgress(percent, 'A ler o ficheiro local...');
        };

        reader.onload = () => {
            updateProgress(100, 'Leitura concluída. A enviar para importação...');
            window.setTimeout(() => {
                uploadForm.dataset.readingInProgress = 'submitted';
                HTMLFormElement.prototype.submit.call(uploadForm);
            }, 120);
        };

        reader.onerror = () => {
            uploadForm.dataset.readingInProgress = 'submitted';
            HTMLFormElement.prototype.submit.call(uploadForm);
        };

        reader.readAsArrayBuffer(file);
    });
});
