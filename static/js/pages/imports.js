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
    const progressMeta = uploadForm.querySelector('[data-import-progress-meta]');
    const submitButton = uploadForm.querySelector('button[type="submit"]');

    const updateProgress = (percent, labelText, metaText = '') => {
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
        if (progressMeta) {
            progressMeta.textContent = metaText;
        }
    };

    const formatDuration = (seconds) => {
        if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
            return '';
        }

        const safe = Math.max(0, Math.round(seconds));
        const mins = Math.floor(safe / 60);
        const secs = safe % 60;
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    };

    const setSubmitState = (disabled, text) => {
        if (!submitButton) {
            return;
        }
        submitButton.disabled = disabled;
        if (text) {
            submitButton.textContent = text;
        }
    };

    const pollImportStatus = (statusUrl) => {
        const pollEveryMs = 2000;

        const runPoll = () => {
            fetch(statusUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            })
                .then((response) => response.json())
                .then((payload) => {
                    const processed = payload.processed_rows || 0;
                    const total = payload.total_rows || 0;
                    const eta = formatDuration(payload.eta_seconds);
                    const elapsed = formatDuration(payload.elapsed_seconds);
                    const meta = total > 0
                        ? `${processed}/${total} linhas processadas${eta ? ` | ETA ${eta}` : ''}${elapsed ? ` | Decorrido ${elapsed}` : ''}`
                        : (elapsed ? `Decorrido ${elapsed}` : '');

                    if (payload.status === 'processing' || payload.status === 'pending') {
                        updateProgress(payload.progress_pct || 0, 'A importar no servidor...', meta);
                        window.setTimeout(runPoll, pollEveryMs);
                        return;
                    }

                    if (payload.status === 'success' || payload.status === 'partial') {
                        updateProgress(100, 'Importação concluída.', meta);
                        setSubmitState(false, 'Importar');
                        uploadForm.dataset.readingInProgress = 'done';
                        return;
                    }

                    updateProgress(payload.progress_pct || 100, 'Importação falhou.', payload.error_log || meta);
                    setSubmitState(false, 'Importar');
                    uploadForm.dataset.readingInProgress = 'done';
                })
                .catch(() => {
                    updateProgress(100, 'Não foi possível acompanhar o progresso.', 'Atualiza a página para ver o estado final do lote.');
                    setSubmitState(false, 'Importar');
                    uploadForm.dataset.readingInProgress = 'done';
                });
        };

        runPoll();
    };

    uploadForm.addEventListener('submit', (event) => {
        if (uploadForm.dataset.readingInProgress === 'true') {
            return;
        }

        setSubmitState(true, 'A importar...');

        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            setSubmitState(false, 'Importar');
            return;
        }

        const file = fileInput.files[0];
        if (!file || file.size <= 0) {
            setSubmitState(false, 'Importar');
            return;
        }

        event.preventDefault();
        uploadForm.dataset.readingInProgress = 'true';
        updateProgress(0, 'A ler o ficheiro local...', '');

        const reader = new FileReader();

        reader.onprogress = (progressEvent) => {
            if (!progressEvent.lengthComputable) {
                return;
            }
            const percent = (progressEvent.loaded / progressEvent.total) * 100;
            updateProgress(percent, 'A ler o ficheiro local...', 'A validar ficheiro antes do envio...');
        };

        reader.onload = () => {
            updateProgress(100, 'Leitura concluída.', 'A enviar ficheiro para o servidor...');

            const xhr = new XMLHttpRequest();
            xhr.open(uploadForm.method || 'POST', uploadForm.action || window.location.href, true);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

            xhr.upload.onprogress = (progressEvent) => {
                if (!progressEvent.lengthComputable) {
                    updateProgress(100, 'A enviar ficheiro para o servidor...', 'Upload em curso...');
                    return;
                }
                const percent = (progressEvent.loaded / progressEvent.total) * 100;
                updateProgress(percent, 'A enviar ficheiro para o servidor...', 'Upload em curso...');
            };

            xhr.onload = () => {
                if (xhr.status !== 202) {
                    setSubmitState(false, 'Importar');
                    uploadForm.dataset.readingInProgress = 'done';
                    updateProgress(100, 'Falha ao iniciar importação.', 'Atualiza a página e tenta novamente.');
                    return;
                }

                let payload = null;
                try {
                    payload = JSON.parse(xhr.responseText);
                } catch (error) {
                    payload = null;
                }

                if (!payload || !payload.status_url) {
                    setSubmitState(false, 'Importar');
                    uploadForm.dataset.readingInProgress = 'done';
                    updateProgress(100, 'Resposta inválida do servidor.', 'Atualiza a página para verificar o lote.');
                    return;
                }

                updateProgress(0, 'Importação iniciada no servidor...', 'A acompanhar processamento em tempo real...');
                pollImportStatus(payload.status_url);
            };

            xhr.onerror = () => {
                setSubmitState(false, 'Importar');
                uploadForm.dataset.readingInProgress = 'done';
                updateProgress(100, 'Falha no envio.', 'Verifica a ligação e tenta novamente.');
            };

            const formData = new FormData(uploadForm);
            xhr.send(formData);
        };

        reader.onerror = () => {
            setSubmitState(false, 'Importar');
            uploadForm.dataset.readingInProgress = 'done';
            updateProgress(100, 'Falha ao ler ficheiro local.', 'Tenta selecionar o ficheiro novamente.');
        };

        reader.readAsArrayBuffer(file);
    });
});
