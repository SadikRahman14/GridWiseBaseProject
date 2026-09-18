#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
if [ ! -f .env ]; then cp .env.example .env; fi
echo 'Setup complete. Run: .venv/bin/python scripts/demo.py'
echo 'After configuring the model, start the API: .venv/bin/python run.py'
