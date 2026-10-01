#!/usr/bin/env bash
# Daily entry point on the DGX (called by the systemd timer).
set -euo pipefail
cd "$HOME/.local/lib/genui-daily"
set -a; . "$HOME/.config/genui-daily/env"; set +a
export GENUI_WECHAT="${GENUI_WECHAT:-1}"
export GENUI_RUNS="$HOME/.local/state/genui-daily/runs"
exec .venv/bin/python -m genui "$@"
