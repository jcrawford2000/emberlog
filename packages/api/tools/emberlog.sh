#!/usr/bin/env bash
set -euo pipefail

SESSION="emberlog"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOLS_DIR="$ROOT/packages/api/tools"

# Safely check for existing session without tripping `set -e`
set +e
tmux has-session -t "$SESSION" >/dev/null 2>&1
has=$?
set -e

if [ "$has" -eq 0 ]; then
  exec tmux attach -t "$SESSION"
fi

# Make sure our helper scripts exist & are executable
for f in emberlog-api.sh emberlog-notifier.sh emberlog-web.sh; do
  [ -x "$TOOLS_DIR/$f" ] || { echo "Missing or not executable: $TOOLS_DIR/$f"; exit 1; }
done

# Create the session + windows
tmux new-session -d -s "$SESSION" -n "api" -c "$ROOT"
tmux send-keys -t "$SESSION":0 "$TOOLS_DIR/emberlog-api.sh" C-m

tmux new-window  -t "$SESSION":1 -n "notifier" -c "$ROOT"
tmux send-keys -t "$SESSION":1 "$TOOLS_DIR/emberlog-notifier.sh" C-m

tmux new-window  -t "$SESSION":2 -n "web" -c "$ROOT"
tmux send-keys -t "$SESSION":2 "$TOOLS_DIR/emberlog-web.sh" C-m

# Nice titles
tmux rename-window -t "$SESSION":0 "api"
tmux select-window -t "$SESSION":0
exec tmux attach -t "$SESSION"
