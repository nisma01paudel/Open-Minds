#!/usr/bin/env bash
# One command. Runs the whole pipeline end to end.
#
#   ./scripts/demo.sh                          # the 2024-09-28 event day
#   ./scripts/demo.sh --as-of 2024-07-20       # a mid-monsoon date, shows the abstain state
#   ./scripts/demo.sh --stop                   # stop the model server afterwards
#
# Starts the open-weight decision model if it is not already up, runs the seven-step
# agent, and prints the trace and the Nepali advisory. Nothing else is required.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8081}"
STOP_AFTER=0
PASSTHRU=()
while [ $# -gt 0 ]; do
  case "$1" in
    --stop) STOP_AFTER=1 ;;
    *) PASSTHRU+=("$1") ;;
  esac
  shift
done

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "no .venv found. Create it first:" >&2
  echo "  uv venv .venv && uv pip install --python .venv/bin/python -e '.[geo,dev,crypto]'" >&2
  exit 1
fi

if curl -s -m 3 "http://127.0.0.1:$PORT/health" | grep -q ok; then
  echo "model already serving on :$PORT"
else
  echo "starting the open-weight model on :$PORT (6 threads; 12 collapses throughput on this CPU)"
  scripts/serve_model.sh start
fi

echo
# Defaults FIRST, caller's flags after: argparse keeps the last value for a repeated
# option, so --as-of overrides the default while the required arguments still exist.
# Passing only the caller's flags broke the documented "--as-of 2024-07-20" invocation.
"$PY" scripts/agent_demo.py \
  --as-of 2024-09-28 --lon 85.05 --lat 27.76 \
  --report "A rural road built by a municipality runs across the slope above the national highway. Cracks have appeared and debris is falling onto the highway." \
  "${PASSTHRU[@]}"

if [ "$STOP_AFTER" = "1" ]; then
  scripts/serve_model.sh stop
fi
