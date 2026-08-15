#!/usr/bin/env bash
# Compile and test the macOS desktop and iOS phone paths as far as this host allows.
# Native CanvasForge.app / Runner.app / IPA still require a Mac with Xcode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "== Python syntax =="
python3 -m py_compile main.py image_library_panel.py undo_manager.py plugin_manager.py \
  mobile_sync.py mobile_qr.py macos_restorable.py

echo "== Desktop tests (pairing + macOS restorable + bundle spec) =="
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  PYTHON="python3"
fi
"$PYTHON" -m pytest tests/test_macos_secure_restorable.py tests/test_macos_bundle.py \
  tests/test_mobile_sync.py

echo "== Flutter phone app tests =="
if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter is not on PATH; skip phone compile."
  echo "On a Mac Mini: cd mobile/app && flutter pub get && flutter test && flutter run -d ios"
  exit 0
fi
(
  cd "$ROOT/mobile/app"
  flutter pub get
  flutter test
  flutter analyze --no-fatal-infos
  echo "== Dart/asset compile (host-neutral) =="
  flutter build bundle
)

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo
  echo "Native Apple binaries were not produced on $(uname -s)."
  echo "On a Mac Mini:"
  echo "  bash scripts/build_macos_app.sh"
  echo "  open dist/CanvasForge.app"
  echo "  cd mobile/app && flutter run -d ios"
  echo "  # or: bash scripts/build_flutter_mobile.sh ios-simulator"
  exit 0
fi

echo "== macOS .app =="
bash "$ROOT/scripts/build_macos_app.sh"

echo "== iOS simulator =="
bash "$ROOT/scripts/build_flutter_mobile.sh ios-simulator"

echo "Apple targets compiled on this Mac."
