# Problem Log: Wayland/COSMIC Desktop Lockup

**Priority:** High  
**Status:** ✅ Closed (Resolved 2025-12-08)  
**Date Reported:** 2025-12-08  
**Date Resolved:** 2025-12-08  
**Affects:** Pop!_OS 24.04 LTS with COSMIC Desktop (Beta) + NVIDIA GPU

**Resolution:** Implemented automatic X11/XWayland backend detection in `main.py` and added `--env=QT_QPA_PLATFORM=xcb` to Flatpak manifest. System lockups no longer occur.  

---

## Problem Description

CanvasForge causes complete system UI lockup when launched on Pop!_OS with COSMIC desktop environment. The screen freezes, keyboard and mouse input are unresponsive, and a hard reboot is required to recover.

## Environment

| Component | Details |
|-----------|---------|
| OS | Pop!_OS 24.04 LTS |
| Desktop | COSMIC (Beta) |
| Windowing | Wayland |
| GPU | NVIDIA GeForce GTX 1070 Ti |
| Kernel | 6.17.4-76061704-generic |
| Python | 3.x with PyQt6 |

## Root Cause Analysis

The lockup is caused by **PyQt6's native Wayland backend conflicting with NVIDIA drivers and the COSMIC compositor**.

### Crash Log Evidence

From `journalctl -b -1`:

```
cosmic-panel: [EGL] 0x3004 (BAD_ATTRIBUTE) eglCreateSyncKHR: EGL_BAD_ATTRIBUTE error
cosmic-session: [WARN wgpu_hal::vulkan] Suboptimal present of frame 0
cosmic-comp: Client bug: Unable to re-configure repositioned popup.
cosmic-comp: Failed to force redraw for corner radius change.
```

These errors indicate:
1. EGL/GPU synchronization failures between Qt and the compositor
2. Vulkan frame presentation issues
3. Wayland popup window protocol violations
4. Compositor rendering failures

### Why It Happens

- PyQt6 defaults to native Wayland on Wayland sessions
- NVIDIA's Wayland support is still maturing
- COSMIC compositor is in beta with known edge cases
- CanvasForge's graphics-intensive operations (QGraphicsScene, SVG rendering) stress the compositor

---

## Solution

### Immediate Workaround

Force CanvasForge to use X11 (via XWayland) instead of native Wayland by setting:

```bash
QT_QPA_PLATFORM=xcb
```

### Implementation Options

#### Option 1: Update Launcher Scripts

Modify `scripts/install_canvasforge.sh` to set the environment variable in the launcher:

```bash
#!/bin/bash
export QT_QPA_PLATFORM=xcb
cd /path/to/canvasforge
source .venv/bin/activate
python main.py "$@"
```

#### Option 2: Update Desktop Entry

Ensure the `.desktop` file uses:

```ini
Exec=env QT_QPA_PLATFORM=xcb /path/to/canvasforge-launcher
```

#### Option 3: Update Flatpak Manifest

Add to the Flatpak build configuration:

```yaml
finish-args:
  - --env=QT_QPA_PLATFORM=xcb
```

Or users can override manually:

```bash
flatpak override --user --env=QT_QPA_PLATFORM=xcb com.lukejmorrison.CanvasForge
```

#### Option 4: Set in Python Code (main.py)

Add at the very top of `main.py` before any Qt imports:

```python
import os
import sys

# Force X11 backend on Wayland+NVIDIA to prevent compositor lockups
# See: ProblemLog_WaylandCosmicLockup.md
if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
    # Check for NVIDIA GPU
    try:
        import subprocess
        result = subprocess.run(['lspci'], capture_output=True, text=True)
        if 'NVIDIA' in result.stdout:
            os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
    except Exception:
        pass  # Fall through to default behavior

from PyQt6.QtWidgets import QApplication
# ... rest of imports
```

---

## Recommended Implementation

**Option 4 (code-level detection)** is the most user-friendly as it:
- Automatically detects Wayland + NVIDIA
- Requires no manual user configuration
- Works for all launch methods (CLI, desktop, Flatpak)
- Falls back to native Wayland on non-NVIDIA systems

However, **Option 3 (Flatpak manifest)** should also be applied for the Flatpak distribution to ensure consistent behavior.

---

## Testing Checklist

- [x] Test with `QT_QPA_PLATFORM=xcb python main.py` - confirm no lockup
- [x] Test Flatpak manifest updated with `--env=QT_QPA_PLATFORM=xcb`
- [x] Verify app functionality is unchanged under XWayland
- [ ] Test on non-NVIDIA system to ensure no regressions
- [ ] Test on X11 session (should work normally)

---

## Additional Issue Found During Testing

**Date:** 2025-12-08

When testing with the X11 workaround, an unrelated import error was discovered:

```
Traceback (most recent call last):
  File "/home/luke/dev/CanvasForge/main.py", line 21, in <module>
    from image_library_panel import ImageLibraryPanel
  File "/home/luke/dev/CanvasForge/image_library_panel.py", line 33, in <module>
    from PyQt6.QtWidgets import QFileSystemModel
ImportError: cannot import name 'QFileSystemModel' from 'PyQt6.QtWidgets'
```

**Fix Required:** `QFileSystemModel` is in `PyQt6.QtGui`, not `PyQt6.QtWidgets`.

In `image_library_panel.py`, line 33, change:

```python
# Wrong:
from PyQt6.QtWidgets import QFileSystemModel

# Correct:
from PyQt6.QtGui import QFileSystemModel
```

**Status:** ✅ Fixed on 2025-12-08

---

## Related Issues

- Pop!_OS COSMIC is beta software - some instability expected
- NVIDIA + Wayland is a known problematic combination
- PyQt6 Wayland backend less mature than X11 backend
- Similar issues reported with other Qt apps on COSMIC

## References

- COSMIC Compositor Issues: https://github.com/pop-os/cosmic-comp/issues
- Qt Wayland Platform Plugin: https://doc.qt.io/qt-6/qpa.html
- NVIDIA Wayland Support: https://wiki.archlinux.org/title/Wayland#NVIDIA

---

## Resolution

**Status:** ✅ Implemented on 2025-12-08

The following fixes have been applied:

1. **main.py**: Added Wayland+NVIDIA auto-detection that sets `QT_QPA_PLATFORM=xcb` before Qt imports
2. **Flatpak manifest**: Added `--env=QT_QPA_PLATFORM=xcb` to `finish-args`
3. **image_library_panel.py**: Fixed `QFileSystemModel` import (moved from `QtWidgets` to `QtGui`)

The application now launches without locking up the COSMIC compositor. Native Wayland support may improve as COSMIC and NVIDIA drivers mature.
