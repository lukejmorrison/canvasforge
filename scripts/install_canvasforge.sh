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

USE_LOCAL=false
CLEAN_INSTALL=false

usage() {
    cat <<EOF
Usage: $0 [--local] [--clean] [--help]

Options:
  --local   Install from the local checkout instead of GitHub
  --clean   Remove existing install directory before install
  --help    Show this help message
EOF
}

die() {
    echo "Error: $1" >&2
    exit 1
}

for arg in "$@"; do
    case "$arg" in
        --local)
            USE_LOCAL=true
            ;;
        --clean)
            CLEAN_INSTALL=true
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $arg (use --help for options)"
            ;;
    esac
done

run_with_retry() {
    local attempts="$1"
    shift
    local delay=2
    local try=1
    while true; do
        if "$@"; then
            return 0
        fi
        if (( try >= attempts )); then
            return 1
        fi
        echo "Command failed (attempt $try/$attempts). Retrying in ${delay}s..." >&2
        sleep "$delay"
        try=$((try + 1))
        delay=$((delay * 2))
    done
}

command -v git >/dev/null 2>&1 || die "git is required but was not found"
command -v python3 >/dev/null 2>&1 || die "python3 is required but was not found"
command -v tar >/dev/null 2>&1 || die "tar is required but was not found"
command -v install >/dev/null 2>&1 || die "install is required but was not found"
if [[ "$(uname -s)" != "Linux" ]]; then
    die "This installer targets Linux desktops."
fi

mkdir -p "$INSTALL_ROOT"

if [[ "$CLEAN_INSTALL" == true ]]; then
    echo "Performing clean install..."
    rm -rf "$APP_DIR"
fi

if [ "$USE_LOCAL" = true ]; then
    echo "Installing from local source..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    rm -rf "$APP_DIR"
    mkdir -p "$APP_DIR"
    
    echo "Copying files..."
    tar --exclude='.git' \
        --exclude='.venv' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='.flatpak-builder' \
        --exclude='flatpak-build' \
        -cf - -C "$PROJECT_ROOT" . | tar -xf - -C "$APP_DIR"
     
else
    if [[ -d "$APP_DIR/.git" ]]; then
        git -C "$APP_DIR" fetch origin master >/dev/null 2>&1 || true
        git -C "$APP_DIR" reset --hard origin/master
    else
        rm -rf "$APP_DIR"
        git clone --depth 1 "$REPO_URL" "$APP_DIR"
    fi
fi

RECREATE_VENV=false
if [[ "$CLEAN_INSTALL" == true ]]; then
    RECREATE_VENV=true
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    RECREATE_VENV=true
fi

if [[ "$RECREATE_VENV" == true ]]; then
    echo "Creating virtual environment..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c 'import sys' >/dev/null 2>&1; then
    echo "Virtual environment is unhealthy; rebuilding..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

run_with_retry 3 "$VENV_DIR/bin/python" -m pip install --upgrade pip || die "Failed to upgrade pip"
run_with_retry 3 "$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt" || die "Failed to install Python dependencies"

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
