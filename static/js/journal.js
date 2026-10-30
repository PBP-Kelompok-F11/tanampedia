(function () {
    function initializeDeleteDialog() {
        const dialog = document.getElementById('journal-delete-dialog');
        if (!dialog) return;
        const form = document.getElementById('delete-dialog-form');
        const title = document.getElementById('delete-dialog-title');
        const description = document.getElementById('delete-dialog-description');
        const error = dialog.querySelector('[data-delete-error]');
        const cancel = dialog.querySelector('[data-delete-cancel] button');
        let trigger = null;
        let busy = false;
        document.querySelectorAll('[data-delete-trigger]').forEach((element) => {
            const button = element.matches('button') ? element : element.querySelector('button');
            if (button) {
                button.setAttribute('aria-haspopup', 'dialog');
                button.setAttribute('aria-controls', dialog.id);
            }
        });

        document.addEventListener('click', (event) => {
            const target = event.target.closest('[data-delete-trigger]');
            if (!target || busy) return;
            trigger = target;
            const isJournal = trigger.dataset.deleteKind === 'journal';
            title.textContent = isJournal ? 'Hapus jurnal?' : 'Hapus entri?';
            description.textContent = isJournal
                ? `Jurnal “${trigger.dataset.deleteLabel}”, beserta semua entri dan likes, akan dihapus permanen.`
                : `Entri “${trigger.dataset.deleteLabel}” akan dihapus permanen. Tindakan ini tidak dapat dibatalkan.`;
            form.action = trigger.dataset.deleteUrl;
            error.textContent = '';
            const menu = trigger.closest('details');
            if (menu) menu.open = false;
            dialog.showModal();
            cancel.focus();
        });
        cancel.addEventListener('click', () => {
            if (!busy) dialog.close();
        });
        dialog.addEventListener('cancel', (event) => {
            if (busy) event.preventDefault();
        });
        dialog.addEventListener('close', () => {
            if (!trigger || !trigger.isConnected) return;
            const menu = trigger.closest('details');
            const focusTarget = menu ? menu.querySelector('summary')
                : trigger.matches('button') ? trigger : trigger.querySelector('button');
            if (focusTarget) focusTarget.focus();
        });
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (busy || !trigger) return;
            busy = true;
            form.querySelectorAll('button').forEach((button) => { button.disabled = true; });
            error.textContent = '';
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Accept': 'application/json' },
                    body: new FormData(form),
                    credentials: 'same-origin',
                });
                if (response.redirected) throw new Error('Sesi berakhir. Muat ulang halaman dan masuk kembali.');
                if (!response.ok) throw new Error('Gagal menghapus. Muat ulang halaman atau coba lagi.');
                const data = await response.json();
                if (trigger.dataset.deleteKind === 'journal') {
                    window.location.assign(data.url);
                    return;
                }
                const card = document.getElementById(`entry-${data.deleted}`);
                if (card) card.remove();
                document.querySelectorAll('[data-entry-count]').forEach((element) => {
                    element.textContent = data.entry_count;
                });
                const empty = document.getElementById('empty-entries');
                if (empty) empty.hidden = data.entry_count !== 0;
                dialog.close();
                const addEntry = document.querySelector('.journal-detail__toolbar .btn');
                if (addEntry) addEntry.focus();
            } catch (failure) {
                error.textContent = failure.message || 'Gagal menghapus. Periksa koneksi dan coba lagi.';
            } finally {
                busy = false;
                form.querySelectorAll('button').forEach((button) => { button.disabled = false; });
            }
        });
    }

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
                    const filtersForm = dropdown.closest('[data-journal-filters-form]');
                    if (filtersForm) return filtersForm.requestSubmit();
                });
            });
        });
    }

    function initializeJournalSearch() {
        const form = document.querySelector('[data-journal-filters-form]');
        const input = document.getElementById('journal-search');
        const list = document.getElementById('journal-list');
        const message = document.getElementById('journal-search-message');
        if (!form || !input || !list || !message) return;

        let timer;
        let controller;
        let composing = false;

        function cancelPendingSearch() {
            clearTimeout(timer);
            if (controller) controller.abort();
            list.removeAttribute('aria-busy');
            message.textContent = '';
        }

        function scheduleSearch() {
            cancelPendingSearch();
            if (!composing) timer = setTimeout(() => form.requestSubmit(), 400);
        }

        input.addEventListener('input', scheduleSearch);
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.isComposing && !composing) {
                event.preventDefault();
                form.requestSubmit();
            }
        });
        input.addEventListener('compositionstart', () => {
            composing = true;
            cancelPendingSearch();
        });
        input.addEventListener('compositionend', () => {
            composing = false;
            scheduleSearch();
        });

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            cancelPendingSearch();
            if (composing) return;

            const url = new URL(form.action, window.location.href);
            url.search = new URLSearchParams(new FormData(form)).toString();
            url.searchParams.delete('page');
            const request = new AbortController();
            controller = request;
            list.setAttribute('aria-busy', 'true');
            message.textContent = 'Mencari jurnal...';

            try {
                const response = await fetch(url, {
                    signal: request.signal,
                    credentials: 'same-origin',
                });
                if (request.signal.aborted) return;
                if (response.redirected) {
                    window.location.assign(response.url);
                    return;
                }
                if (!response.ok) throw new Error('Search failed');
                const page = new DOMParser().parseFromString(await response.text(), 'text/html');
                if (request.signal.aborted) return;
                const results = page.getElementById('journal-list');
                if (!results) throw new Error('Missing journal list');

                list.replaceChildren(...results.childNodes);
                // Keep tab links in sync with the latest search and filter values.
                const tabs = document.querySelectorAll('[data-journal-tab]');
                const updatedTabs = page.querySelectorAll('[data-journal-tab]');
                tabs.forEach((tab, index) => {
                    if (updatedTabs[index]) tab.setAttribute('href', updatedTabs[index].getAttribute('href'));
                });
                window.history.replaceState(null, '', url);
                message.textContent = `${list.querySelectorAll('.journal-card').length} jurnal ditemukan.`;
            } catch (error) {
                if (!request.signal.aborted) {
                    message.textContent = 'Pencarian gagal. Periksa koneksi lalu tekan Enter untuk mencoba lagi.';
                }
            } finally {
                if (controller === request) list.removeAttribute('aria-busy');
            }
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

    initializeDeleteDialog();
    initializeDropdowns();
    initializeJournalSearch();
    initializeJournalForm();
    initializeEntryForm();
    initializeJournalLikes();
})();
