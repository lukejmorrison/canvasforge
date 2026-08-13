# CanvasForge Agent Instructions

The primary agent/contributor guidelines live in [`AGENT.md`](AGENT.md) (philosophy,
conventions, workflows). Read that first. This file adds environment notes for
Cursor cloud agents.

## Cursor Cloud specific instructions

CanvasForge is a single-process **PyQt6 desktop GUI** app. The whole app is
`main.py` (a large intentional monolith); helpers are `image_library_panel.py`,
`undo_manager.py`, and `plugin_manager.py`. There is **no test suite, linter, or
build step** in this repo — "run the app" is the only way to exercise changes.

### Running (dev)

- The Python venv lives at `.venv` (created by the startup update script). Run with
  `.venv/bin/python main.py`. See `AGENT.md` for the canonical dev commands.
- This is a GUI app, so it needs a display or an offscreen Qt platform:
  - Headless smoke check (no display): `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py`
  - Real GUI for manual/computer-use testing: an X server is available on
    `DISPLAY=:1`. Launch with `DISPLAY=:1 QT_QPA_PLATFORM=xcb .venv/bin/python main.py`.
    (An Xvfb server on `:99` also exists if you need a throwaway display.)
- The Qt runtime needs system libraries (EGL/GL, xcb, fontconfig, etc.). These are
  baked into the VM image, not the update script; the app import will fail with
  `libEGL.so.1: cannot open shared object file` if they are ever missing.

### Useful launch behaviors (non-obvious)

- Passing an image path as an argument auto-loads it onto the canvas:
  `.venv/bin/python main.py /path/to/image.png`. This is the fastest way to get a
  non-empty canvas for testing annotate/export.
- `--screenshot-editor` / `--omarchy-editor` flags put it in screenshot-editor mode.
- Saving/exporting (File → Save, or `Ctrl+S`) writes a flattened PNG to
  `~/Pictures/CanvasForge/` (named `YYYY-MM-DD_CanvasForge_N.png`) unless changed in
  Preferences. Good end-to-end check: load an image, add an arrow/text, save, and
  confirm the PNG appears there.
- `save_canvas` prints `DEBUG ...` lines to stdout and the app prints a benign
  `setHighDpiScaleFactorRoundingPolicy must be called before...` warning on start —
  both are expected noise, not errors.
