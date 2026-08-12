# Problem Log: Omarchy UWSM App Lock on Launch

**Priority:** High  
**Status:** ✅ Closed (Resolved 2026-08-12)  
**Date Reported:** 2026-08-12  
**Date Resolved:** 2026-08-12  
**Affects:** Omarchy / Hyprland sessions that launch apps with `uwsm-app`

**Resolution:** Fixed the desktop entry Exec quoting, set `StartupWMClass=canvasforge` so launch-or-focus can find the window, disabled startup notification waits, reused a running instance, and removed the blocking `lspci` probe that delayed first paint.

---

## Problem Description

Launching CanvasForge from the Omarchy app menu shows a critical notification:

```
App failure
Could not acquire lock on '/run/user/1000/uwsm-app.lock'
```

The app never appears, or only appears after a retry.

## Environment

| Component | Details |
| --- | --- |
| OS | Omarchy Arch Linux |
| Session | Hyprland via UWSM |
| Launcher | `uwsm-app` (Omarchy app menu / `omarchy-launch-or-focus`) |
| Lock file | `$XDG_RUNTIME_DIR/uwsm-app.lock` |

## Root Cause Analysis

`uwsm-app` is a shell client that `flock`s `$XDG_RUNTIME_DIR/uwsm-app.lock` for 5 seconds while it talks to `wayland-wm-app-daemon.service`. If that lock is busy, it calls `notify-send` with title **App failure** and the exact lock path from the screenshot.

That happens when:

1. **A previous `uwsm-app` is still in the pipe handshake** because the desktop entry was hard to parse (`Exec="/abs/path"` quotes) or the daemon was wedged.
2. **The user launches again** because the first window never appeared. The first process was still in the 5-second `lspci` NVIDIA probe, so Hyprland had no `canvasforge` window to focus.
3. **`omarchy-launch-or-focus` cannot match the running window.** Wayland `app_id` is `canvasforge` (from `setDesktopFileName`), but the desktop file had no `StartupWMClass` and the documented Hyprland rules only matched `CanvasForge`. The launcher starts a second `uwsm-app` instead of focusing.

## Solution

1. Write desktop entries with an unquoted `Exec=... %F`, `TryExec`, `StartupWMClass=canvasforge`, and `StartupNotify=false`.
2. Reuse a running instance over a local socket so a second process hands off argv and exits.
3. Detect NVIDIA with `/dev/nvidiactl` (and friends) instead of `lspci`.
4. Document Hyprland rules as `class:^(canvasforge|CanvasForge)$`.

### Immediate workaround (already-wedged session)

```bash
systemctl --user restart wayland-wm-app-daemon.service
```

Then launch `canvasforge` from a terminal once to confirm the binary itself is fine.

## Testing Checklist

- [x] Desktop Exec lines are unquoted and include `%F`
- [x] `StartupWMClass=canvasforge` is set on installer, AUR, and Flatpak entries
- [x] Second process hands off to the first instead of opening another window
- [x] NVIDIA Wayland probe no longer shells out to `lspci`
- [ ] Launch from Omarchy app menu while CanvasForge is already in the scratchpad
- [ ] Print Screen while CanvasForge is already running

## Related Files

- `main.py`
- `scripts/install_canvasforge.sh`
- `packaging/aur/canvasforge-beta/PKGBUILD`
- `flatpak/com.lukejmorrison.CanvasForge.desktop`
- `README.md`
