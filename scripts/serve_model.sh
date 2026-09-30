#!/usr/bin/env bash
# Start the open-weight decision model. ALWAYS 6 threads: measured on this
# machine, generation collapses from ~16 tok/s at 6 threads to 1-3.5 at 12.
set -euo pipefail
AISTACK="${AISTACK:-$HOME/win/aistack}"
MODEL="${MODEL:-$AISTACK/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
PORT="${PORT:-8081}"
BIN="$AISTACK/llama.cpp/build/bin/llama-server"

# PREFLIGHT. The model and the llama.cpp build live outside this repository - 1.1 GB of weights
# and a compiled binary - so a fresh clone has neither. Without this check the script started
# nothing, waited thirty seconds and said "server did not become ready", which tells a reader
# neither what is missing nor what to do. Reported by cloning the repo and running the one
# command the submission calls "verified cold".
missing=()
[ -x "$BIN" ]   || missing+=("the llama-server binary: $BIN")
[ -f "$MODEL" ] || missing+=("the model weights:        $MODEL")

if [ ${#missing[@]} -gt 0 ] && [ "${1:-start}" = "start" ]; then
  {
    echo "Cannot start the model: this checkout does not have everything it needs."
    echo
    echo "Missing:"
    for m in "${missing[@]}"; do echo "  - $m"; done
    echo
    echo "These are deliberately not in the repository - 1.1 GB of weights and a compiled"
    echo "binary do not belong in git. Fetch them once:"
    echo
    echo "    ./scripts/fetch_model.sh"
    echo
    echo "Or point at an existing setup:  AISTACK=/path/to/aistack $0 start"
    echo
    echo "Geometry, thresholds and routing work without the model; only the decision step"
    echo "needs it. See docs/MODELS.md for the model and its licence."
  } >&2
  exit 3
fi

case "${1:-start}" in
  start)
    pkill -f "llama-serve[r].*--port $PORT" 2>/dev/null || true
    nohup "$BIN" -m "$MODEL" \
      -t 6 -c 4096 --port "$PORT" --no-warmup > /tmp/pahiro-llama-server.log 2>&1 &
    for _ in $(seq 1 30); do sleep 1
      curl -s -m 2 "http://127.0.0.1:$PORT/health" | grep -q ok && { echo "ready on :$PORT"; exit 0; }
    done
    echo "server did not become ready; see /tmp/pahiro-llama-server.log" >&2; exit 1 ;;
  stop)  pkill -f "llama-serve[r].*--port $PORT" && echo "stopped" || echo "not running" ;;
  *) echo "usage: $0 {start|stop}" >&2; exit 2 ;;
esac
