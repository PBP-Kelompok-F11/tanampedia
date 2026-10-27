(function () {
    function getCookie(name) {
        const cookie = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`));
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    }

    function clearFormErrors(form) {
        form.querySelectorAll('[data-error-for]').forEach((element) => {
            element.textContent = '';
        });
    }

    function showFormErrors(form, errors) {
        Object.entries(errors || {}).forEach(([name, messages]) => {
            const fieldError = form.querySelector(`[data-error-for="${name}"]`);
            if (fieldError) {
                fieldError.textContent = messages.map((error) => error.message).join(' ');
            }
        });
    }

    function initializeDropdowns() {
        document.querySelectorAll('[data-dropdown]').forEach((dropdown) => {
            const trigger = dropdown.querySelector('[role="combobox"]');
            const menu = dropdown.querySelector('[role="listbox"]');
            const value = dropdown.querySelector('[data-dropdown-value]');
            const input = dropdown.querySelector('[data-dropdown-input]');

            trigger.addEventListener('click', () => {
                const isOpen = trigger.getAttribute('aria-expanded') === 'true';
                trigger.setAttribute('aria-expanded', String(!isOpen));
                menu.hidden = isOpen;
            });

            dropdown.querySelectorAll('[role="option"]').forEach((option) => {
                option.addEventListener('click', () => {
                    input.value = option.dataset.value;
                    value.textContent = option.textContent.trim();
                    value.classList.remove('dropdown__value--placeholder');
                    dropdown.querySelectorAll('[role="option"]').forEach((item) => {
                        item.setAttribute('aria-selected', String(item === option));
                    });
                    trigger.setAttribute('aria-expanded', 'false');
                    menu.hidden = true;
                });
            });
        });
    }

    function initializeJournalForm() {
        const form = document.getElementById('journal-form');
        if (!form) {
            return;
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            clearFormErrors(form);
            const message = document.getElementById('journal-form-message');
            message.textContent = '';

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: new FormData(form),
                    credentials: 'same-origin',
                });
                const data = await response.json();
                if (!response.ok) {
                    showFormErrors(form, data.errors);
                    message.textContent = 'Periksa kembali data jurnal yang kamu masukkan.';
                    return;
                }

                window.location.assign(data.url);
            } catch (error) {
                message.textContent = 'Jurnal gagal disimpan. Periksa koneksi lalu coba lagi.';
                console.error('Gagal membuat jurnal:', error);
            }
        });
    }

    function initializeEntryForm() {
        const form = document.getElementById('entry-form');
        if (!form) {
            return;
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            clearFormErrors(form);
            const message = document.getElementById('entry-form-message');
            message.textContent = '';

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: new FormData(form),
                    credentials: 'same-origin',
                });
                const data = await response.json();
                if (!response.ok) {
                    showFormErrors(form, data.errors);
                    message.textContent = 'Periksa kembali catatan yang kamu masukkan.';
                    return;
                }

                window.location.assign(data.url);
            } catch (error) {
                message.textContent = 'Catatan gagal disimpan. Periksa koneksi lalu coba lagi.';
                console.error('Gagal membuat catatan:', error);
            }
        });
    }

    function initializeJournalLikes() {
        document.addEventListener('click', async (event) => {
            const button = event.target.closest('[data-journal-like]');
            if (!button || button.disabled) {
                return;
            }

            button.disabled = true;
            const message = button.parentElement.querySelector('[data-like-message]');
            message.textContent = '';
            try {
                const response = await fetch(button.dataset.likeUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    credentials: 'same-origin',
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Permintaan like gagal.');
                }

                button.setAttribute('aria-pressed', String(data.liked));
                button.setAttribute(
                    'aria-label',
                    data.liked ? 'Batalkan suka' : 'Sukai jurnal',
                );
                button.classList.toggle('journal-like--active', data.liked);
                button.querySelector('[data-like-count]').textContent =
                    `${data.likes_count} likes`;
            } catch (error) {
                console.error('Gagal memperbarui like jurnal:', error);
                message.textContent = 'Like gagal disimpan. Coba lagi.';
            } finally {
                button.disabled = false;
            }
        });
    }

    initializeDropdowns();
    initializeJournalForm();
    initializeEntryForm();
    initializeJournalLikes();
})();
