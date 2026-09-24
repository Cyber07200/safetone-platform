#!/usr/bin/env bash
# SafeTone — one-command local start (macOS / Linux).
# Creates backend/.venv, installs dependencies, runs backend (8000) and frontend (5173).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"

cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "→ Creating Python virtualenv"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt
[ -f .env ] || { cp .env.example .env; echo "→ Created backend/.env from .env.example (Demo Mode)"; }
alembic upgrade head

cd "$ROOT/frontend"
[ -d node_modules ] || { echo "→ Installing frontend dependencies"; npm install --no-fund --no-audit; }

cd "$ROOT/backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACK=$!
cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null || true' INT TERM EXIT
echo ""
echo "  SafeTone:  http://127.0.0.1:5173"
echo "  API docs:  http://127.0.0.1:8000/docs"
echo "  Ctrl+C to stop"
wait
