# Feature Request: CanvasForge Image Library

## Document Metadata
| Field | Value |
| --- | --- |
| Doc ID | FR-20251204-ImageLibrary |
| Version | v1.1 |
| Date | 2025-12-06 11:00 |
| Owner / Author | Grok (xAI Assistant) |
| Status | Draft |
| Priority | Medium |
| Changelog Tag | [Unreleased] CanvasForge Image Library |
| Related Files | main.py; assets/toolbar_icons/; TODO.md; README.md |

## Project Context
- `main.py` hosts everything: `MainWindow` builds a `QHBoxLayout` with `CanvasView` (3/4 width) and a right-side `QVBoxLayout` for the Repository (`ArtifactList`) and Layers (`LayerList`).
- `CanvasView` already supports drag/drop from `ArtifactList`, clipboard pastes, and exports (flatten) via `MainWindow` helpers; it is the correct integration point for dropping library thumbnails directly to the canvas.
- Asset folders: `assets/toolbar_icons/` (already in use) and `assets/app_icons/` (window icon). A future `assets/image_library/` space may store UI art or cached thumbnails if needed.
- Persistence/logging: screenshots of pasted assets live under `pasted_logs/`, flattened renders under `artifacts/`, and user exports default to `~/Pictures/CanvasForge`. The library should monitor `~/Pictures/Screenshots` (with fallbacks) without disturbing those existing flows.
- Packaging: `flatpak/com.lukejmorrison.CanvasForge.yml` and `scripts/install_canvasforge.sh` must copy any new library assets or schema defaults so sandboxed builds can still find the screenshot folder.

## Overview
The CanvasForge Image Library introduces a dedicated panel for browsing and managing screenshot assets sourced from the user’s OS-specific Screenshots folder (for example `~/Pictures/Screenshots` on Pop!_OS). It provides thumbnail previews, sorting, search, zoom controls, and drag-to-canvas import so users can reference captured material without leaving CanvasForge. The widget docks alongside the Repository and Layers panels to preserve the 3:1 canvas dominance while keeping external assets one click away.

## Goals
- **Improve Asset Discoverability**: Keep recent screenshots visible so designers avoid manual file navigation.
- **Streamline Import/Export**: Enable drag-to-canvas and provide a one-click export button that flattens scenes back into the monitored Screenshots folder.
- **Enhance Workflow Efficiency**: Offer sort/search/zoom controls so large screenshot libraries stay manageable.
- **Remain Modular**: Encapsulate the feature inside a reusable widget that could later move into a `widgets/` package or native binding layer.

## Requirements

### Architecture Fit
- Replace the current `main_layout = QHBoxLayout(...)` arrangement with a `QSplitter` stack: `[ImageLibraryPanel | CanvasView | RightSidebar]`. This keeps proportional resizing while allowing the library to collapse when not in use.
- Introduce an `ImageLibraryPanel(QWidget)` in a new module (for example `image_library_panel.py`) that exposes signals such as `assetActivated(path: Path)` and `exportRequested()`.
- Keep Repository (`ArtifactList`) and Layers (`LayerList`) untouched so existing project flows remain stable.
- Provide a lightweight `ImageMetadataDock` (optional) as a `QDockWidget` or footer inside the panel to surface the selected file’s name, size, and modified date.

### Functional Requirements
1. **Library Panel Widget**
   - Resizable sidebar hosted in the splitter; default width ~220px.
   - Header row with folder selector (All / Favorites / Custom paths), a search field, and refresh button.
   - Center grid using `QListView` or `QGridView` in IconMode, displaying 100px thumbnails with selection highlighting.
   - Footer bar with sort dropdown (Date Modified ↓ default, Date Created, Name, Size), zoom slider (50%-200%), and an `Export Canvas` button tied to flattening.
2. **Data Binding**
   - `QFileSystemModel` (root = detected Screenshots folder; fallback to `~/Pictures` then `~/Pictures/CanvasForge`).
   - `QSortFilterProxyModel` for search text and sorting strategy.
   - `QFileSystemWatcher` (or polling timer) to refresh the proxy when new files appear.
   - Acceptable formats: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.svg`.
3. **Interactions**
   - Dragging a thumbnail emits a `mimeData` payload with `Qt.Url` entries so `CanvasView.dropEvent` can reuse `_paste_file_path` (already implemented).
   - Double-clicking a thumbnail emits `assetActivated(path)`; `MainWindow` calls `add_artifact(path)` and drops the new layer near the viewport center.
   - Selection updates the properties footer plus a preview swatch.
   - Export button triggers `MainWindow.flatten_all` (or selected layers) and writes to the monitored folder with timestamped filenames (e.g., `canvas_export_YYYYMMDD_HHMM.png`).

### UI & Accessibility
- Follow the existing dark palette (Fusion style) so the panel blends into the theme.
- Provide keyboard navigation: arrow keys move selection, `Enter` imports, `Ctrl+F` focuses the search box, and `Ctrl+R` refreshes the folder.
- Display tooltips for buttons and show file metadata inline (name, resolution, size, modified date).
- Persist splitter sizes via `QSettings` using the same key family already used for `default_save_dir`.

### Non-Functional Requirements
- Load 100 thumbnails in <500ms and remain responsive with 500+ files via lazy thumbnail creation (store `QPixmap` cache keyed by absolute path + mtime).
- No new pip dependencies; rely entirely on PyQt6 components already bundled.
- Read-only access to the screenshot folder unless exporting; validate write permissions before enabling the export button.
- Strings routed through existing translation hooks so future `QtLinguist` work can localize labels.

### Technical Notes
- Restructure `MainWindow` to:
  1. Instantiate `ImageLibraryPanel` before `CanvasView`.
  2. Replace `main_layout.addWidget(...)` with a `QSplitter(Qt.Horizontal)` where index 0 = library, 1 = canvas, 2 = right sidebar.
  3. Connect panel signals:
     - `panel.assetActivated.connect(self._import_library_asset)`
     - `panel.assetDropped.connect(self._drop_asset_onto_canvas)` (optional helper)
     - `panel.exportRequested.connect(self.flatten_all)` (or new method that calls `_flatten_items`).
- Extend `CanvasView.dragEnterEvent`/`dropEvent` to accept `mimeData.hasUrls()` so library drags behave like OS file drops (existing `_paste_file_path` already handles this path).
- Share the screenshot-path resolver between the panel and `MainWindow` (utility like `paths.get_screenshot_folder()` to keep logic centralized). Store the chosen folder in `QSettings("CanvasForge", "CanvasForge")` under `screenshot_library_dir`.
- Consider optional `ImageLibraryController` class to wrap model/watcher logic, simplifying unit tests.

## Dependencies
- `main.py`: `MainWindow`, `CanvasView`, `add_artifact`, flatten helpers.
- Qt classes from PyQt6 already vendored with the flatpak wheels: `QFileSystemModel`, `QSortFilterProxyModel`, `QFileSystemWatcher`, `QSplitter`, `QStyledItemDelegate`, `QSettings`.
- Installer + Flatpak scripts must ensure the screenshot folder path is accessible or documented for sandbox permissions.

## Risks
- **Path Variability**: Some distros rename the Screenshots folder. Mitigate with `QStandardPaths.PicturesLocation` + user override UI.
- **Performance**: Very large folders (>1,000 images) could lag. Use background thumbnail generation (`QtConcurrent` or queued `QTimer.singleShot`) and cache results.
- **Sandbox Permissions**: Flatpak builds may not have direct access to `~/Pictures/Screenshots`. Document the required portal permissions and consider adding a folder picker fallback.
- **Theme Drift**: New widgets should reuse the dark palette; share stylesheets so sliders/buttons match the toolbar aesthetic.

## Success Metrics
- Library loads in <2s for 100 images on Pop!_OS reference hardware (after thumbnails cached).
- Drag-and-drop from the library creates scene items with no console warnings.
- Export button writes flattened PNGs to the monitored folder with correct timestamps and hides overlay handles (reusing the existing flatten logic).
- User testing shows at least a 50% reduction in context switches to the OS file manager during workshops.

## Implementation Plan
| Step | Scope | Key Files / Classes | Notes |
| --- | --- | --- | --- |
| 1 | Create `image_library_panel.py` with `ImageLibraryPanel`, `ImageLibraryProperties`, and a shared path resolver helper. | `image_library_panel.py` (new) | Build UI scaffold, wire up `QFileSystemModel` + proxy, expose Qt signals. |
| 2 | Swap `QHBoxLayout` for `QSplitter` in `MainWindow` so the library can dock left of `CanvasView`. | `main.py` (`MainWindow.__init__`) | Remove fixed stretch factors; persist splitter widths via `QSettings`. |
| 3 | Connect panel signals to new slots: `_import_library_asset`, `_export_canvas_to_library`, `_set_library_root`. | `main.py` | Slots should reuse `add_artifact`, `flatten_all`, and `save_canvas` logic rather than duplicating code. |
| 4 | Extend `CanvasView` drag/drop to accept file URLs emitted by the library panel. | `CanvasView.dragEnterEvent`, `dropEvent`, `_paste_file_path` | Accept `mimeData.hasUrls()` even when the source is the library widget, ensuring consistent behavior across OS drags. |
| 5 | Add screenshot-path setting + picker so users can retarget the library if their OS stores captures elsewhere. | `main.py` (new menu action) | Store under `screenshot_library_dir`; update watcher + panel when changed. |
| 6 | Update docs and TODO: mention the new sidebar, include a troubleshooting note in `README.md`, and add a Medium-priority TODO entry. | `README.md`, `TODO.md` | README section should explain how to enable/disable the panel and where files are read from. |
| 7 | QA + polish: test on Pop!_OS and Windows, ensure Flatpak manifest bundles any new modules, capture screenshots for release notes. | Manual tests, `flatpak/` manifest | Document findings in `CHANGELOG.md` before release. |

## Test Plan
- **Model tests**: Unit-test the path resolver and sorter using a temporary directory populated with fake screenshots (Qt Test or pytest-qt if introduced later).
- **Manual smoke**: Create 200 dummy PNGs, verify scroll/zoom/search performance, drag thumbnails to various canvas zoom levels, and confirm exported files hide selection overlays.
- **Regression**: Re-run flatten/save workflows to ensure existing behavior is unchanged when the library panel is collapsed or disabled.
- **Flatpak**: Build via `scripts/build_flatpak.sh`, confirm the sandbox can read the screenshot folder (or show a dialog requesting access).

## Next Steps
1. Land Steps 1-4 in a feature branch, including unit tests for the resolver where feasible.
2. Update README/TODO/Flatpak manifest (Steps 5-6) and gather screenshots for release notes.
3. Draft the `[YYYY-MM-DD HH:MM] Image Library` changelog entry once the feature merges; update this doc’s `Changelog Tag` plus timeline row to the final timestamp.

## Timeline

| Date (UTC) | Event |
| --- | --- |
| 2025-12-06 18:20 | `[Unreleased] CanvasForge Image Library` work started: created `image_library_panel.py`, refactored `main.py` around a horizontal splitter, wired export/import signals, and documented the feature in `README.md`/`TODO.md`. |


```bash
# Append to TODO.md under Medium Priority
cat <<'EOF' >> TODO.md
- **CanvasForge Image Library:** Integrate left sidebar panel for Screenshots folder browsing with thumbnails, search/sort/zoom, drag-to-canvas, auto-refresh, and export-to-screenshots support (see featurerequest/CanvasForge_Image_Library.md).
