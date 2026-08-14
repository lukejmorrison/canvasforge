# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CanvasForge (macOS Intel x86_64 onedir .app)

import ast
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)


def _bundle_version() -> str:
    """Read __version__ from main.py so Finder/About match the checkout."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return "0.6.0"


BUNDLE_VERSION = _bundle_version()

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "plugins"), "plugins"),
    (str(ROOT / "artifacts"), "artifacts"),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "image_library_panel",
        "undo_manager",
        "plugin_manager",
        "agent_handoff",
        "agent_handoff.adapters",
        "agent_handoff.adapters.clipboard",
        "agent_handoff.adapters.cli",
        "agent_handoff.adapters.grok",
        "agent_handoff.adapters.hermes",
        "agent_handoff.adapters.http",
        "agent_handoff.adapters.openclaw",
        "agent_handoff.adapters.vscode",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt6.QtWebEngine",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtBluetooth",
        "PyQt6.QtNfc",
        "PyQt6.QtPositioning",
        "PyQt6.QtSensors",
        "PyQt6.QtSerialPort",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Keep Cocoa + image/SVG plugins; drop Wayland/XCB (Linux-only).
a.binaries = [
    b for b in a.binaries
    if not any(
        token in b[0].lower()
        for token in ("wayland", "qxcb", "qeglfs", "qvnc", "qlinuxfb", "qminimalegl")
    )
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CanvasForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="CanvasForge",
)

app = BUNDLE(
    coll,
    name="CanvasForge.app",
    icon=str(ROOT / "assets" / "app_icons" / "canvasForge_app_icon.png"),
    bundle_identifier="com.lukejmorrison.CanvasForge",
    info_plist={
        "CFBundleName": "CanvasForge",
        "CFBundleDisplayName": "CanvasForge",
        "CFBundleShortVersionString": BUNDLE_VERSION,
        "CFBundleVersion": BUNDLE_VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
