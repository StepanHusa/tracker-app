#!/usr/bin/env bash
# Cleanly remove everything Tracker App installed or created.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/bin/tracker-app"
DATA_ROOT="$HOME/.local/share/tracker_app"
LOG_DIR="$HOME/.local/state/tracker_app"

"$BIN" stop 2>/dev/null || true

if [[ -f "$BIN" ]]; then
    echo "==> Removing $BIN"
    rm -f "$BIN"
fi

echo "==> Removing $LOG_DIR"
rm -rf "$LOG_DIR"

if [[ -d "$DATA_ROOT" ]]; then
    read -rp "Also delete tracker data in $DATA_ROOT? [y/N] " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        rm -rf "$DATA_ROOT"
    else
        echo "    Kept $DATA_ROOT"
    fi
fi

echo "==> Removing $APP_DIR"
rm -rf "$APP_DIR"

echo "Done. Tracker App removed (remember to unbind its keyboard shortcut)."
