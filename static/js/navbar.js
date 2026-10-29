(function () {
    var toggle = document.getElementById('navbar-toggle');
    var menu = document.getElementById('navbar-mobile-menu');
    if (!toggle || !menu) {
        return;
    }

    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var pendingCloseHandler = null;

    function clearPendingClose() {
        if (pendingCloseHandler) {
            menu.removeEventListener('transitionend', pendingCloseHandler);
            pendingCloseHandler = null;
        }
    }

    function open() {
        clearPendingClose();
        menu.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        toggle.classList.add('is-open');

        if (prefersReducedMotion) {
            menu.classList.add('is-visible');
            return;
        }

        void menu.offsetHeight;
        menu.classList.add('is-visible');
    }

    function close() {
        if (menu.hidden) {
            return;
        }

        clearPendingClose();
        menu.classList.remove('is-visible');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.classList.remove('is-open');

        if (prefersReducedMotion) {
            menu.hidden = true;
            return;
        }

        pendingCloseHandler = function (event) {
            if (event.target !== menu) {
                return;
            }
            menu.hidden = true;
            clearPendingClose();
        };
        menu.addEventListener('transitionend', pendingCloseHandler);
    }

    toggle.addEventListener('click', function () {
        if (toggle.getAttribute('aria-expanded') === 'true') {
            close();
        } else {
            open();
        }
    });

    menu.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', close);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            close();
        }
    });

    var breakpoint = window.matchMedia('(min-width: 861px)');
    breakpoint.addEventListener('change', function (event) {
        if (event.matches) {
            close();
        }
    });
})();
