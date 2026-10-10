---
title: AI Proposal Evaluation System
tags: [project, generative-ai, ml, proposal-evaluator, explainable-ai]
anchor: "#projects"
links:
  - label: GitHub
    href: https://github.com/kavya1b1/AI-Proposal-Evaluator
---
## Overview
The AI Proposal Evaluation System, also called the AI-Driven Proposal Evaluation and Explainability Suite, is an end-to-end decision support system for evaluating R&D and research proposals. It is a full-stack platform built with FastAPI and Streamlit that analyses over 300 R&D proposal PDFs and automates funding recommendations.

## The problem it solves
Manual evaluation of research proposals is slow, subjective and inconsistent, lacks transparency and is poorly documented. As proposal volumes grow, funding agencies and institutions need an evaluation process that is scalable, objective and explainable.

## How it works
The system automatically parses the proposal PDF and scores its novelty, feasibility and financial alignment. An ML ensemble produces the final score, with uncertainty estimation and confidence intervals. Decisions are explained with feature importance and SHAP, and generative AI writes a human-readable evaluation narrative and a professional PDF report in under 5 seconds.

## Architecture
A Streamlit dashboard talks to a FastAPI backend. The backend runs PDF parsing and text extraction, novelty analysis, a budget and financial check, the ML ensemble evaluation, uncertainty and confidence estimation, explainable AI, GenAI narrative generation, and PDF report generation. Results and evaluation metadata are stored in SQLite.

## Machine learning and results
An ML ensemble scoring model reaches 91.3% prediction accuracy, with uncertainty estimation and confidence intervals. The repository includes the model training code, an embedding model, a vector store, and a dataset of past projects.

## Inputs and outputs
The inputs are the proposal PDF and the budget in rupees. The budget affects the financial feasibility score, the weighting of the ML score, and the risk and confidence estimate; without it the model still works but cannot judge financial realism. The outputs are a final AI score from 0 to 100, a confidence interval and uncertainty band, explainable feature contributions, an AI-generated narrative, a downloadable PDF report, and an evaluation history timeline.

## Tech stack
Python, FastAPI, SQLAlchemy with SQLite, ReportLab for PDFs, Scikit-Learn for the ensemble, sampling-based uncertainty estimation, SHAP for explainability, an LLM for the narrative, and Streamlit with Plotly for the dashboard.
