#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.9 or newer, then run this again."
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Python 3.9 or newer is required."
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 22.12 or newer is required. Install it, then run this again."
  exit 1
fi

if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 12) ? 0 : 1)'; then
  echo "Node.js 22.12 or newer is required. Current version: $(node --version)"
  exit 1
fi

echo "Creating the Python environment..."
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Installing frontend packages..."
npm ci

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo
echo "Setup complete."
echo "Run: npm run dev"
echo "Then open: http://127.0.0.1:5173"
echo "Add your OpenAI API key in Settings or edit .env."
