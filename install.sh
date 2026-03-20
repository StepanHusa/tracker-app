#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${HOME}/.local/share/tracker_app/venv"
BIN="${HOME}/bin/tracker-app"
DATA_DIR="${HOME}/.local/share/tracker_app/trackers"
LOG_DIR="${HOME}/.local/state/tracker_app"

echo "==> Checking dependencies"
if ! /usr/bin/python3 -c "import gi" 2>/dev/null; then
    echo "ERROR: python3-gi not found. Install it with:"
    echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    exit 1
fi

echo "==> Creating venv at ${VENV} (with system site-packages for PyGObject)"
# Must use /usr/bin/python3 (apt Python) — miniconda's python3 doesn't have python3-gi
/usr/bin/python3 -m venv --system-site-packages "${VENV}"

echo "==> Installing Python deps"
"${VENV}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" -q

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
echo ""
echo "Note: the old 'tracker' command (Taxlio) is unaffected."
