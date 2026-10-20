#!/usr/bin/env bash
# Read-only diagnostics — run from any path inside a JARVIS ONE git checkout.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "JARVIS ONE diagnostics: $ROOT"
python3 --version || true
docker --version || true
docker compose version || true
if [[ -f .env ]]; then echo '.env present (values hidden)'; else echo 'Missing .env: run python3 setup.py'; fi
if [[ -f config/printers.json ]]; then echo 'Private printer config present'; else echo 'Printer config missing: run python3 setup.py'; fi
if docker compose version >/dev/null 2>&1; then docker compose ps || true; fi
