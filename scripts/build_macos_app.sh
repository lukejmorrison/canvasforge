#!/usr/bin/env bash
# Build an Intel x86_64 CanvasForge.app for older Mac Minis (macOS 11+).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script builds a macOS .app and must be run on macOS."
  echo "On Linux, use Flatpak/AUR/install_canvasforge.sh instead."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv-macos}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
# Pin Qt < 6.8 so macOS 11 / 2014-class Minis remain supported.
python -m pip install "PyQt6>=6.6,<6.8" "pyinstaller>=6.3"

rm -rf "$ROOT/build" "$ROOT/dist"
pyinstaller --noconfirm --clean "$ROOT/canvasforge.spec"

APP_PATH="$ROOT/dist/CanvasForge.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Build failed: $APP_PATH not found"
  exit 1
fi

# Ad-hoc sign for personal use (right-click → Open past Gatekeeper).
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep -s - "$APP_PATH" || true
fi

DMG_PATH="$ROOT/dist/CanvasForge-macos-x86_64.dmg"
if command -v hdiutil >/dev/null 2>&1; then
  rm -f "$DMG_PATH"
  hdiutil create -volname "CanvasForge" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_PATH"
  echo "DMG ready: $DMG_PATH"
fi

echo "App ready: $APP_PATH"
echo "Manual smoke checklist:"
echo "  1) Launch .app (Retina thumbs / Cmd shortcuts / Preferences in app menu)"
echo "     Restore leftover com.lukejmorrison.CanvasForge.savedState and confirm no SIGILL"
echo "  2) Select tool: marquee → hand drag → snap back to hole"
echo "  3) Library scroll with many screenshots"
echo "  4) Fill / blur / eyedropper feel responsive"
echo "  5) CanvasForge → Settings → Mobile → Pair Mobile Device shows a QR code and security code"
