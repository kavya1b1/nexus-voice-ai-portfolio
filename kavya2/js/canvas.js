// ── Hero Canvas — Neural Particle Field ──
(function () {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];
  let mouse = { x: -9999, y: -9999 };

  function resize() {
    W = canvas.width  = canvas.offsetWidth;
    H = canvas.height = canvas.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize, { passive: true });

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = e.clientX - rect.left;
    mouse.y = e.clientY - rect.top;
  });
  canvas.addEventListener('mouseleave', () => { mouse.x = mouse.y = -9999; });

  class Particle {
    constructor() { this.reset(true); }
    reset(initial) {
      this.x    = Math.random() * W;
      this.y    = initial ? Math.random() * H : H + 10;
      this.r    = Math.random() * 1.5 + 0.3;
      this.vx   = (Math.random() - 0.5) * 0.3;
      this.vy   = -(Math.random() * 0.5 + 0.15);
      this.opacity = Math.random() * 0.5 + 0.1;
      this.life = 0;
      this.maxLife = Math.random() * 300 + 200;
    }
    update() {
      const dx   = this.x - mouse.x;
      const dy   = this.y - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 120) {
        const force = (120 - dist) / 120 * 0.8;
        this.vx += (dx / dist) * force;
        this.vy += (dy / dist) * force;
      }
      this.vx *= 0.98;
      this.vy *= 0.98;
      this.x  += this.vx;
      this.y  += this.vy;
      this.life++;
      if (this.y < -10 || this.life > this.maxLife) this.reset(false);
    }
    draw() {
      const alpha = Math.min(this.life / 40, 1, (this.maxLife - this.life) / 40) * this.opacity;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(232,255,0,${alpha})`;
      ctx.fill();
    }
  }

  const COUNT = window.innerWidth < 768 ? 60 : 140;
  for (let i = 0; i < COUNT; i++) particles.push(new Particle());

  function drawConnections() {
    const MAX = 100;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < MAX) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(232,255,0,${(1 - d / MAX) * 0.08})`;
          ctx.lineWidth   = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  function drawMouseConnections() {
    particles.forEach(p => {
      const dx = p.x - mouse.x;
      const dy = p.y - mouse.y;
      const d  = Math.sqrt(dx * dx + dy * dy);
      if (d < 150) {
        ctx.beginPath();
        ctx.moveTo(mouse.x, mouse.y);
        ctx.lineTo(p.x, p.y);
        ctx.strokeStyle = `rgba(0,255,224,${(1 - d / 150) * 0.12})`;
        ctx.lineWidth   = 0.6;
        ctx.stroke();
      }
    });
  }

  function loop() {
    ctx.clearRect(0, 0, W, H);
    drawConnections();
    drawMouseConnections();
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(loop);
  }
  loop();
})();
