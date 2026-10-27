(() => {
    const form = document.querySelector('[data-quiz-answer]');
    if (!form || !window.fetch || !window.FormData) return;

    const card = form.closest('[data-quiz-card]');
    const buttons = [...form.querySelectorAll('button[name="option"]')];
    const status = card.querySelector('[data-quiz-status]');
    const error = card.querySelector('[data-quiz-error]');
    let submitting = false;

    form.addEventListener('submit', async (event) => {
        const selected = event.submitter;
        if (!selected || selected.name !== 'option') return;
        event.preventDefault();
        if (submitting || selected.disabled) return;

        const data = new FormData(form);
        data.set('option', selected.value);
        submitting = true;
        form.setAttribute('aria-busy', 'true');
        error.hidden = true;
        status.textContent = 'Memeriksa jawaban…';
        buttons.forEach((button) => { button.disabled = true; });

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: data,
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
                mode: 'same-origin',
            });
            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }
            if (!response.headers.get('Content-Type')?.includes('application/json')) {
                throw new Error(response.status === 403
                    ? 'Sesi keamanan kedaluwarsa. Muat ulang halaman kuis lalu coba lagi.'
                    : 'Hasil jawaban belum dapat ditampilkan. Coba lagi atau muat ulang halaman kuis.');
            }
            const payload = await response.json();
            if (response.status === 401 && payload.login_url) {
                window.location.assign(payload.login_url);
                return;
            }
            if (!response.ok) throw new Error(payload.error || 'Jawaban belum dapat diproses. Coba lagi.');

            const parsedDocument = new DOMParser().parseFromString(payload.html, 'text/html');
            const replacement = parsedDocument.querySelector('[data-quiz-card]');
            if (!replacement) throw new Error('Hasil jawaban belum dapat ditampilkan. Muat ulang halaman kuis.');
            card.replaceWith(replacement);
            replacement.querySelector('[data-quiz-result]')?.focus();
        } catch (failure) {
            error.querySelector('[data-quiz-error-text]').textContent = failure.message
                || 'Koneksi terputus. Coba lagi atau muat ulang halaman kuis untuk memeriksa hasilnya.';
            error.hidden = false;
            error.focus();
        } finally {
            submitting = false;
            form.removeAttribute('aria-busy');
            status.textContent = '';
            buttons.forEach((button) => { button.disabled = false; });
        }
    });
})();
