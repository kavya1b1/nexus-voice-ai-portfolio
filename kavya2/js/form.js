// ── Contact Form → delivers to email via FormSubmit ──
(function () {
  const form    = document.getElementById('contactForm');
  const success = document.getElementById('formSuccess');
  const error   = document.getElementById('formError');
  if (!form) return;

  const ENDPOINT = 'https://formsubmit.co/ajax/kavya1b1@gmail.com';

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn  = form.querySelector('button[type="submit"]');
    const span = btn.querySelector('span');
    const data = new FormData(form);

    // Basic validation
    if (!data.get('name').trim() || !data.get('email').trim() || !data.get('message').trim()) {
      error.textContent = 'Please fill in your name, email and message.';
      error.classList.add('show');
      setTimeout(() => error.classList.remove('show'), 4000);
      return;
    }

    // Email subject: "From Portfolio: <their subject>"
    const userSubject = (data.get('subject') || '').trim();
    data.set('_subject', userSubject ? `From Portfolio: ${userSubject}` : 'From Portfolio: New message');
    data.set('_template', 'table');
    data.set('_captcha', 'false');
    data.set('_replyto', data.get('email'));

    btn.disabled = true;
    span.textContent = 'Sending…';
    error.classList.remove('show');

    try {
      const res  = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
        body: data
      });
      const json = await res.json();
      if (!res.ok || json.success === 'false' || json.success === false) throw new Error('send failed');

      form.reset();
      success.classList.add('show');
      setTimeout(() => success.classList.remove('show'), 5000);
    } catch (err) {
      error.textContent = 'Something went wrong. Please email me directly at kavya1b1@gmail.com';
      error.classList.add('show');
      setTimeout(() => error.classList.remove('show'), 6000);
    } finally {
      btn.disabled = false;
      span.textContent = 'Send Message';
    }
  });
})();
