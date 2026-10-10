#!/bin/bash
set -e
cd "$(dirname "$0")/voice-agent"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
printf '\nNEXUS API will start at http://127.0.0.1:8000\nEnsure Ollama is running and your configured model is pulled.\nPress Ctrl+C to stop.\n\n'
uvicorn app.main:app --host 127.0.0.1 --port 8000
