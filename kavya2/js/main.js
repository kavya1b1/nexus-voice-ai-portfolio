// ── Main Interactions ──
(function () {

  // ── Magnetic primary buttons ──
  document.querySelectorAll('.btn-primary').forEach(btn => {
    btn.addEventListener('mousemove', (e) => {
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width  / 2;
      const y = e.clientY - rect.top  - rect.height / 2;
      btn.style.transform = `translate(${x * 0.22}px, ${y * 0.38}px)`;
    });
    btn.addEventListener('mouseleave', () => { btn.style.transform = ''; });
  });

  // ── 3D Tilt on project cards ──
  document.querySelectorAll('.project-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const rx   = (e.clientY - rect.top  - rect.height / 2) / (rect.height / 2) *  5;
      const ry   = (e.clientX - rect.left - rect.width  / 2) / (rect.width  / 2) * -5;
      card.style.transform  = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px)`;
      card.style.transition = 'transform 0.08s linear';
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform  = '';
      card.style.transition = 'transform 0.4s var(--ease-out)';
    });
  });

  // ── Smooth scroll ──
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // ── Typewriter in hero subtitle ──
  const heroSub = document.querySelector('.hero-sub');
  if (heroSub) {
    const roles = [
      'Generative AI Engineer',
      'ML Researcher',
      'RAG Pipeline Builder',
      'Full-Stack AI Developer',
      'Hackathon Finalist'
    ];
    heroSub.innerHTML = 'AI/ML engineer at <em>VIT Bhopal</em> — crafting<br/>intelligent systems, one model at a time.<br/><span id="tw" style="color:var(--clr-accent);border-right:2px solid var(--clr-accent);padding-right:3px;font-style:normal"></span>';
    const tw = document.getElementById('tw');
    if (tw) {
      let ri = 0, ci = 0, deleting = false;
      function type() {
        const word = roles[ri];
        if (!deleting) {
          tw.textContent = word.slice(0, ++ci);
          if (ci === word.length) { deleting = true; setTimeout(type, 1800); return; }
        } else {
          tw.textContent = word.slice(0, --ci);
          if (ci === 0) { deleting = false; ri = (ri + 1) % roles.length; }
        }
        setTimeout(type, deleting ? 50 : 95);
      }
      setTimeout(type, 1200);
    }
  }

  // ── Back to top visibility ──
  const btt = document.getElementById('backToTop');
  if (btt) {
    btt.style.opacity    = '0';
    btt.style.transition = 'opacity .3s';
    window.addEventListener('scroll', () => {
      btt.style.opacity = window.scrollY > 500 ? '1' : '0';
    }, { passive: true });
  }

})();
