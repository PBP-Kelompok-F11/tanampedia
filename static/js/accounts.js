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

    function initializeModals() {
        document.querySelectorAll('[data-modal-open]').forEach((trigger) => {
            trigger.addEventListener('click', () => {
                const modal = document.getElementById(trigger.dataset.modalOpen);
                if (modal) {
                    modal.hidden = false;
                }
            });
        });

        document.querySelectorAll('.modal').forEach((modal) => {
            const close = () => {
                modal.hidden = true;
            };

            modal.querySelectorAll('[data-modal-close]').forEach((button) => {
                button.addEventListener('click', close);
            });

            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape' && !modal.hidden) {
                    close();
                }
            });
        });
    }

    function initializeEditProfileForm() {
        const form = document.getElementById('edit-profile-form');
        if (!form) {
            return;
        }

        const modal = form.closest('.modal');
        const message = document.getElementById('edit-profile-message');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            clearFormErrors(form);
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
                    message.textContent = 'Periksa kembali data yang kamu masukkan.';
                    return;
                }

                document.querySelectorAll('[data-profile-display-name]').forEach((el) => {
                    el.textContent = data.display_name_or_username;
                });
                document.querySelectorAll('[data-navbar-display-name]').forEach((el) => {
                    el.textContent = data.display_name_or_username;
                });
                const bioEl = document.querySelector('[data-profile-bio]');
                if (bioEl) {
                    bioEl.textContent = data.bio || 'Belum ada bio.';
                }

                if (modal) {
                    modal.hidden = true;
                }
            } catch (error) {
                message.textContent = 'Profil gagal disimpan. Periksa koneksi lalu coba lagi.';
                console.error('Gagal memperbarui profil:', error);
            }
        });
    }

    initializeModals();
    initializeEditProfileForm();
})();
