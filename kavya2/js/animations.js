// ── Scroll Reveal + Highlight underline ──
(function () {
  const revealEls  = document.querySelectorAll('.reveal-up, .reveal-left, .reveal-right');
  const highlights = document.querySelectorAll('.highlight');

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  revealEls.forEach(el => io.observe(el));
  highlights.forEach(el => io.observe(el));

  // Parallax hero bg text
  const bgText = document.querySelector('.hero-bg-text');
  if (bgText) {
    window.addEventListener('scroll', () => {
      bgText.style.transform = `translateY(${window.scrollY * 0.25}px)`;
    }, { passive: true });
  }
})();
