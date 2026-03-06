#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
NOTIFIER_DIR="$ROOT/packages/notifier"

if [ ! -d "$NOTIFIER_DIR" ]; then
  echo "Notifier package not present at $NOTIFIER_DIR"
  exit 1
fi

cd "$NOTIFIER_DIR"
poetry run uvicorn emberlog_notifier.app.main:app --host 0.0.0.0 --port 8090 --reload
