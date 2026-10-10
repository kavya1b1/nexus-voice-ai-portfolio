// ── Certificate preview modal (Google Drive embed) ──
(function () {
  const modal = document.getElementById('certModal');
  const frame = document.getElementById('certFrame');
  const open  = document.getElementById('certOpen');
  const close = document.getElementById('certClose');
  if (!modal) return;

  function hide() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    frame.src = 'about:blank';
  }

  document.querySelectorAll('.cert-pill[data-cert]').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const id = a.dataset.cert;
      frame.src = 'https://drive.google.com/file/d/' + id + '/preview';
      open.href = a.href;
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    });
  });

  close.addEventListener('click', hide);
  modal.addEventListener('click', (e) => { if (e.target === modal) hide(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
})();
