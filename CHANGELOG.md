# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0-beta.6] - 2026-05-14 18:40

### Fixed
- **Grok TUI local path rejection on image paste:** For the "Clipboard (base64 JPEG)" target we now completely omit `setUrls()` (and therefore the `file://` entry in text/uri-list). Previously the local save path was still being advertised on the clipboard, causing Grok TUI to sometimes pick a local filesystem path for the `image_url` field and get the "must be base64 or URL" 400 error. The target now only ever exposes the raw `image/jpeg` bytes + the `data:image/jpeg;base64,...` string — nothing local leaks onto the clipboard.
- **Grok TUI JPEG clipboard paste (follow-up):** The removal of `setImageData()` from beta.5 is kept so only JPEG (never a PNG fallback) is offered for the binary image part.

## [0.6.0-beta.5] - 2026-05-14 18:19

### Fixed
- **Grok TUI JPEG clipboard paste:** Removed `setImageData()` for the "Clipboard (base64 JPEG)" target. This prevents Qt from auto-registering an `image/png` fallback, ensuring native clipboard consumers like Grok TUI receive only the properly encoded `image/jpeg` bytes (resized/flattened JPEG) when pasting images. The base64 data URL is still available in text for tools that need it.

## [0.6.0-beta.4] - 2026-05-14

### Changed
- **Grok clipboard JPEG defaults:** Clipboard base64 handoff now saves and copies JPEG images instead of PNG, scaling the longest side to 1440px and encoding at quality 88 to avoid Grok TUI dimension and base64 warnings.

## [0.6.0-beta.3] - 2026-05-14

### Added
- **Grok-friendly clipboard encoding:** Added a Clipboard base64 image target that copies a `data:image/png;base64,...` payload and PNG clipboard image data for tools that reject local filesystem paths.
- **Versioned app menu label:** The AUR desktop launcher now includes the beta version in the Omarchy app menu name.

## [0.6.0-beta.2] - 2026-05-14

### Added
- **Clipboard agent handoff:** Agent preferences now include a Clipboard target that saves the selected layers as a PNG in the configured CanvasForge save folder, copies the image path, and triggers a desktop notification.

## [0.6.0-beta.1] - 2026-05-08

### Added
- **Beta release channel:** Switched CanvasForge to explicit beta versioning so GitHub prereleases and Arch/Omarchy AUR updates can track the same tag series.
- **AUR beta packaging:** Added a `canvasforge-beta` PKGBUILD workflow that installs CanvasForge into standard Linux system paths for Arch and Omarchy users.
- **Release automation:** Added helper scripts for preparing prerelease tags, GitHub prereleases, and refreshed AUR metadata.

## [2026-05-08 06:15] Clipboard canvas paste and toolbar fit

### Added
- **Canvas-centered clipboard paste:** File > Paste / Ctrl+V now pastes clipboard images, SVGs, file URLs, and text onto the visible canvas instead of only adding image data to the repository. New pasted items expand the canvas bounds when needed.
- **Distinct Send to Agent icon:** Added a dedicated Send to Agent toolbar icon so it no longer shares the Callout visual language.

### Fixed
- **Toolbar high-scale fit:** Toolbar auto-fit now targets a single row and can shrink to smaller icon-only buttons when larger OS font or display scaling would otherwise wrap tools onto a second line.
- **Toolbar hover labels:** Toolbar icons now keep direct tooltip/accessible text on the actual icon buttons, so descriptions still appear when labels are hidden in icon-only auto-fit mode.
- **Callout toolbar identity:** Refreshed the Callout plugin icon so it reads as a template/callout action rather than a duplicate of Send to Agent.

## [2026-05-01 07:34] Canvas size presets and info tag

### Added
- **Alt-resize canvas presets:** Holding Alt while dragging a canvas edge or corner now snaps the workspace to common social, video, web, X.com, and connected-monitor sizes. The live resize readout names the snapped preset.
- **Canvas info tag:** A small tag below the canvas now shows resolution, aspect ratio, PNG image type, and transparency status.

## [2026-05-01 00:36] Smooth animated wheel zoom

### Added
- **Smooth Photoshop-style zoom:** Wheel zoom now uses cursor anchoring, gentler multiplicative scaling, and optional 60 FPS animation with configurable sensitivity so fast wheel flicks glide instead of jumping.

## [2026-05-01 00:28] Photoshop-style wheel zoom preference

### Added
- **Zoom with Scroll Wheel preference:** Canvas preferences now include a Photoshop-style wheel behavior toggle. When enabled, wheel zooms at the cursor; when disabled, wheel pans/scrolls vertically and Alt+wheel zooms at the cursor.

## [2026-05-01 00:24] View menu controls

### Added
- **View menu:** Added zoom in/out, zoom to fit, shrink-to-fit, actual size, pixel grid, background color choices, sidebar visibility, details focus, library focus, and recent-captures focus actions.

## [2026-05-01 00:15] Modifier-constrained resize handles

### Added
- **Resize handle modifiers:** Canvas, cutout, blur/highlight, and generic item handles now use the standard Shift/Alt/Ctrl resize constraints: default proportional scaling, Shift/Ctrl independent axes, Alt center-based scaling, Ctrl+Shift shear-style transforms where supported, and Ctrl+Alt+Shift perspective-style transforms where supported.

## [2026-05-01 00:00] Canvas resize readout

### Added
- **Live canvas size readout:** Dragging a canvas edge or corner now shows the current canvas size plus signed resize deltas; corner drags report both width and height changes.

## [2026-04-30 19:53] Selection save + agent handoff toolbar

### Added
- **Selected-layer export:** Toolbar disk action saves only the selected canvas items to the configured CanvasForge save folder.
- **Agent handoff:** Toolbar Send to Agent action bundles the selected image plus `annotations.json` and sends it through a configurable command or HTTP endpoint for Codex, Claude, OpenClaw, or Wizwam Agent Platform workflows.
- **VS Code Codex handoff:** Added a target that opens the selected-image bundle in VS Code and copies a ready `codex_prompt.md` prompt to the clipboard.
- **Select All:** Edit > Select All Canvas Items and Ctrl+A select every active layer.
- **Cutout tool:** The old raster-region selection workflow remains available as a separate Cutout toolbar action.
- **Drag-and-drop toolbar editing:** Preferences > Toolbar rows can now be dragged to reorder toolbar buttons, with Move Up/Down kept as fallback controls.

### Fixed
- **Select tool behavior:** The toolbar Select button now activates object selection/marquee selection, with Ctrl/Cmd-click toggling individual items.
- **Toolbar reorder crash:** Fixed the missing live reorder hook that crashed Preferences when moving toolbar items.

## [1.5.0] - 2025-12-10

### Added
- **Appearance Settings:** New "Appearance" tab in Preferences with Icon Theme support
  - Users can select different icon themes stored in `assets/toolbar_icons/`
  - Dynamic discovery of new themes folder
- **Robust Icon Loading:** Enhanced icon system that prioritizes SVG files and handles missing assets gracefully
  - Automatic fallback to PNG if SVG missing
  - Automatic fallback to global assets if plugin asset missing
  - Visual placeholder generation for completely missing icons (dashed red box with text)
- **Plugin System Polish:**
  - Improved `plugin_manager.py` to auto-resolve icons using the global resource system
  - Validates plugin icons against both .svg and .png extensions
- **Platform Support:** Installer verified on Pop!_OS and Omarchy Arch Linux, with improved retry logic for Arch rolling releases

### Changed
- **Crop Tool:** Updated to use the new robust icon loading system, fixing missing icon issues
- **Preferences:** Reorganized tabs to include Appearance settings


## [1.4.0] - 2025-12-09

### Added
- **Plugin System:** Full modular plugin architecture for extending CanvasForge
  - `PluginManager` class for discovering, loading, and managing plugins
  - `PluginAPI` class exposing controlled access to scene, items, and UI
  - Plugin manifest format (`manifest.json`) with permissions, hooks, and dependencies
  - Plugins tab in Preferences for managing installed plugins
  - "Open Plugins Folder" button for easy access to user plugins directory
  - Configurable editor path for plugin development (defaults to VS Code)
  - Plugin reload functionality without restarting app
  
- **Undo/Redo System:** Comprehensive undo/redo that works across the entire app
  - `UndoManager` class with undo/redo stacks and action groups
  - `UndoableAction` base class for all reversible operations
  - Built-in action types: `ImageEditAction`, `MoveItemAction`, `TransformItemAction`, etc.
  - Edit > Undo (Ctrl+Z) and Edit > Redo (Ctrl+Shift+Z) menu items
  - Dynamic menu text showing action description (e.g., "Undo Crop Image")
  
- **Crop Tool Plugin:** First bundled plugin demonstrating the plugin system
  - Crop any raster image on the canvas
  - Visual crop overlay with adjustable region
  - Full undo/redo support
  - Keyboard shortcuts: C to activate, Enter to apply, Escape to cancel
  - Located in `plugins/crop_tool/`

### Changed
- Version bumped to 1.4.0

## [1.3.0] - 2025-12-09

### Added
- **Window Position Persistence:** App now remembers window position, size, and monitor between sessions
  - New "Window" tab in Preferences with "Remember window position and size" option
  - Window state saved automatically when closing
  - Respects system default (mouse cursor position) when disabled
- **File > Exit menu item:** Added Exit option with Ctrl+Q shortcut
- **Canvas Import Settings:** New preferences in Edit > Preferences > Canvas tab:
  - "After adding image" behavior: Keep current view, Pan to show new image, Zoom to fit all items, or Zoom to fit new item
  - "Scale down images larger than viewport" option to auto-scale large imports
- **Fit view methods:** Added `fit_all_items()`, `fit_item()`, and `pan_to_item()` methods to CanvasView

### Fixed
- **Critical crash fix:** Fixed RuntimeError "wrapped C/C++ object deleted" when deleting items
  - Added `sip.isdeleted()` checks before accessing graphics items
  - Block signals during item removal to prevent stale reference access
- **Image Library selection:** Adding images from library now correctly selects only the new item
- **Image Library refresh/sort sync:** Refresh button re-applies current sort settings
- **Date display positioning:** Date flows after filename, ensuring filename always visible

## [1.2.0] - 2025-12-09

### Added
- **Image Library Display Update:** Redesigned file listing with:
  - Small 48x48 image thumbnails showing actual previews (not file icons)
  - Left-justified filename column for better readability
  - YYMMDD HHMMSS date/time format visible inline for sort verification
  - Background thumbnail generation with caching for smooth performance
- **ThumbnailCache class:** Async thumbnail generator that queues image loading to prevent UI blocking
- **ImageLibraryDelegate class:** Custom `QStyledItemDelegate` for the new row-based display

### Changed
- **Image Library view mode:** Switched from IconMode (grid) to ListMode (rows) for columnar layout
- **Removed zoom slider:** Zoom control removed since thumbnails are now fixed-size in list view

### Technical
- Thumbnail cache handles 500+ images with LRU eviction
- Background generation uses `QTimer.singleShot` queue pattern
- Date format constant `DATE_FORMAT = "yyMMdd HHmmss"` shared across delegate and properties

## [1.1.0] - 2025-12-08

### Added
- **Preferences Dialog:** New unified settings dialog accessible via Edit > Preferences (Ctrl+,) with organized tabs:
  - **Folders tab:** Clear settings for "Save canvas to" (export destination) and "Screenshot folder" (image library source) with descriptions
  - **Canvas tab:** Placeholder for future canvas-related settings
  - **About tab:** App info, feature list, version number, and credits
- **Image Library Panel:** New sidebar widget (`image_library_panel.py`) for browsing screenshots with thumbnails, search, sorting, and drag-to-canvas functionality
- **Version tracking:** Added `__version__ = "1.1.0"` constant to main.py

### Fixed
- **Wayland/COSMIC lockup:** Implemented automatic X11/XWayland backend detection for NVIDIA GPUs on Wayland sessions to prevent compositor lockups. Added `--env=QT_QPA_PLATFORM=xcb` to Flatpak manifest.
- **QFileSystemModel import:** Fixed incorrect import from `QtWidgets` to `QtGui` in image_library_panel.py
- **Save function error handling:** Added debug logging and return value checking for `image.save()` operations

### Changed
- **Menu reorganization:** Removed separate "Change Save Folder..." and "Change Image Library Folder..." menu items in favor of unified Preferences dialog
- **Improved UX:** Folder settings now have clear descriptions explaining their purpose

### Closed Issues
- ProblemLog_WaylandCosmicLockup.md - System lockup on Wayland+NVIDIA+COSMIC
- ProblemLog_SaveFunctionNotWorking.md - Confusing folder settings UI

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
