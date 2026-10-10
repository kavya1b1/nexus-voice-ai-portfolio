// ── Animated Counters ──
(function () {
  const counters = document.querySelectorAll('.stat-num');
  let triggered  = false;

  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

  function run() {
    if (triggered) return;
    triggered = true;
    counters.forEach(el => {
      const target   = parseInt(el.dataset.count, 10);
      const duration = 1800;
      const start    = performance.now();
      (function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        el.textContent = Math.floor(easeOut(progress) * target);
        if (progress < 1) requestAnimationFrame(tick);
        else el.textContent = target;
      })(performance.now());
    });
  }

  const statsEl = document.querySelector('.hero-stats');
  if (!statsEl) return;
  new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) run();
  }, { threshold: 0.5 }).observe(statsEl);
})();
