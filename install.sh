#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv"
BIN="${HOME}/bin/tracker-app"
DATA_DIR="${HOME}/.local/share/tracker_app/trackers"
LOG_DIR="${HOME}/.local/state/tracker_app"

echo "==> Checking dependencies"
if ! /usr/bin/python3 -c "import gi" 2>/dev/null; then
    echo "ERROR: python3-gi not found. Install it with:"
    echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    exit 1
fi
if ! command -v uv >/dev/null; then
    echo "ERROR: uv not found (https://docs.astral.sh/uv/)"
    exit 1
fi

echo "==> Creating venv at ${VENV} (with system site-packages for PyGObject)"
# Must use /usr/bin/python3 (apt Python) — only it has python3-gi
uv venv --quiet --allow-existing --system-site-packages --python /usr/bin/python3 "${VENV}"

echo "==> Installing Python deps"
uv pip install --quiet --python "${VENV}/bin/python3" -r "${SCRIPT_DIR}/requirements.txt"

echo "==> Creating data/log directories"
mkdir -p "${DATA_DIR}" "${LOG_DIR}"

echo "==> Writing launcher script at ${BIN}"
mkdir -p "${HOME}/bin"
cat > "${BIN}" << EOF
#!/usr/bin/env bash
exec "${VENV}/bin/python3" "${SCRIPT_DIR}/tracker" "\$@"
EOF
chmod +x "${BIN}"

chmod +x "${SCRIPT_DIR}/tracker"

echo ""
echo "Done!"
echo ""
echo "  Run:    ${BIN} toggle"
echo "  Debug:  ${BIN} start --no-fork"
echo ""
echo "Assign a keyboard shortcut in your DE settings pointing to:"
echo "  ${BIN} toggle"
