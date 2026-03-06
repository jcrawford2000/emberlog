#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT/packages/api"
poetry run uvicorn emberlog_api.app.main:app --host 0.0.0.0 --port 8080 --reload
