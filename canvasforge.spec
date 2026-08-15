# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CanvasForge (macOS Intel x86_64 onedir .app)

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

# LAN HTML fallback only — do not ship the Flutter tree inside the .app.
MOBILE_FALLBACK = (
    "index.html",
    "app.js",
    "style.css",
    "manifest.webmanifest",
    "README.md",
)

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "plugins"), "plugins"),
    (str(ROOT / "artifacts"), "artifacts"),
    (str(ROOT / "vendor"), "vendor"),
]
for _name in MOBILE_FALLBACK:
    _src = ROOT / "mobile" / _name
    if _src.is_file():
        datas.append((str(_src), "mobile"))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "image_library_panel",
        "undo_manager",
        "plugin_manager",
        "macos_restorable",
        "mobile_sync",
        "mobile_qr",
        "vendor",
        "vendor.segno",
        "vendor.segno.encoder",
        "vendor.segno.consts",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(ROOT / "packaging" / "macos" / "pyi_rth_disable_savedstate.py"),
    ],
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
    # argv_emulation makes the windowed bootloader create NSApplication and
    # process Apple Events before Python runs. That initializes NSPersistentUI
    # without a secure-coding delegate and SIGILLs on Monterey. Qt handles
    # Open With via QFileOpenEvent instead.
    argv_emulation=False,
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
        "CFBundleShortVersionString": "0.6.0",
        "CFBundleVersion": "0.6.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSQuitAlwaysKeepsWindows": False,
        "ApplePersistenceIgnoreState": True,
    },
)
