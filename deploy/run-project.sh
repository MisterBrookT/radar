#!/usr/bin/env bash
# Project-owned detached job entry; BASE is an immutable snapshot with code/ and runs/.
set -euo pipefail
BASE="$1"
TOPIC="${2:-genui}"
END="${3:-$(date -u +%F)}"
RUN_ID="$(basename "$BASE")"
finish() {
  local status=$?
  printf '%s\n' "$status" > "$BASE/exit-status"
  tmux wait-for -S "radar-$RUN_ID-done" || true
}
trap finish EXIT
cd "$BASE/code"
export RADAR_RUNS="$BASE/runs" RADAR_NO_X=1 RADAR_WECHAT=1
export RADAR_LLM_PROVIDER=pi RADAR_TTS_PROVIDER=piper RADAR_LANGUAGE=en
export RADAR_TTS_WORKERS=1 OMP_NUM_THREADS=2 PYTHONUNBUFFERED=1
export RADAR_PIPER_PYTHON="${RADAR_PIPER_PYTHON:-$HOME/.local/lib/genui-local-tts/.venv/bin/python}"
export RADAR_PIPER_MODEL="${RADAR_PIPER_MODEL:-$HOME/.local/lib/genui-local-tts/voices/en_US-ljspeech-high.onnx}"
export RADAR_WECHAT_PYTHON="${RADAR_WECHAT_PYTHON:-$HOME/.local/lib/genui-weixin/.venv/bin/python}"
PYTHON="${RADAR_PYTHON:-$HOME/.local/lib/genui-daily/.venv/bin/python}"
export PATH="$(dirname "$PYTHON"):$HOME/.local/bin:$PATH"
export PYTHONPATH="$BASE/code"
# Existing paired-account runtime paths are compatibility resources, not project names.
"$RADAR_WECHAT_PYTHON" -m radar.weixin status > "$BASE/context-status.json"
"$PYTHON" -m radar run --topic "$TOPIC" --week-ending "$END" --run-id "$RUN_ID"
