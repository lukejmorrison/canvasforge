# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- Track new tooling such as stretch handles, fill/eyedropper workflows, Mojo experiments, SVG morphing, and future export options.

## [2025-12-05 09:00] Branded desktop icon & installer

- **Added:** New `assets/app_icons/canvasForge_app_icon.png` art now powers the main window icon so CanvasForge looks branded in the Pop!_OS dock and task switcher.
- **Updated:** `scripts/install_canvasforge.sh` copies the new icon into the system icon cache and keeps the `.desktop` entry under Audio & Video in sync.
- **Documented:** `README.md` now calls out the desktop-ready icon plus the helper installer script.
- **New:** Flatpak manifest (`flatpak/com.lukejmorrison.CanvasForge.yml`) plus `scripts/build_flatpak.sh` automate sandboxed installs via `flatpak-builder` for Pop!_OS, auto-installing the KDE 6.8 runtime/SDK on first run and caching PyPI wheels on the host so the sandbox builds offline.

## [2025-12-04 17:30] Simplified Icon Loading

- **Refactored:** Removed resolution information from icon filenames (e.g., `toolbar_icon_pointer.png`) for easier maintenance and customization.
- **Improved:** `get_icon()` now supports automatic format detection, prioritizing `.png` files and falling back to `.svg` if a PNG is not found. This allows users to mix and match file types without changing code.

## [2025-12-04 17:15] UI Polish & Placeholders

- **Updated:** Toolbar icons are now larger (48x48) and use a consistent font style (bold, 10pt) with text displayed under the icons for better readability on high-res monitors.
- **Added:** Placeholder SVG icons for tools that previously lacked graphics (Rotate, Scale, Snap Grid, etc.), allowing for easy customization by replacing the file.

## [2025-12-04 17:00] Dark Mode & Icon Refresh

- **Added:** Dark mode support using the Fusion style and a custom dark palette for a modern, premium look.
- **Updated:** Toolbar icons are now loaded from `assets/toolbar_icons/` with resolution-specific filenames (e.g., `toolbar_icon_pointer_95x108.png`), making it easy for users to customize the interface by replacing these files.
- **Refactored:** Renamed all toolbar assets to match their tool/feature usage for better clarity and maintainability.

## [2025-12-03 23:38] Late-night flatten & save polish (see `CanvasForge_251203_v15.md`)

- **Added:** `Flatten Selected`/`Flatten All`, Delete, Bring Forward, Send Backward, and status-bar cursor readouts, giving the layer list parity with scene operations.
- **Added:** Save workflow powered by `QSettings` + `Pathlib` that auto-creates a configurable Pictures/CanvasForge folder, hides blue handles/overlays before rendering, and restores the previous selection afterward.
- **Added:** Context-menu forwarding wrappers (`CanvasRectItem`, `CanvasEllipseItem`, `CanvasTextItem`, `VectorItem`, `RasterItem`, `SelectionOverlay`) so every object—including overlay rectangles—pipes right-clicks into the shared action menu.
- **Added:** Text editing refinements (`CanvasTextItem`) that gate context menus while editing, support Escape to exit, and keep transform origins synced with content changes.
- **Added:** Artifact presets folder (`artifacts/`) and screenshot capture directory, as captured in the v15 directory listing.
- **Fixed / Learned:** Hid overlay items before saving to avoid exported PNGs with blue controls (issue reproduced while looking at `text_20251203_233526_129.txt`).
- **Fixed / Learned:** `_ensure_save_directory` simplified to avoid referencing widgets during startup, eliminating the crash logged after the default-folder refactor.
- **Fixed / Learned:** Normalized `QPoint` vs `QPointF` handling in context menus (`_normalize_screen_point`) after a `QPoint` lacked `.toPoint()` when clicking post-save.

## [2025-12-03 18:29] Selection overlay + text-flow revamp (see `CanvasForge_251203_v13.md` & `v14`)

- **Added:** Selection overlay objects with resize-handle callbacks and their own context menus so raster cutouts can be repositioned/rescaled before extraction.
- **Added:** Handle event hooks (`handle_resize_press/drag/release`) that allow overlays to reuse the same blue handles as regular items.
- **Added:** Early versions of the cursor-forwarding system plus better zoom-aware placement logic for selection drops.
- **Fixed / Learned:** Switched overlay fill/pen alpha application to `QColor.setAlpha()` after experiment logs (`text_20251203_150137_390.txt`) showed `QColor("blue", 128)` crashes.
- **Fixed / Learned:** Captured additional clipboard text samples (e.g., `text_20251203_180418_329.txt`) verifying that the logging pipeline still worked while overlays were active.

## [2025-12-03 16:17] Selection handles & raster cutouts (see `CanvasForge_251203_v8.md`–`v10`)

- **Added:** `SelectionHandles` and `FillMode` abstractions so every raster/vector/text/shape item gets live blue handles plus rotate knobs.
- **Added:** Raster cutout workflow (`startSelection`, `updateSelection`, `endSelection`) that copies a region, optionally auto-fills the hole, and spawns a draggable item at the drop cursor.
- **Added:** Zoom factor tracking inside `CanvasView` to keep cutout offsets accurate regardless of viewport scaling.
- **Added:** Large toolbar refresh introducing pointer/select separation, selection marquee mode, and scroll-wheel zoom guardrails.
- **Fixed / Learned:** Addressed crashes encountered when handles tried to set alpha directly in the `QColor` constructor (error logged in `text_20251203_150137_390.txt`).
- **Fixed / Learned:** Hardened raster pixmap conversion to ARGB so flatten/cutout renders no longer produced format errors.

## [2025-12-03 13:24] Toolbar assets & repository UX (see `CanvasForge_251203_v4.md`–`v7`)

- **Added:** Introduced `assets/toolbar_icons/` and wiring for icon-based actions, making the tool switcher easier to scan.
- **Added:** Began capturing clipboard snippets under `pasted_logs/`, with the first text specimen stored in `text_20251203_125831_357.txt` for reproducibility.
- **Added:** Expanded tool palette with Rotate, Scale, Align-to-grid, and Selection-move scaffolding, plus early status logging to `output.log`.
- **Fixed / Learned:** Interpreted the syntax error shown in the first `pasted_logs` entry (missing colon after `elif ToolType.SELECT`) and corrected the toolbar setup accordingly.

## [2025-12-03 12:53] Clipboard-aware transforms (see `CanvasForge_251203_v2.md` & `v3`)

- **Added:** Rich clipboard ingest—context-menu paste on the canvas logs text, bitmaps, and SVG payloads to `pasted_logs/` before instantiating scene items.
- **Added:** Rotation and non-uniform scaling tools with mouse-drag gestures and transform-origin bookkeeping.
- **Added:** Inkscape round-trip editing for vector artifacts via temporary SVG files, giving complex callouts an external editor path.
- **Added:** Scene ↔ layer-list selection synchronization plus drag/drop cloning that rehydrates bitmap bytes to keep repository entries alive.
- **Fixed / Learned:** Introduced drag/drop mime guards so only repository drags are accepted (preventing stray Qt drags from raising exceptions).
- **Fixed / Learned:** Logged Gnome schema warnings and clipboard contents, providing the first evidence that the glue scripts behaved on Pop!_OS (`text_20251203_141521_382.txt`).

## [2025-12-03 07:56] Prototype bootstrap (see `CanvasForge_251203_v1.md`)

- **Added:** Initial PyQt6 scene with draggable raster/vector/text items, a repository panel, synchronized layer list, and basic rectangle/ellipse/text drawing tools.
- **Added:** Drag/drop from the repository onto the canvas along with immediate text editing on double-click.
- **Added:** Simple flatten-to-PNG command that renders the entire scene bounding rect.
