#!/usr/bin/env bash
# Fetch the open-weight decision model, once.
#
# The weights are 1.1 GB and the server is a compiled binary, so neither is in this repository.
# This script exists because the submission calls `./scripts/demo.sh` a one-command demo and it
# is not one on a machine that has never run it - a fact only visible from a clean clone.
#
#   ./scripts/fetch_model.sh                  # into $HOME/win/aistack
#   AISTACK=/somewhere ./scripts/fetch_model.sh
set -euo pipefail

AISTACK="${AISTACK:-$HOME/win/aistack}"
GGUF_DIR="$AISTACK/gguf"
MODEL="$GGUF_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
BIN="$AISTACK/llama.cpp/build/bin/llama-server"

# Qwen2.5-1.5B-Instruct, Q4_K_M, Apache-2.0. Open weights only, as the competition requires.
URL="${MODEL_URL:-https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf}"

mkdir -p "$GGUF_DIR"

echo "aistack: $AISTACK"

if [ -f "$MODEL" ]; then
  echo "weights: already present ($(du -h "$MODEL" | cut -f1)) - skipping"
else
  echo "weights: downloading 1.1 GB from Hugging Face"
  echo "         $URL"
  if command -v curl >/dev/null 2>&1; then
    # -C - resumes, so an interrupted download does not start over.
    curl -L --fail -C - -o "$MODEL.part" "$URL" || {
      echo "download failed. If you are offline, copy an existing .gguf to:" >&2
      echo "  $MODEL" >&2; exit 1; }
    mv "$MODEL.part" "$MODEL"
  else
    echo "curl is required to download the weights" >&2; exit 1
  fi
  echo "weights: $(du -h "$MODEL" | cut -f1)"
fi

if [ -x "$BIN" ]; then
  echo "server:  already built at $BIN"
elif command -v llama-server >/dev/null 2>&1; then
  echo "server:  llama-server is on PATH at $(command -v llama-server)"
  echo "         symlink it, or set BIN by hand:"
  echo "           ln -s \"$(command -v llama-server)\" \"$BIN\""
  mkdir -p "$(dirname "$BIN")"; ln -sf "$(command -v llama-server)" "$BIN"
  echo "         linked."
else
  echo "server:  llama-server not found."
  echo "         Build it, or install it, then re-run this script:"
  echo
  echo "           git clone https://github.com/ggml-org/llama.cpp \"$AISTACK/llama.cpp\""
  echo "           cmake -S \"$AISTACK/llama.cpp\" -B \"$AISTACK/llama.cpp/build\" -DLLAMA_CURL=ON"
  echo "           cmake --build \"$AISTACK/llama.cpp/build\" --target llama-server -j"
  echo
  echo "         Then: ./scripts/demo.sh"
  exit 1
fi

echo
echo "Ready. Now run:  ./scripts/demo.sh"
