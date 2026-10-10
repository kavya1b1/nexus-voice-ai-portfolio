/* ═══════════════════════════════════════════════════════════════
   KNOWLEDGE BASE for the voice assistant  (this is the "RAG" data)
   ───────────────────────────────────────────────────────────────
   • Add / edit entries freely — the assistant re-indexes on load.
   • text      → what the assistant says (write it the way you'd speak)
   • keywords  → extra words that should make this entry match
   • followups → suggestion chips shown after this answer
   • links     → optional buttons under the answer
   To add a new project: copy one "project" entry below, change it,
   and add its title to the "projects" overview entry.
   ═══════════════════════════════════════════════════════════════ */
window.KAVYA_KB = [
  {
    id: 'intro', group: 'about', title: 'Introduction about Kavya',
    keywords: 'introduction intro overview summary brief who kavya gupta background profile',
    text: "Kavya Gupta is a final-year B.Tech Computer Science student at VIT Bhopal, with a CGPA of 8.75. He specialises in AI and machine learning, generative AI and agentic AI. He loves building things that think and shipping them to production, from RAG pipelines to full ML applications. He was a Smart India Hackathon 2025 finalist, ranking in the top 45 out of 950, and he leads the machine learning domain at the Google Developer Group Club at VIT. He is currently open to internships and research collaborations.",
    followups: ['Tell me about his projects', 'What are his skills?', 'How can I contact him?']
  },
  {
    id: 'education', group: 'about', title: 'Education and CGPA',
    keywords: 'education college university vit bhopal btech b.tech degree cgpa gpa grades marks final year student study studying graduation graduate computer science cse',
    text: "Kavya is a final-year B.Tech student in Computer Science and Engineering at VIT Bhopal, graduating in 2027, with a CGPA of 8.75. His focus areas are AI and machine learning, generative AI and agentic AI.",
    followups: ['What are his achievements?', 'What are his skills?']
  },
  {
    id: 'achievements', group: 'about', title: 'Achievements and hackathons',
    keywords: 'achievements achievement hackathon hackathons sih smart india finalist cybershield wicys runner-up winner won award awards prize rank ranking competition competitions accomplishments',
    text: "Kavya was a finalist at Smart India Hackathon 2025, placing in the top 45 out of 950. He was also second runner-up at the CyberShield Hackathon organised by WiCyS, and he is the machine learning lead at the Google Developer Group Club at VIT.",
    followups: ['Tell me about GDGC', 'Tell me about his projects']
  },
  {
    id: 'gdgc', group: 'about', title: 'ML Lead at Google Developer Group Club',
    keywords: 'gdgc gdg google developer group club lead leader leadership ml lead machine learning team experience role position community club',
    text: "Kavya is the Machine Learning Lead at the Google Developer Group Club at VIT, where he leads the machine learning domain.",
    followups: ['What are his achievements?', 'What are his skills?']
  },
  {
    id: 'skills', group: 'skills', title: 'Skills and tech stack overview',
    keywords: 'skills skill tech stack technologies technology toolkit tools expertise good at know proficient strengths',
    text: "Kavya works across AI, backend and data. On the AI side: generative AI, RAG, fine-tuning LLMs, Scikit-Learn and PyTorch. Languages: Python, C plus plus, JavaScript and SQL. Frameworks: FastAPI, Flask, Streamlit and Node.js with Express. Databases and tools: MongoDB, PostgreSQL, Redis, Git, GitHub and Postman.",
    followups: ['Which AI skills does he have?', 'Which databases does he use?', 'What certifications does He have?']
  },
  {
    id: 'skills-ai', group: 'skills', title: 'AI and machine learning skills',
    keywords: 'ai ml machine learning generative genai gen rag retrieval augmented generation llm llms fine-tuning finetuning scikit-learn sklearn pytorch deep learning agentic agents langgraph model models',
    text: "On the AI side, Kavya works with generative AI, retrieval-augmented generation or RAG, fine-tuning large language models, Scikit-Learn and PyTorch. He also builds agentic workflows, for example with LangGraph in his ColdMail AI project.",
    followups: ['Tell me about ColdMail AI', 'Tell me about the proposal evaluator']
  },
  {
    id: 'skills-lang', group: 'skills', title: 'Programming languages',
    keywords: 'programming languages language python c++ cpp javascript js sql code coding',
    text: "Kavya's programming languages are Python, C plus plus, JavaScript and SQL. Python powers his AI and backend projects.",
    followups: ['Which frameworks does he use?', 'What are his skills?']
  },
  {
    id: 'skills-frameworks', group: 'skills', title: 'Frameworks',
    keywords: 'frameworks framework fastapi flask streamlit node nodejs express backend api web development full stack fullstack',
    text: "For building applications Kavya uses FastAPI, Flask, Streamlit, and Node.js with Express.",
    followups: ['Which databases does he use?', 'Tell me about his projects']
  },
  {
    id: 'skills-tools', group: 'skills', title: 'Databases and tools',
    keywords: 'databases database db tools mongodb postgresql postgres redis git github postman sqlite chromadb vector storage',
    text: "On the data and tooling side, Kavya uses MongoDB, PostgreSQL, Redis, Git and GitHub, and Postman. His projects also use SQLite and ChromaDB.",
    followups: ['Which frameworks does he use?', 'Tell me about his projects']
  },
  {
    id: 'certs', group: 'skills', title: 'Certifications',
    keywords: 'certifications certification certificate certificates certified course courses ibm watsonx oracle oci microsoft azure dp-900 cloud data science credential credentials',
    text: "Kavya holds three certifications: Generative AI using IBM watsonx from IBM, the OCI 2025 Data Science Professional from Oracle, and Azure Data Fundamentals, DP-900, from Microsoft. You can open each certificate from the Skills section of this page.",
    links: [{ label: 'See certificates ↗', href: '#skills' }],
    followups: ['What are his skills?', 'Tell me about his projects']
  },
  {
    id: 'projects', group: 'projects', title: 'Projects overview',
    keywords: 'projects project portfolio built built work works made github repositories repos apps applications showcase',
    text: "Kavya's portfolio features four projects: the AI Proposal Evaluation System, Autonomous ColdMail AI, an n8n Workflow Generator Chrome extension, and SafeSphere.AI, a real-time moderation engine. Ask me about any of them.",
    links: [{ label: 'See projects ↗', href: '#projects' }],
    followups: ['Tell me about the proposal evaluator', 'Tell me about ColdMail AI', 'Tell me about SafeSphere', 'Tell me about the n8n extension']
  },
  {
    id: 'proj-proposal', group: 'projects', title: 'AI Proposal Evaluation System',
    keywords: 'proposal proposals evaluator evaluation evaluate system funding rd r&d pdfs pdf ensemble accuracy shap uncertainty confidence report sqlite streamlit fastapi scoring recommendation',
    text: "The AI Proposal Evaluation System is a full-stack platform built with FastAPI and Streamlit. It analyses over 300 R&D proposal PDFs and automates funding recommendations. An ML ensemble scoring model reaches 91.3% prediction accuracy, with uncertainty estimation and confidence intervals, and generative AI produces a report in under 5 seconds, stored in SQLite.",
    links: [{ label: 'GitHub ↗', href: 'https://github.com/kavya1b1/AI-Proposal-Evaluator' }],
    followups: ['Tell me about ColdMail AI', 'Tell me about SafeSphere', 'What are his skills?']
  },
  {
    id: 'proj-coldmail', group: 'projects', title: 'Autonomous ColdMail AI',
    keywords: 'coldmail cold mail email emails outreach autonomous agentic langgraph groq smtp chromadb postgresql redis frontend saas opportunity extraction agent pipeline',
    text: "Autonomous ColdMail AI is a full-stack agentic AI outreach platform. A LangGraph pipeline, with an LLM agent that extracts opportunities, drafts and sends personalised cold emails over SMTP. It has a FastAPI REST API and a five-view SaaS-style frontend, backed by PostgreSQL, ChromaDB and Redis, and it uses Groq-hosted LLMs for fast inference.",
    links: [{ label: 'GitHub ↗', href: 'https://github.com/kavya1b1/Autonomous-ColdMail-AI-' }],
    followups: ['Tell me about the n8n extension', 'Tell me about SafeSphere', 'Which AI skills does he have?']
  },
  {
    id: 'proj-n8n', group: 'projects', title: 'n8n Workflow Generator Chrome Extension',
    keywords: 'n8n chrome extension browser workflow workflows automation generator generate prompt deepseek openrouter json clipboard gmail classification',
    text: "The n8n Workflow Generator is a Chrome extension that turns a plain-text prompt into a complete n8n automation workflow. It uses DeepSeek R1 through OpenRouter to generate native n8n JSON, which is copied to your clipboard, ready to import. A Gmail email-classification workflow is included as an example.",
    links: [{ label: 'GitHub ↗', href: 'https://github.com/kavya1b1/n8nChrome-Extention' }],
    followups: ['Tell me about SafeSphere', 'Tell me about ColdMail AI', 'What are his skills?']
  },
  {
    id: 'proj-safesphere', group: 'projects', title: 'SafeSphere.AI moderation engine',
    keywords: 'safesphere sphere moderation moderate toxicity toxic unsafe content safety image text bytez sightengine redis mongodb latency detection logs audit real-time realtime',
    text: "SafeSphere.AI is a real-time AI moderation engine that analyses more than 10,000 text and image samples for toxicity and unsafe content. It reaches over 95% detection accuracy using the Bytez.js and Sightengine APIs. Redis-based async processing cut latency by 35% to about 1.5 seconds, and MongoDB stores over 50,000 moderation logs, user reports and audit history.",
    links: [{ label: 'GitHub ↗', href: 'https://github.com/kavya1b1/SafeSphere.ai' }],
    followups: ['Tell me about the proposal evaluator', 'Tell me about the n8n extension', 'What are his skills?']
  },
  {
    id: 'strengths', group: 'about', title: 'Why work with Kavya',
    keywords: 'why hire strengths strength unique different special best standout value impact reason choose stand out',
    text: "Kavya focuses on closing the gap between research and real-world impact. He has built an ML ensemble with 91.3% accuracy, a real-time moderation engine processing over 10,000 samples, and agentic AI systems. He is also a hackathon finalist, an ML team lead, and cloud certified.",
    followups: ['Tell me about his projects', 'How can I contact him?']
  },
  {
    id: 'availability', group: 'contact', title: 'Availability and opportunities',
    keywords: 'availability available open hire hiring job jobs internship internships intern opportunity opportunities collaboration collaborate collaborations research freelance work looking recruit recruiter',
    text: "Kavya is open to internships, research collaborations, hackathon teams, or just a good tech conversation. The best way to reach him is the contact form on this page, or by email.",
    links: [{ label: 'Contact form ↗', href: '#contact' }],
    followups: ['How can I contact him?', 'Can I see his resume?']
  },
  {
    id: 'contact', group: 'contact', title: 'Contact details',
    keywords: 'contact reach email mail linkedin github message connect touch talk write social address',
    text: "You can reach Kavya by email at kavya1b1@gmail.com, on LinkedIn as its-kavya-gupta, or on GitHub as kavya1b1. You can also use the contact form at the bottom of this page, and your message goes straight to his inbox.",
    links: [
      { label: 'Email ↗', href: 'mailto:kavya1b1@gmail.com' },
      { label: 'LinkedIn ↗', href: 'https://www.linkedin.com/in/its-kavya-gupta/' },
      { label: 'GitHub ↗', href: 'https://github.com/kavya1b1' }
    ],
    followups: ['Is he open to internships?', 'Can I see his resume?']
  },
  {
    id: 'resume', group: 'contact', title: 'Resume',
    keywords: 'resume cv download curriculum vitae pdf',
    text: "You can download Kavya's resume with the Download Resume button in the About section of this page.",
    links: [{ label: 'Download resume ↗', href: 'Kavya_Resume.pdf' }],
    followups: ['How can I contact him?', 'Tell me about his projects']
  },
  {
    id: 'assistant', group: 'meta', title: 'About this assistant',
    keywords: 'assistant bot agent voice ai who are you what are you chatbot local free offline browser privacy how work works built made rag knowledge base help can do',
    text: "I'm Kavya's voice assistant. I run entirely inside your browser, so there are no servers and no cost. I search a small knowledge base about him and answer from it. Ask about his projects, skills, certifications, achievements, or how to contact him. For example: tell me about SafeSphere, which databases does he use, or is he open to internships?",
    followups: ['Give me a quick intro', 'Tell me about his projects', 'How can I contact him?']
  }
];
