"""Stop leftover AppKit savedState from SIGILL on Monterey.

Qt 6.7 / libqcocoa and the PyInstaller windowed bootloader can create
NSApplication before a delegate implements applicationSupportsSecureRestorableState:.
If ~/Library/Saved Application State/<bundle>.savedState exists, AppKit
initializes NSPersistentUI without secure coding. A later YES delegate
(ours or Qt's) then aborts in NSPersistentUIRequiresSecureCoding when
the oapp event calls restoreAllPersistentState.

Do not create NSApplication or install a YES delegate here: that is the
ASI. Discard the files, write defaults without loading AppKit, and after
QApplication() replace restoreAllPersistentState with a no-op.
"""

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE_ID = "com.lukejmorrison.CanvasForge"
SAVED_STATE_BUNDLE_IDS = (BUNDLE_ID,)

_macos_objc_keepalive = []
_persistent_ui_disabled = False


def is_darwin(platform=None) -> bool:
    return (platform if platform is not None else sys.platform) == "darwin"


def saved_application_state_dir(home=None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / "Library" / "Saved Application State"


def saved_state_paths(home=None, bundle_ids=None) -> list[Path]:
    ids = bundle_ids if bundle_ids is not None else SAVED_STATE_BUNDLE_IDS
    root = saved_application_state_dir(home)
    return [root / f"{bundle_id}.savedState" for bundle_id in ids]


def discard_macos_saved_application_state(
    *, platform=None, home=None, bundle_ids=None
) -> list[Path]:
    """Remove leftover AppKit savedState for this bundle. No-op off Darwin."""
    if not is_darwin(platform):
        return []
    removed = []
    for path in saved_state_paths(home, bundle_ids):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                removed.append(path)
    return removed


def disable_macos_window_restoration(*, platform=None) -> bool:
    """Disable window reopen via env and `defaults` without loading AppKit."""
    if not is_darwin(platform):
        return False
    os.environ["NSQuitAlwaysKeepsWindows"] = "NO"
    os.environ["ApplePersistenceIgnoreState"] = "YES"
    try:
        subprocess.run(
            [
                "defaults", "write", BUNDLE_ID,
                "NSQuitAlwaysKeepsWindows", "-bool", "false",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            [
                "defaults", "write", BUNDLE_ID,
                "ApplePersistenceIgnoreState", "-bool", "true",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass
    return True


def install_macos_secure_restorable_state(*, platform=None, home=None) -> bool:
    """Discard leftover savedState before QApplication / first AppKit use.

    Returns True on Darwin after the filesystem and defaults work, even if
    AppKit is absent. Linux/Windows is a no-op.
    """
    if not is_darwin(platform):
        return False
    disable_macos_window_restoration(platform=platform)
    discard_macos_saved_application_state(platform=platform, home=home)
    return True


def _load_mac_library(name: str):
    path = ctypes.util.find_library(name)
    if path is None:
        path = {
            "objc": "/usr/lib/libobjc.A.dylib",
            "Foundation": "/System/Library/Frameworks/Foundation.framework/Foundation",
            "AppKit": "/System/Library/Frameworks/AppKit.framework/AppKit",
        }.get(name)
    if not path:
        return None
    try:
        return ctypes.CDLL(path)
    except OSError:
        return None


class _ObjCBlock(ctypes.Structure):
    """libclosure block layout so we can invoke a void (^)(void) handler."""

    _fields_ = [
        ("isa", ctypes.c_void_p),
        ("flags", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("invoke", ctypes.c_void_p),
        ("descriptor", ctypes.c_void_p),
    ]


def _call_void_block(block_ptr) -> None:
    if not block_ptr:
        return
    block = ctypes.cast(block_ptr, ctypes.POINTER(_ObjCBlock)).contents
    if not block.invoke:
        return
    ctypes.CFUNCTYPE(None, ctypes.c_void_p)(block.invoke)(block_ptr)


def disable_macos_persistent_ui(*, platform=None) -> bool:
    """No-op NSPersistentUI restore so an oapp event cannot SIGILL.

    Call after QApplication() (AppKit is loaded) and before app.exec().
    Replaces restoreAllPersistentStateWithCompletionHandler: and invokes
    the completion block so launch can continue.
    """
    global _persistent_ui_disabled
    if not is_darwin(platform):
        return False
    if _persistent_ui_disabled:
        return True
    try:
        installed = _replace_persistent_ui_restore()
    except Exception:
        return False
    if installed:
        _persistent_ui_disabled = True
    return installed


def _replace_persistent_ui_restore() -> bool:
    libobjc = _load_mac_library("objc")
    if libobjc is None or _load_mac_library("AppKit") is None:
        return False

    libobjc.objc_getClass.restype = ctypes.c_void_p
    libobjc.objc_getClass.argtypes = [ctypes.c_char_p]
    libobjc.sel_registerName.restype = ctypes.c_void_p
    libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
    libobjc.class_replaceMethod.restype = ctypes.c_void_p
    libobjc.class_replaceMethod.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p
    ]

    manager = libobjc.objc_getClass(b"NSPersistentUIManager")
    if not manager:
        return False
    selector = libobjc.sel_registerName(
        b"restoreAllPersistentStateWithCompletionHandler:"
    )
    if not selector:
        return False

    restore_imp = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    )

    def _noop_restore(_self, _cmd, completion):
        _call_void_block(completion)

    imp = restore_imp(_noop_restore)
    _macos_objc_keepalive.extend((imp, _noop_restore))
    libobjc.class_replaceMethod(manager, selector, imp, b"v@:@?")
    return True
