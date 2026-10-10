/* ═══════════════════════════════════════════════════════════════
   Voice assistant for the portfolio — 100% free, runs in the browser
   • Speech in  : browser SpeechRecognition (Chrome / Edge / Safari)
   • Knowledge  : local BM25 RAG over js/kb.js
   • Speech out : browser speechSynthesis
   • Optional   : "Smart mode" = small LLM running locally via WebGPU
   • Optional   : live GitHub repo lookup (free public API, no key)
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const KB = window.KAVYA_KB, R = window.KavyaRAG;
  if (!KB || !R) return;

  const CONFIG = {
    // Backend (voice-agent/ folder). Override before this script loads:  window.VOICE_AGENT_API = 'https://…'
    apiBase: (window.VOICE_AGENT_API || 'http://localhost:8000').replace(/\/$/, ''),
    githubUser: 'kavya1b1',
    recogLang: 'en-IN',                 // speech-recognition language
    smartModel: 'Llama-3.2-1B-Instruct-q4f16_1-MLC',
    smartLib: 'https://esm.run/@mlc-ai/web-llm'
  };
  const DEFAULT_CHIPS = ['Give me a quick intro', 'What can I ask?', 'Tell me about his projects', 'How can I contact him?', 'Is he open to internships?'];
  const SYSTEM_PROMPT = "You are the voice assistant on Kavya Gupta's portfolio website. Answer the visitor's question using ONLY the context provided. " +
    "Reply in at most three short, natural sentences suitable for speaking aloud. No markdown, no lists, no emojis. Refer to Kavya in the third person. " +
    "If the answer is not in the context, say you don't have that information and suggest using the contact form.";

  const index = R.build(KB);
  const byId = index.byId;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis;

  const S = { open: false, introduced: false, muted: false, busy: false, listening: false, speaking: false,
              last: null, lastResults: [], used: new Set(), smart: false, engine: null, smartLoading: false, rec: null,
              agent: { online: false, llm: false, stt: false, sttReady: false, model: '' }, history: [], streaming: false, pending: 0, recStop: null, streamToken: 0 };

  /* ── DOM ───────────────────────────────────────────── */
  const MIC_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4"/></svg>';
  const SEND_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg>';
  const webgpu = !!navigator.gpu;

  const root = document.createElement('div');
  root.innerHTML =
    '<button class="va-fab" id="vaFab" type="button" aria-label="Talk to Kavya\'s AI assistant">' + MIC_SVG + '<span>Ask my AI</span></button>' +
    '<div class="va-nudge" id="vaNudge">👋 Prefer to listen? Ask my AI assistant about Kavya.</div>' +
    '<section class="va-panel" id="vaPanel" role="dialog" aria-label="Kavya\'s AI voice assistant">' +
      '<header class="va-head">' +
        '<div class="va-avatar">KG</div>' +
        '<div class="va-title"><b>Kavya\'s AI Assistant <span class="va-badge" id="vaBadge">Offline mode</span></b><span class="va-status" id="vaStatus">Tap the mic and ask anything</span></div>' +
        '<button class="va-icon-btn" id="vaMute" type="button" title="Mute / unmute voice" aria-label="Mute voice">🔊</button>' +
        '<button class="va-icon-btn" id="vaClose" type="button" title="Close" aria-label="Close assistant">✕</button>' +
      '</header>' +
      '<label class="va-smart' + (webgpu ? '' : ' disabled') + '" title="' + (webgpu ? 'Runs a small AI model fully on your device' : 'Needs a browser with WebGPU (recent Chrome / Edge)') + '">' +
        '<input type="checkbox" id="vaSmart"' + (webgpu ? '' : ' disabled') + '> Smart mode <small>' + (webgpu ? 'local LLM · one-time ~0.8 GB download' : '(needs WebGPU)') + '</small>' +
      '</label>' +
      '<div class="va-log" id="vaLog" aria-live="polite"></div>' +
      '<div class="va-chips" id="vaChips"></div>' +
      '<div class="va-input">' +
        '<button class="va-mic" id="vaMic" type="button" aria-label="Tap to speak">' + MIC_SVG + '</button>' +
        '<input class="va-text" id="vaText" type="text" placeholder="…or type your question" autocomplete="off" />' +
        '<button class="va-send" id="vaSend" type="button" aria-label="Send">' + SEND_SVG + '</button>' +
      '</div>' +
    '</section>';
  document.body.appendChild(root);

  const $ = id => document.getElementById(id);
  const fab = $('vaFab'), nudge = $('vaNudge'), panel = $('vaPanel'), log = $('vaLog'), chips = $('vaChips'),
        statusEl = $('vaStatus'), badge = $('vaBadge'), smartRow = root.querySelector('.va-smart'), mic = $('vaMic'), text = $('vaText'), muteBtn = $('vaMute'), smartBox = $('vaSmart');

  const heroVoiceLaunch = $('heroVoiceLaunch');
  if (heroVoiceLaunch) heroVoiceLaunch.addEventListener('click', () => fab.click());

  /* ── UI helpers ────────────────────────────────────── */
  function setStatus(t) { statusEl.textContent = t; }
  function setMode(mode) { // idle | listening | speaking | thinking
    panel.classList.toggle('is-listening', mode === 'listening');
    panel.classList.toggle('is-speaking', mode === 'speaking');
    const labels = { idle: 'Tap the mic and ask anything', listening: 'Listening…', speaking: 'Speaking… (tap mic to interrupt)', thinking: 'Thinking…' };
    setStatus(labels[mode] || '');
  }
  function renderLinks(el, links) {
    if (!links || !links.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'va-links';
    links.forEach(l => {
      const a = document.createElement('a');
      a.textContent = l.label; a.href = l.href;
      if (/^https?:|^mailto:/.test(l.href)) { a.target = '_blank'; a.rel = 'noopener'; }
      else if (l.href.startsWith('#')) a.addEventListener('click', () => { if (window.innerWidth <= 600) closePanel(); });
      wrap.appendChild(a);
    });
    el.appendChild(wrap);
  }
  function addMsg(role, msg, links) {
    const el = document.createElement('div');
    el.className = 'va-msg ' + role;
    el.body = document.createElement('span');
    el.body.textContent = msg;
    el.appendChild(el.body);
    renderLinks(el, links);
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }
  function addTrace(el, trace, sources, ms, mode) {
    if (!trace.length) return;
    const d = document.createElement('details');
    d.className = 'va-trace';
    const sum = document.createElement('summary');
    sum.textContent = 'How I answered' + (ms ? ' · ' + (ms / 1000).toFixed(1) + 's' : '') + (mode ? ' · ' + mode : '');
    d.appendChild(sum);
    const ol = document.createElement('ol');
    trace.forEach(t => { const li = document.createElement('li'); const b = document.createElement('b'); b.textContent = t.node; li.appendChild(b); li.appendChild(document.createTextNode(' ' + t.detail)); ol.appendChild(li); });
    d.appendChild(ol);
    if (sources && sources.length) {
      const p = document.createElement('div'); p.className = 'va-src';
      p.textContent = 'Sources: ' + sources.map((x, i) => '[' + (i + 1) + '] ' + x.title + ' · ' + x.section + ' (sim ' + x.dense.toFixed(2) + ')').join('   ');
      d.appendChild(p);
    }
    el.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  function showChips(list) {
    chips.innerHTML = '';
    (list && list.length ? list : DEFAULT_CHIPS).slice(0, 4).forEach(q => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'va-chip'; b.textContent = q;
      b.addEventListener('click', () => ask(q));
      chips.appendChild(b);
    });
  }

  /* ── Text to speech ────────────────────────────────── */
  let voice = null;
  function pickVoice() {
    if (!synth) return null;
    const vs = synth.getVoices();
    if (!vs.length) return null;
    const rank = v => (v.lang === 'en-IN' ? 40 : v.lang === 'en-GB' ? 25 : v.lang === 'en-US' ? 20 : v.lang.startsWith('en') ? 10 : 0) +
                      (/google|natural|online|neural/i.test(v.name) ? 15 : 0) + (/female|zira|samantha|heera|veena|aria|jenny/i.test(v.name) ? 3 : 0);
    return vs.slice().sort((a, b) => rank(b) - rank(a))[0];
  }
  if (synth) { synth.onvoiceschanged = () => { voice = pickVoice(); }; voice = pickVoice(); }

  function stopSpeaking() {
    S.speakToken++;
    S.streaming = false; S.pending = 0;
    if (synth) synth.cancel();
    if (S.speaking) { S.speaking = false; if (!S.listening && !S.busy) setMode('idle'); }
  }
  S.speakToken = 0;
  function mkUtterance(p) {
    const u = new SpeechSynthesisUtterance(p);
    if (!voice) voice = pickVoice();
    if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = 'en-IN';
    u.rate = 1.02; u.pitch = 1;
    return u;
  }
  function speak(msg) {            // speak a complete message
    if (!synth || S.muted) return;
    synth.cancel();
    const token = ++S.speakToken;
    S.streaming = false;
    const parts = R.splitSentences(R.toSpeech(msg.replace(/\[\d+\]/g, '')));
    if (!parts.length) return;
    S.speaking = true; setMode('speaking');
    parts.forEach((p, i) => {
      const u = mkUtterance(p);
      const done = () => { if (token === S.speakToken && i === parts.length - 1) { S.speaking = false; if (!S.listening && !S.busy) setMode('idle'); } };
      u.onend = done; u.onerror = done;
      synth.speak(u);
    });
  }
  // Streaming TTS: speak each sentence as soon as the LLM has produced it
  function speakStreamBegin() {
    if (!synth || S.muted) return;
    synth.cancel(); S.streamToken = ++S.speakToken; S.pending = 0; S.streaming = true; S.speaking = true; setMode('speaking');
  }
  function speakChunk(txt) {
    if (!synth || S.muted || !S.streaming) return;
    const t = R.toSpeech(txt.replace(/\[\d+\]/g, ''));
    if (!t.trim()) return;
    const token = S.streamToken, u = mkUtterance(t);
    S.pending++;
    const done = () => { if (token !== S.speakToken) return; S.pending--; if (S.pending <= 0 && !S.streaming) { S.speaking = false; if (!S.listening && !S.busy) setMode('idle'); } };
    u.onend = done; u.onerror = done;
    synth.speak(u);
  }
  function speakStreamEnd() {
    S.streaming = false;
    if (S.pending <= 0 && S.speaking) { S.speaking = false; if (!S.listening && !S.busy) setMode('idle'); }
  }

  /* ── Speech to text ────────────────────────────────── */
  function listen() {
    if (S.listening) { if (S.recStop) S.recStop(); else { try { S.rec.stop(); } catch (e) {} } return; }
    stopSpeaking();
    if (S.agent.online && S.agent.stt && !S.agent.sttReady) probeBackend();   // model may have finished loading by now
    if (S.agent.online && S.agent.sttReady && window.MediaRecorder && navigator.mediaDevices) return listenLocalWhisper();
    if (!SR) { setStatus('Voice input needs Chrome, Edge or Safari — please type instead'); text.focus(); return; }
    const rec = new SR();
    S.rec = rec;
    rec.lang = CONFIG.recogLang; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    let finalText = '', errKind = '';
    rec.onstart = () => { S.listening = true; setMode('listening'); text.value = ''; };
    rec.onresult = e => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      text.value = (finalText + ' ' + interim).trim();
    };
    rec.onerror = e => { errKind = e.error || 'error'; };
    rec.onend = () => {
      S.listening = false;
      const q = (finalText || text.value).trim();
      if (errKind === 'not-allowed' || errKind === 'service-not-allowed') { setStatus('Microphone blocked — allow mic access, or type your question'); return; }
      if (errKind === 'audio-capture') { setStatus('No microphone found — please type your question'); return; }
      if (errKind === 'network') { setStatus('Speech service unreachable — please type your question'); return; }
      if (q) { text.value = ''; ask(q); }
      else { setMode('idle'); setStatus("Didn't catch that — tap the mic and try again"); }
    };
    try { rec.start(); } catch (e) { setMode('idle'); }
  }

  /* ── Local speech-to-text via the backend (faster-whisper) ── */
  async function listenLocalWhisper() {
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { setStatus('Microphone blocked — allow mic access, or type your question'); return; }
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
    // simple voice-activity detection: stop 1.4 s after the visitor stops talking
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC(), src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser();
    an.fftSize = 1024; src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    let heard = false, silentSince = 0;
    const t0 = Date.now();
    const stop = () => { if (rec.state !== 'inactive') rec.stop(); };
    const timer = setInterval(() => {
      an.getByteTimeDomainData(buf);
      let sum = 0; for (let i = 0; i < buf.length; i++) { const d = (buf[i] - 128) / 128; sum += d * d; }
      const rms = Math.sqrt(sum / buf.length), now = Date.now();
      if (rms > 0.04) { heard = true; silentSince = 0; }
      else if (heard) { if (!silentSince) silentSince = now; else if (now - silentSince > 1400) stop(); }
      if (now - t0 > 15000) stop();
    }, 100);
    S.recStop = stop;
    rec.onstart = () => { S.listening = true; setMode('listening'); setStatus('Listening… tap the mic to send'); text.value = ''; };
    rec.onstop = async () => {
      clearInterval(timer); stream.getTracks().forEach(t => t.stop()); try { ctx.close(); } catch (e) {}
      S.listening = false; S.recStop = null;
      if (!heard) { setMode('idle'); setStatus("Didn't hear anything — tap the mic and try again"); return; }
      setMode('thinking'); setStatus('Transcribing locally…');
      const ctl = new AbortController(), timer2 = setTimeout(() => ctl.abort(), 45000);
      try {
        const fd = new FormData();
        fd.append('audio', new Blob(chunks, { type: rec.mimeType || 'audio/webm' }), 'speech.webm');
        const r = await fetch(CONFIG.apiBase + '/transcribe', { method: 'POST', body: fd, signal: ctl.signal });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const out = await r.json();
        if ((out.text || '').trim()) ask(out.text.trim());
        else { setMode('idle'); setStatus("Didn't catch that — tap the mic and try again"); }
      } catch (e) {
        console.warn('Local transcription failed:', e);
        S.agent.sttReady = false;     // use the browser's speech recognition from now on
        setMode('idle');
        setStatus(SR ? 'Local speech-to-text unavailable — switched to browser recognition. Tap the mic again.' : 'Local speech-to-text unavailable — please type your question');
      } finally { clearTimeout(timer2); }
    };
    rec.start();
  }

  /* ── Optional: local LLM ("Smart mode") ────────────── */
  async function enableSmart() {
    if (S.engine) { S.smart = true; return; }
    if (S.smartLoading) return;
    S.smartLoading = true; smartBox.disabled = true;
    try {
      setStatus('Loading local AI model… (first time only)');
      const webllm = await import(CONFIG.smartLib);
      S.engine = await webllm.CreateMLCEngine(CONFIG.smartModel, {
        initProgressCallback: p => setStatus('Loading local AI… ' + Math.round((p.progress || 0) * 100) + '%')
      });
      S.smart = true;
      addMsg('bot', 'Smart mode is on. I will now phrase answers with a small AI model running on your device.');
      setMode('idle');
    } catch (err) {
      console.warn('Smart mode failed:', err);
      S.smart = false; smartBox.checked = false;
      addMsg('bot', "I couldn't start Smart mode on this device, so I'll keep answering from my knowledge base.");
      setMode('idle');
    } finally { S.smartLoading = false; smartBox.disabled = !webgpu; }
  }
  async function smartAnswer(q, chunks) {
    const ctx = chunks.map((c, i) => '[' + (i + 1) + '] ' + c.title + ': ' + c.text).join('\n');
    const out = await S.engine.chat.completions.create({
      messages: [{ role: 'system', content: SYSTEM_PROMPT }, { role: 'user', content: 'Context:\n' + ctx + '\n\nQuestion: ' + q }],
      temperature: 0.2, max_tokens: 150
    });
    return (out.choices[0].message.content || '').trim();
  }

  /* ── Optional: live GitHub lookup (free public API) ── */
  async function githubLive() {
    try {
      const r = await fetch('https://api.github.com/users/' + CONFIG.githubUser + '/repos?sort=updated&per_page=8', { headers: { Accept: 'application/vnd.github+json' } });
      if (!r.ok) throw new Error('gh ' + r.status);
      const repos = (await r.json()).filter(x => !x.fork).slice(0, 4);
      if (!repos.length) throw new Error('empty');
      const names = repos.map(x => x.name.replace(/[-_.]+/g, ' ').trim());
      const list = names.length > 1 ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1] : names[0];
      return { text: "Fresh from GitHub: Kavya's most recently updated public repositories are " + list + '.',
               links: repos.map(x => ({ label: x.name + ' ↗', href: x.html_url })), chips: ['Tell me about his projects', 'What are his skills?'] };
    } catch (e) {
      return { text: "I couldn't reach GitHub right now, but you can see all of Kavya's code at github.com slash " + CONFIG.githubUser + '.',
               links: [{ label: 'GitHub ↗', href: 'https://github.com/' + CONFIG.githubUser }] };
    }
  }

  /* ── Brain: intents + retrieval ────────────────────── */
  const RE = {
    greet: /^(hi+|hello+|hey+|hola|namaste|yo|good\s(morning|afternoon|evening))\b[\s!.,]*$/i,
    thanks: /^(thanks|thank you|thx|great|awesome|cool|nice|perfect|wonderful|got it|ok|okay)(\s+(a lot|so much|kavya))?\W*$/i,
    bye: /^(bye|goodbye|see you|that'?s all|no thanks|nothing else|quit|exit)\b/i,
    stop: /^(stop|quiet|shut up|be quiet|pause)\W*$/i,
    more: /^(tell me more|more|more details?|go on|continue|and|what else|anything else|elaborate)\W*$/i,
    intro: /\b(intro(duce|duction)?|brief|overview|summary|summari[sz]e)\b|who('?s| is) kavya|^(tell me )?about (kavya|him|yourself|you|the person)\W*$/i,
    github: /(latest|recent|newest|updated).*(repo|repos|repositories|github)|github (repos|repositories|activity)/i,
    contact: /\b(e-?mail (id|address)|mail id|(his|your|the) e-?mail\b|phone|linkedin|how (can|do|could) i (contact|reach|get in touch)|contact (him|details|info|kavya)|reach (him|out))/i,
    resume: /\b(resume|cv|curriculum vitae)\b/i,
    who: /(who|what) are you|what can (you|i) (do|ask|say)|what should i ask|how do you work|are you (an? )?(ai|bot|human|real)|your name|^help\W*$/i,
    pron: /\b(it|its|that|this|those|these|that one|this one|the same)\b/i
  };

  function chunkLinks(c) { return c.links || []; }

  async function think(q) {
    const t = q.trim();
    if (RE.stop.test(t)) { stopSpeaking(); return { silent: true }; }
    if (RE.greet.test(t)) return { text: "Hello! I'm Kavya's AI assistant. Ask me about his projects, skills, achievements, or say 'give me a quick intro'." , chips: DEFAULT_CHIPS };
    if (RE.thanks.test(t)) return { text: "You're welcome! Anything else you'd like to know about Kavya?", chips: DEFAULT_CHIPS };
    if (RE.bye.test(t)) return { text: "Thanks for stopping by! If you'd like to talk to Kavya, the contact form is at the bottom of the page.", links: [{ label: 'Contact ↗', href: '#contact' }] };
    if (RE.github.test(t)) return await githubLive();
    if (RE.more.test(t) && S.last) {
      const skip = c => S.used.has(c.id) || (S.last.id.indexOf('proj-') === 0 && c.id === 'projects');
      const next = S.lastResults.map(r => r.chunk).find(c => !skip(c)) ||
                   KB.find(c => c.group === S.last.group && !skip(c));
      if (next) return fromChunk(next, [next]);
      return { text: "That's everything I have on that topic. You could ask about his projects, skills or how to contact him.", chips: DEFAULT_CHIPS };
    }
    if (RE.contact.test(t)) return fromChunk(byId.contact, [byId.contact]);
    if (RE.resume.test(t)) return fromChunk(byId.resume, [byId.resume]);
    if (RE.who.test(t)) return fromChunk(byId.assistant, [byId.assistant]);
    if (RE.intro.test(t)) return fromChunk(byId.intro, [byId.intro]);

    // Retrieval (with simple follow-up handling for "it / that / this")
    let results = R.search(index, t, 3);
    if (S.last && (RE.pron.test(t) || !R.confident(results[0]))) {
      const aug = R.search(index, t + ' ' + S.last.title + ' ' + S.last.keywords.split(' ').slice(0, 6).join(' '), 3);
      const lastHit = aug.find(r => r.chunk.id === S.last.id);
      if (RE.pron.test(t) && lastHit) results = [lastHit].concat(aug.filter(r => r !== lastHit));
      else if (!R.confident(results[0]) && R.confident(aug[0]) && RE.pron.test(t)) results = aug;
    }
    if (!R.confident(results[0])) {
      return { text: "I don't have that in my knowledge base. I can tell you about Kavya's projects, skills, certifications, achievements, or how to reach him. You can also send him a message through the contact form.",
               links: [{ label: 'Contact form ↗', href: '#contact' }], chips: DEFAULT_CHIPS, miss: true };
    }
    const top = results[0].chunk;
    return fromChunk(top, results.map(r => r.chunk), true, t);
  }

  async function fromChunk(chunk, ctxChunks, allowSmart, question) {
    let answer = chunk.text;
    if (allowSmart && S.smart && S.engine) {
      try { const s = await smartAnswer(question, ctxChunks); if (s) answer = s; } catch (e) { console.warn(e); }
    }
    S.last = chunk; S.used.add(chunk.id);
    S.lastResults = ctxChunks.map(c => ({ chunk: c }));
    return { text: answer, links: chunkLinks(chunk), chips: chunk.followups };
  }

  /* ── Backend agent (SSE streaming) ─────────────────── */
  async function* sseEvents(res) {
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i + 2);
        let event = 'message', data = '';
        block.split('\n').forEach(l => { if (l.startsWith('event: ')) event = l.slice(7); else if (l.startsWith('data: ')) data += l.slice(6); });
        if (data) yield { event, data: JSON.parse(data) };
      }
    }
  }
  function takeSentences(state) {            // pull completed sentences out of the token buffer
    let m;
    while ((m = /[.!?]\s/.exec(state.buf))) {
      const cut = m.index + 1;
      speakChunk(state.buf.slice(0, cut));
      state.buf = state.buf.slice(cut).trimStart();
    }
  }
  function updateBadge() {
    const a = S.agent;
    badge.textContent = !a.online ? 'Offline mode' : a.llm ? 'Agent · local LLM' : 'Agent · retrieval only';
    badge.classList.toggle('on', a.online);
    if (smartRow) smartRow.style.display = a.online ? 'none' : '';
  }
  async function probeBackend() {
    try {
      const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 1500);
      const r = await fetch(CONFIG.apiBase + '/health', { signal: ctl.signal });
      clearTimeout(timer);
      const j = await r.json();
      S.agent = { online: r.ok && j.status === 'ok', llm: !!j.llm, stt: !!j.stt, sttReady: !!j.stt_ready, model: j.model || '' };
    } catch (e) { S.agent = { online: false, llm: false, stt: false, sttReady: false, model: '' }; }
    updateBadge();
  }

  async function askAgent(q) {
    const res = await fetch(CONFIG.apiBase + '/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: q, history: S.history.slice(-6) })
    });
    if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);
    const msgEl = addMsg('bot', '');
    const st = { buf: '', text: '', trace: [], sources: [], links: [], got: false };
    speakStreamBegin();
    try {
      for await (const { event, data } of sseEvents(res)) {
        if (event === 'trace') { st.trace.push(data); setStatus(data.node + ': ' + data.detail.slice(0, 60)); }
        else if (event === 'sources') st.sources = data;
        else if (event === 'links') st.links = data;
        else if (event === 'token') {
          st.got = true; st.text += data; st.buf += data;
          msgEl.body.textContent = st.text; log.scrollTop = log.scrollHeight;
          takeSentences(st);
        } else if (event === 'replace') {
          st.text = data; st.buf = '';
          msgEl.body.textContent = data;
          stopSpeaking(); speakStreamBegin(); speakChunk(data);
        } else if (event === 'done') {
          if (st.buf.trim()) speakChunk(st.buf);
          st.buf = '';
          st.done = data;
        }
      }
    } catch (e) {
      if (!st.got) { msgEl.remove(); speakStreamEnd(); throw e; }
    }
    speakStreamEnd();
    renderLinks(msgEl, st.links);
    addTrace(msgEl, st.trace, st.sources, st.done && st.done.ms, st.done && st.done.mode);
    if (st.done && st.done.relevant) S.history.push({ role: 'user', content: q }, { role: 'assistant', content: st.text.replace(/\[\d+\]/g, '').slice(0, 600) });
    const chunk = KB.find(c => st.sources[0] && c.title === st.sources[0].title) || null;
    if (chunk) { S.last = chunk; S.used.add(chunk.id); }
    showChips(chunk ? chunk.followups : null);
  }

  async function askLocal(q) {
    const wait = S.smart ? addMsg('bot thinking', 'Thinking…') : null;
    const reply = await think(q);
    if (wait) wait.remove();
    if (reply.silent) return;
    addMsg('bot', reply.text, reply.links);
    showChips(reply.chips);
    S.history.push({ role: 'user', content: q }, { role: 'assistant', content: reply.text });
    S.busy = false;
    speak(reply.text);
  }

  async function ask(q) {
    q = (q || '').trim();
    if (!q || S.busy) return;
    stopSpeaking();
    addMsg('user', q);
    if (RE.stop.test(q)) { setMode('idle'); return; }
    S.busy = true; setMode('thinking');
    try {
      if (S.agent.online) {
        try { await askAgent(q); }
        catch (e) {
          console.warn('Agent backend failed, using offline mode:', e);
          S.agent.online = false; updateBadge();
          await askLocal(q);
        }
      } else await askLocal(q);
    } catch (e) {
      console.error(e);
      addMsg('bot', 'Sorry, something went wrong. Please try again.');
    } finally {
      S.busy = false;
      if (!S.speaking && !S.listening) setMode('idle');
    }
  }

  /* ── Open / close ──────────────────────────────────── */
  function openPanel() {
    S.open = true; panel.classList.add('open'); fab.classList.add('hidden'); nudge.classList.remove('show');
    probeBackend();
    if (!S.introduced) {
      S.introduced = true;
      const intro = byId.intro;
      const msg = "Hi! I'm Kavya's AI assistant. Here's a quick intro. " + intro.text + " Ask me anything about him — tap the mic and speak, or type your question.";
      S.last = intro; S.used.add(intro.id);
      addMsg('bot', msg, intro.links);
      showChips(intro.followups);
      speak(msg);                    // runs inside the click → browsers allow it
      if (!SR) setStatus('Voice input needs Chrome, Edge or Safari — you can still type');
    }
    setTimeout(() => text.focus({ preventScroll: true }), 50);
  }
  function closePanel() {
    S.open = false; panel.classList.remove('open'); fab.classList.remove('hidden');
    stopSpeaking(); if (S.listening) { try { S.rec.abort(); } catch (e) {} }
  }

  fab.addEventListener('click', openPanel);
  $('vaClose').addEventListener('click', closePanel);
  mic.addEventListener('click', listen);
  $('vaSend').addEventListener('click', () => { const v = text.value; text.value = ''; ask(v); });
  text.addEventListener('keydown', e => { if (e.key === 'Enter') { const v = text.value; text.value = ''; ask(v); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && S.open) closePanel(); });
  window.addEventListener('beforeunload', () => { if (synth) synth.cancel(); });
  muteBtn.addEventListener('click', () => {
    S.muted = !S.muted;
    muteBtn.textContent = S.muted ? '🔇' : '🔊'; muteBtn.classList.toggle('off', S.muted);
    if (S.muted) stopSpeaking();
  });
  smartBox.addEventListener('change', () => { if (smartBox.checked) enableSmart(); else S.smart = false; });

  // Gentle one-time nudge
  setTimeout(() => { if (!S.open) { nudge.classList.add('show'); setTimeout(() => nudge.classList.remove('show'), 7000); } }, 5000);
  nudge.addEventListener('click', openPanel);
})();
