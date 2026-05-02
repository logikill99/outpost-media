#!/usr/bin/env bash
# outpost-media — run locally (not as a daemon).
# Activates .venv, loads .env, starts the Flask + SocketIO app on http://localhost:5000.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [[ ! -d ".venv" ]]; then
  echo "No .venv found. Create one first:" >&2
  echo "  python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "No .env found. Copy the template and fill it in:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi

exec .venv/bin/python run.py
