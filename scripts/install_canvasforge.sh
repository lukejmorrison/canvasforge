#!/usr/bin/env bash
set -euo pipefail

APP_NAME="CanvasForge"
REPO_URL="https://github.com/lukejmorrison/canvasforge.git"
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$INSTALL_ROOT/canvasforge"
VENV_DIR="$APP_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
LAUNCHER_SCRIPT="$BIN_DIR/canvasforge"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$DESKTOP_DIR/canvasforge.desktop"
ICON_SOURCE_REL="assets/app_icons/canvasForge_app_icon.png"
ICON_TARGET_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
ICON_TARGET="$ICON_TARGET_ROOT/canvasforge.png"

command -v git >/dev/null 2>&1 || { echo "git is required but was not found" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required but was not found" >&2; exit 1; }
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This installer targets Linux (Pop!_OS) desktops." >&2
    exit 1
fi

mkdir -p "$INSTALL_ROOT"
if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch origin master >/dev/null 2>&1 || true
    git -C "$APP_DIR" reset --hard origin/master
else
    rm -rf "$APP_DIR"
    git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"
deactivate

mkdir -p "$BIN_DIR"
cat > "$LAUNCHER_SCRIPT" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" "$APP_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER_SCRIPT"

mkdir -p "$ICON_TARGET_ROOT"
if [[ -f "$APP_DIR/$ICON_SOURCE_REL" ]]; then
    install -Dm644 "$APP_DIR/$ICON_SOURCE_REL" "$ICON_TARGET"
else
    echo "Warning: icon source $ICON_SOURCE_REL not found; desktop entry will use default icon." >&2
fi

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Remix screenshots, snippets, and vectors
Exec="$LAUNCHER_SCRIPT"
Icon=canvasforge
Terminal=false
Categories=AudioVideo;Graphics;
EOF
chmod 644 "$DESKTOP_FILE"

update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "${XDG_DATA_HOME:-$HOME/.local/share}/icons" >/dev/null 2>&1 || true
fi

echo "$APP_NAME installed. Launch it from the Audio & Video menu or run 'canvasforge'."
