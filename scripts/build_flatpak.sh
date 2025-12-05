#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$REPO_ROOT/flatpak/com.lukejmorrison.CanvasForge.yml"
BUILD_DIR="$REPO_ROOT/flatpak-build"
RUNTIME="org.kde.Platform//6.8"
SDK="org.kde.Sdk//6.8"
WHEELS_DIR="$REPO_ROOT/flatpak/vendor/wheels"

command -v flatpak >/dev/null 2>&1 || { echo "flatpak is required but was not found" >&2; exit 1; }
command -v flatpak-builder >/dev/null 2>&1 || { echo "flatpak-builder is required but was not found" >&2; exit 1; }

ensure_ref() {
	local ref="$1"
	if ! flatpak info "$ref" >/dev/null 2>&1; then
		echo "Installing required Flatpak ref: $ref"
		flatpak install --user -y "$ref"
	fi
}

ensure_ref "$RUNTIME"
ensure_ref "$SDK"

echo "Refreshing local PyPI wheels for offline Flatpak build"
rm -rf "$WHEELS_DIR"
mkdir -p "$WHEELS_DIR"
python3 -m pip download --only-binary=:all: --prefer-binary -r "$REPO_ROOT/requirements.txt" -d "$WHEELS_DIR"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

flatpak-builder --user --install --force-clean "$BUILD_DIR" "$MANIFEST"

echo "CanvasForge Flatpak installed. Launch with 'flatpak run com.lukejmorrison.CanvasForge'."
