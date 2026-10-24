(function () {
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var revealTargets = document.querySelectorAll('.lp-reveal');
    var countTargets = document.querySelectorAll('[data-count-to]');

    if (prefersReducedMotion) {
        revealTargets.forEach(function (el) { el.classList.add('is-visible'); });
        countTargets.forEach(function (el) { el.textContent = el.dataset.countTo; });
        return;
    }

    function animateCount(el) {
        var target = parseInt(el.dataset.countTo, 10);
        var duration = 1200;
        var start = null;

        function step(timestamp) {
            if (start === null) start = timestamp;
            var progress = Math.min((timestamp - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        }

        window.requestAnimationFrame(step);
    }

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;

            entry.target.classList.add('is-visible');

            if (entry.target.hasAttribute('data-count-to')) {
                animateCount(entry.target);
            }

            observer.unobserve(entry.target);
        });
    }, { threshold: 0.2 });

    revealTargets.forEach(function (el) { observer.observe(el); });

    countTargets.forEach(function (el) {
        if (!el.classList.contains('lp-reveal')) {
            observer.observe(el);
        }
    });
})();
