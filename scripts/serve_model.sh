#!/usr/bin/env bash
# Start the open-weight decision model. ALWAYS 6 threads: measured on this
# machine, generation collapses from ~16 tok/s at 6 threads to 1-3.5 at 12.
set -euo pipefail
AISTACK="${AISTACK:-$HOME/win/aistack}"
MODEL="${MODEL:-$AISTACK/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
PORT="${PORT:-8081}"
case "${1:-start}" in
  start)
    pkill -f "llama-serve[r].*--port $PORT" 2>/dev/null || true
    nohup "$AISTACK/llama.cpp/build/bin/llama-server" -m "$MODEL" \
      -t 6 -c 4096 --port "$PORT" --no-warmup > /tmp/pahiro-llama-server.log 2>&1 &
    for _ in $(seq 1 30); do sleep 1
      curl -s -m 2 "http://127.0.0.1:$PORT/health" | grep -q ok && { echo "ready on :$PORT"; exit 0; }
    done
    echo "server did not become ready; see /tmp/pahiro-llama-server.log" >&2; exit 1 ;;
  stop)  pkill -f "llama-serve[r].*--port $PORT" && echo "stopped" || echo "not running" ;;
  *) echo "usage: $0 {start|stop}" >&2; exit 2 ;;
esac
