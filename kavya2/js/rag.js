/* ═══════════════════════════════════════════════════════
   Tiny local RAG engine — BM25 retrieval, no network, no API
   ═══════════════════════════════════════════════════════ */
(function (root) {
  const STOP = new Set(('a an the is are was were be been am do does did of to in on at for with and or but if so as by from ' +
    'about tell me you your her she he his hers kavya kavyas can could would please what whats which who whom how when where we ' +
    'it its this that these those i my we us any some give show explain describe also just really very much there them they ' +
    'know like want wanna get got let lets ok okay yes').split(/\s+/));

  // Query-side synonyms (applied to raw words, before stemming)
  const SYN = {
    college: ['education', 'vit'], university: ['education', 'vit'], degree: ['education'], studies: ['education'],
    study: ['education'], studying: ['education'], graduate: ['education'], graduating: ['education'],
    grade: ['cgpa'], grades: ['cgpa'], gpa: ['cgpa'], marks: ['cgpa'], percentage: ['cgpa'],
    mail: ['email'], reach: ['contact'], connect: ['contact'], phone: ['contact'], number: ['contact'],
    hire: ['hire'], hiring: ['hire'], recruit: ['availability'],
    job: ['availability', 'internship'], jobs: ['availability', 'internship'], employment: ['availability'],
    available: ['availability'], intern: ['internship'], interns: ['internship'], freelance: ['availability'],
    technologies: ['skills', 'stack'], technology: ['skills', 'stack'], tech: ['skills', 'stack'], tools: ['skills', 'tools'],
    expertise: ['skills'], good: ['skills'],
    prize: ['achievements'], award: ['achievements'], awards: ['achievements'], win: ['achievements'], won: ['achievements'],
    winner: ['achievements'], rank: ['sih', 'achievements'], honors: ['achievements'], accomplishments: ['achievements'],
    leader: ['lead', 'gdgc'], leadership: ['lead', 'gdgc'], club: ['gdgc'], google: ['gdgc'],
    cv: ['resume'], certificate: ['certifications'], certificates: ['certifications'], certified: ['certifications'],
    certification: ['certifications'], course: ['certifications'], courses: ['certifications'],
    llm: ['generative', 'llm'], llms: ['generative', 'llm'], genai: ['generative', 'genai'], gpt: ['generative'],
    agent: ['agentic'], agents: ['agentic'], chatbot: ['assistant'], bot: ['assistant'],
    app: ['projects'], apps: ['projects'],
    extension: ['chrome', 'n8n'], moderation: ['safesphere'], proposal: ['proposal'], cold: ['coldmail']
  };

  function stem(w) {
    if (w.length > 4 && w.endsWith('ies')) return w.slice(0, -3) + 'y';
    if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss') && !w.endsWith('us')) w = w.slice(0, -1);
    if (w.length > 6 && w.endsWith('ing')) w = w.slice(0, -3);
    return w;
  }

  function rawWords(text) {
    return String(text).toLowerCase().replace(/c\+\+/g, 'cpp').replace(/n8n/g, 'n8n').replace(/[^a-z0-9\s.-]/g, ' ')
      .replace(/\.(?=\s|$)/g, ' ').split(/[\s]+/).map(w => w.replace(/^[.-]+|[.-]+$/g, '')).filter(Boolean);
  }

  function tokenizeDoc(text) {
    return rawWords(text).filter(w => w.length > 1 && !STOP.has(w)).map(stem);
  }

  // Returns groups: one group per meaningful word the user said (word + its synonyms)
  function queryGroups(text) {
    const groups = [];
    rawWords(text).forEach(w => {
      if (w.length < 2 || STOP.has(w)) return;
      const g = [stem(w)];
      if (SYN[w]) SYN[w].forEach(x => g.push(stem(x)));
      groups.push(g);
    });
    return groups;
  }
  function tokenizeQuery(text) {
    return [].concat.apply([], queryGroups(text));
  }

  function build(kb) {
    const docs = kb.map(c => {
      const toks = []
        .concat(tokenizeDoc(c.text))
        .concat(tokenizeDoc(c.keywords || ''), tokenizeDoc(c.keywords || ''))
        .concat(tokenizeDoc(c.title), tokenizeDoc(c.title), tokenizeDoc(c.title));
      const tf = {};
      toks.forEach(t => { tf[t] = (tf[t] || 0) + 1; });
      return { chunk: c, tf, len: toks.length };
    });
    const N = docs.length;
    const avgdl = docs.reduce((s, d) => s + d.len, 0) / N;
    const df = {};
    docs.forEach(d => Object.keys(d.tf).forEach(t => { df[t] = (df[t] || 0) + 1; }));
    return { docs, N, avgdl, df, byId: Object.fromEntries(kb.map(c => [c.id, c])) };
  }

  function search(index, query, k) {
    const groups = queryGroups(query);
    const q = [].concat.apply([], groups);
    if (!q.length) return [];
    const k1 = 1.4, b = 0.6;
    const res = index.docs.map(d => {
      let score = 0;
      const seen = new Set();
      q.forEach(t => {
        const f = d.tf[t];
        if (!f) return;
        const idf = Math.log(1 + (index.N - index.df[t] + 0.5) / (index.df[t] + 0.5));
        const w = seen.has(t) ? 0.35 : 1; // repeated query terms count less
        seen.add(t);
        score += w * idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * d.len / index.avgdl));
      });
      const matched = groups.filter(g => g.some(t => d.tf[t])).length;
      return { chunk: d.chunk, score, coverage: matched / groups.length };
    }).filter(r => r.score > 0).sort((a, b) => b.score - a.score);
    return res.slice(0, k || 3);
  }

  // Is the best result trustworthy enough to answer from?
  function confident(r) {
    return !!r && (r.coverage >= 0.5 || r.score >= 8);
  }

  // Make text sound natural for text-to-speech
  const PRON = [
    [/kavya1b1@gmail\.com/gi, 'kavya one b one at gmail dot com'],
    [/its-kavya-gupta/gi, 'its kavya gupta'],
    [/kavya1b1/gi, 'kavya one b one'],
    [/SafeSphere\.AI/gi, 'SafeSphere dot A I'],
    [/Bytez\.js/gi, 'Bytez J S'],
    [/Node\.js/gi, 'Node J S'],
    [/C\+\+/g, 'C plus plus'],
    [/R&D/g, 'R and D'],
    [/\bn8n\b/gi, 'N eight N'],
    [/\bDP-900\b/g, 'D P nine hundred'],
    [/(\d)\+/g, '$1 plus'],
    [/(\d)%/g, '$1 percent'],
    [/&/g, ' and '],
    [/\bGDGC\b/g, 'G D G C'], [/\bVIT\b/g, 'V I T'], [/\bCGPA\b/g, 'C G P A'], [/\bSIH\b/g, 'S I H'],
    [/\bRAG\b/g, 'R A G'], [/\bLLMs?\b/g, 'L L Ms'], [/\bFastAPI\b/g, 'Fast A P I'], [/\bAPIs?\b/g, 'A P Is'],
    [/\bSQL\b/g, 'sequel'], [/\bSQLite\b/g, 'sequel lite'], [/\bPDFs?\b/g, 'P D Fs'], [/\bSMTP\b/g, 'S M T P'],
    [/\bREST\b/g, 'rest'], [/\bSaaS\b/g, 'sass'], [/\bOCI\b/g, 'O C I'], [/\bML\b/g, 'M L'], [/\bai\b/gi, 'A I'],
    [/\bUI\b/g, 'U I'], [/\bJSON\b/g, 'jason'], [/\bB\.Tech\b/gi, 'B Tech'], [/\bCSE\b/g, 'C S E'], [/\bWiCyS\b/g, 'Wi Sys'],
    [/\bIBM\b/g, 'I B M'], [/\bGenAI\b/g, 'Gen A I'], [/\bGroq\b/g, 'Grok'], [/\bPostgreSQL\b/g, 'Postgres Q L'],
    [/\bMongoDB\b/g, 'Mongo D B'], [/\bChromaDB\b/g, 'Chroma D B'], [/\bLangGraph\b/g, 'Lang Graph'],
    [/[→↗]/g, ' '], [/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, ' ']
  ];
  function toSpeech(text) {
    let t = String(text);
    PRON.forEach(([re, rep]) => { t = t.replace(re, rep); });
    return t.replace(/\s+/g, ' ').replace(/\s+([.,!?;:])/g, '$1').trim();
  }

  function splitSentences(text) {
    const m = String(text).match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g);
    return (m || [text]).map(s => s.trim()).filter(Boolean);
  }

  const API = { build, search, confident, tokenizeQuery, toSpeech, splitSentences };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.KavyaRAG = API;
})(typeof window !== 'undefined' ? window : globalThis);
