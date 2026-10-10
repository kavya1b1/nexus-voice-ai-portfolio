// ── Skills Filter + Bar Animation ──
(function () {
  const tabs  = document.querySelectorAll('.skill-tab');
  const cards = document.querySelectorAll('.skill-card');
  const fills = document.querySelectorAll('.skill-fill');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const cat = tab.dataset.cat;

      cards.forEach((card, i) => {
        const match = cat === 'all' || card.dataset.cat === cat;
        card.classList.toggle('hidden', !match);
        if (match) {
          card.style.animation = 'none';
          card.offsetHeight; // reflow
          card.style.animation = `fadeInCard 0.4s var(--ease-out) ${i * 0.04}s both`;
        }
      });
    });
  });

  // Animate bars when skills section enters view
  let filled = false;
  new IntersectionObserver((entries) => {
    if (!filled && entries[0].isIntersecting) {
      filled = true;
      fills.forEach(fill => {
        setTimeout(() => { fill.style.width = fill.dataset.pct + '%'; }, 250);
      });
    }
  }, { threshold: 0.2 }).observe(document.getElementById('skills'));
})();
