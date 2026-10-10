---
title: Autonomous ColdMail AI
tags: [project, agentic-ai, coldmail, outreach, rag, langgraph]
anchor: "#projects"
links:
  - label: GitHub
    href: https://github.com/kavya1b1/Autonomous-ColdMail-AI-
---
## Overview
Autonomous ColdMail AI, also called ColdMail AI Pro, is an agentic AI sales-development assistant that turns a single batch of job openings into personalised, research-backed cold emails. It is a full-stack agentic AI outreach platform, built with a LangGraph pipeline, a FastAPI REST API and a five-view SaaS-style frontend.

## The problem it solves
During college placement season the placement team can send 15 to 20 or more job openings in one email. Handling that manually means opening every job description, working out the required skills, checking whether the role fits your profile, finding company information, writing a separate personalised email, attaching the resume and verifying links, and repeating it for every company. That is slow and hard to scale.

## How it works
The user provides the batch of opportunities and the agent extracts them, researches each company, matches the resume to the job description, retrieves relevant resume evidence, writes a personalised email, reviews it, rewrites it if needed, waits for human approval, and then sends it over SMTP. The AI does the repetitive work while the user keeps control of the final email.

## Key features
It extracts multiple opportunities from one unstructured message. It researches public company pages to create evidence for the email. Resume to job matching combines skill matching with semantic similarity. Hybrid RAG, using BM25 and dense embeddings, retrieves only the relevant resume and profile evidence instead of passing the whole resume to the LLM. An AI review step scores each email for personalisation, clarity and grounding, and weak drafts are routed back for rewriting. Analytics track generated emails, sent emails, failed sends, campaign history and personalisation scores.

## Safety and reliability
Emails are never sent automatically: a human approval gate must approve each one, and real email sending is disabled by default in demo mode. Output is grounded in evidence, structured validation is applied, and only approved profile links are kept, which prevents hallucinated portfolio or social links. Pytest regression tests cover extraction, matching, retrieval, the workflow nodes, schemas and email-sending safety.

## Tech stack
The frontend is HTML, CSS and vanilla JavaScript. The backend is FastAPI with a LangGraph agentic workflow and Groq-hosted LLMs. Retrieval uses BM25 and Sentence Transformers, research uses HTTPX, Trafilatura and BeautifulSoup, PDFs are processed with PyMuPDF, and data is stored with SQLAlchemy and SQLite. Authentication uses JWT and bcrypt, email goes over SMTP, and the infrastructure includes Docker, Redis, PostgreSQL and ChromaDB.
