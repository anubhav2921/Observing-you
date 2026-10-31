#!/usr/bin/env bash
# Bash unified launcher for AI Study Focus Monitor
MODE="${1:-web}"
HOST="${2:-127.0.0.1}"
PORT="${3:-8000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

echo "=========================================================="
echo "  Starting AI Study Focus Monitor (Mode: $MODE)"
echo "=========================================================="

if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_EXE="$REPO_ROOT/.venv/bin/python"
else
    PYTHON_EXE="python3"
fi

"$PYTHON_EXE" "$REPO_ROOT/run_app.py" --mode "$MODE" --host "$HOST" --port "$PORT"

