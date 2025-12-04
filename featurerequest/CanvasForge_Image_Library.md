# Feature Request: CanvasForge Image Library

## Document Metadata
- **Title**: CanvasForge Image Library Integration
- **Version**: 1.0
- **Date**: December 04, 2025
- **Author**: Grok (xAI Assistant)
- **Status**: Draft for Review
- **Priority**: Medium (Enhances discoverability and workflow efficiency without altering core editing logic)
- **Estimated Effort**: 4-6 hours for implementation; 1-2 days including testing and edge cases
- **Related Artifacts**: 
  - CHANGELOG.md (Reference: [2025-12-04 11:34] Image Library Integration)
  - TODO.md (Add under "Medium Priority" as detailed in attachment)
  - Screenshot: Provided UI mockup showing sidebar layout with thumbnails, sort/zoom controls, and properties panel

## Overview
The CanvasForge Image Library introduces a dedicated panel for browsing and managing image assets sourced from the user's OS-specific Screenshots folder (e.g., `~/Pictures/Screenshots`). This feature provides a visual repository of saved or captured files, enabling seamless drag-and-drop integration with the canvas, thumbnail previews, sorting, search, and zoom controls. It positions the library as a left sidebar (vertical strip) or optional bottom panel, complementing the existing Repository and Layers panels without disrupting the 3:1 canvas dominance.

This enhancement addresses a key usability gap: Users currently lack an at-a-glance view of external assets, requiring manual file navigation. By auto-monitoring the Screenshots directory, the library fosters a closed-loop workflow—capture externally, browse/import effortlessly, edit on-canvas, and export back to the folder.

## Goals and Objectives
### Primary Goals
- **Improve Asset Discoverability**: Allow users to visualize and access recent screenshots/captures directly within the app, reducing context-switching to file explorers.
- **Streamline Import/Export**: Enable one-click loading of library items to the canvas and automatic syncing of exports to the Screenshots folder.
- **Enhance Workflow Efficiency**: Support sorting (by date modified/created, name, size), search, and zoom for quick scanning of large libraries.

### Secondary Objectives
- **Modular Design**: Ensure the feature is self-contained (e.g., via a reusable QWidget) for future refactoring to low-level languages (e.g., Rust/C++), aligning with Graphite.rs/Inkscape integration goals.
- **Cross-Platform Compatibility**: Dynamically detect OS paths for Screenshots folder; fallback to `~/Pictures` if unavailable.
- **Performance Optimization**: Use efficient Qt models to handle 100+ files without lag; implement lazy loading for thumbnails.

### Non-Goals
- Full file management (e.g., rename/delete in-app; defer to OS tools).
- Advanced editing in the library view (e.g., cropping; use canvas for that).
- Non-image formats (focus on PNG/JPG/SVG/GIF; extend via filters if needed).

## User Personas and Stories
### Target Personas
- **Primary: Creative Professional (e.g., Designer)**: Uses CanvasForge for rapid prototyping; needs quick access to screenshots for reference or cutouts.
- **Secondary: Developer/Tester**: Captures app states frequently; values auto-refresh and drag-to-canvas for iterative workflows.

### User Stories
- As a designer, I want to see thumbnails of my recent screenshots in a sidebar so I can drag relevant ones to the canvas without opening Finder/Explorer.
- As a user, I want to sort/search the library by date/name/size so I can locate specific captures quickly.
- As a tester, I want the library to auto-refresh when new screenshots are added so I don't need to restart the app.
- As a creative, I want a zoom slider for thumbnails so I can preview details without committing to full import.

## Functional Requirements
### Core Components
1. **Library Panel Widget**:
   - Vertical sidebar (left edge, ~200px wide; resizable via QSplitter) or horizontal bottom bar (alternative).
   - Top section: Search bar (QLineEdit) and folder navigation (QListView for subfolders like "All Files", "Images").
   - Middle section: Thumbnail grid (QGridView in IconMode; auto-adjust rows/columns).
   - Bottom section: Sort dropdown (QComboBox: Date Modified/Created, Name, Size), zoom slider (QSlider: 50-200%), and Export button (ties to flatten).

2. **Data Binding**:
   - Use QFileSystemModel filtered to image extensions (*.png, *.jpg, *.jpeg, *.gif, *.svg).
   - Root path: Dynamically resolve OS Screenshots folder (macOS/Linux: `~/Pictures/Screenshots`; Windows: `%USERPROFILE%\Pictures\Screenshots`).
   - Proxy model (QSortFilterProxyModel) for search/sorting; custom roles for dates/sizes.

3. **Interactions**:
   - **Drag-and-Drop**: Thumbnails draggable to canvas (mimeData with file paths; extend dropEvent to load via add_artifact).
   - **Double-Click**: Loads selected image to canvas as a new layer.
   - **Selection**: Updates a right-docked Properties panel with metadata (name, size, date, preview).
   - **Auto-Refresh**: QFileSystemWatcher monitors root path; refresh model on changes.
   - **Export**: Button flattens current canvas and saves to Screenshots folder with timestamp (e.g., "canvas_export_20251204_1134.png").

### UI/UX Guidelines (Based on Screenshot)
- **Layout Alignment**: Left sidebar with dark theme (match app: #1e1e1e background, #ffffff text).
- **Thumbnails**: 100px base size (scalable); icons via QFileIconProvider; grid spacing 10px.
- **Controls**: Compact horizontal bar at bottom; sort defaults to "Date Created" descending; zoom at 100%.
- **Properties Panel**: Docked right (QDockWidget); shows file info in a form layout (QLabel pairs).
- **Accessibility**: Keyboard navigation (arrow keys for thumbnails); tooltips on hover.

## Non-Functional Requirements
- **Performance**: Handle 500+ files with <500ms load time; lazy thumbnail generation.
- **Compatibility**: PyQt6 6.5+; cross-platform (test on Linux/Windows/macOS).
- **Security**: Read-only access to Screenshots folder; no execution of files.
- **Localization**: English default; extensible via Qt translations.
- **Error Handling**: Graceful fallbacks (e.g., create folder if missing); log to output.log.

## Technical Implementation Notes
- **Dependencies**: No new pip installs (leverage Qt natives: QFileSystemModel, QSortFilterProxyModel, QFileSystemWatcher).
- **Integration Points**:
  - MainWindow.__init__: Add splitter and call create_library_panel().
  - CanvasView.dropEvent: Extend for url mimeData.
  - Flatten_scene: Optional path parameter for library exports.
- **Extensibility**: Abstract panel as a mixin for future ports (e.g., Rust: qt-rs bindings).
- **Testing**: Unit tests for path resolution/sort; manual: Add screenshot, verify drag/refresh.

## Dependencies and Risks
- **Dependencies**: Existing add_artifact/flatten_scene methods; QFileSystemModel (Qt standard).
- **Risks**:
  - Path Variability: Mitigate with os.path.exists checks and user config fallback.
  - Performance on Large Folders: Risk of lag; mitigate with pagination (QPageSize).
  - Theme Mismatch: Ensure stylesheet consistency.

## Success Metrics
- **Quantitative**: 80% reduction in import time (user survey); library loads <2s for 100 files.
- **Qualitative**: Positive feedback on workflow (e.g., "Easier to reference screenshots"); no crashes in 10-session tests.
- **Adoption**: 50% of exports route through library in beta usage.

## Next Steps
1. **Review and Prioritize**: Add to TODO.md under "Medium Priority" (as scripted below).
2. **Implementation**: Assign to Coding Agent; target merge by Dec 05, 2025.
3. **Testing/QA**: Validate on Pop!_OS (per logs); edge cases in screenshots/. 

---

### Script to Update TODO.md
To automate addition to your TODO.md, run this in your project root (or via Coding Agent):

```bash
# Append to TODO.md under Medium Priority
echo "
- **Lightweight Demo Recording Tool:** [Existing entry...]

- **CanvasForge Image Library:** Integrate left sidebar panel for Screenshots folder browsing with thumbnails, search/sort/zoom, drag-to-canvas, and properties dock (PRD: FeatureRequest_CF_ImageLibraryPRD.md)." >> TODO.md
```

This PRD provides a comprehensive blueprint for your Coding Agent to execute the feature while aligning with CanvasForge's modular ethos. Should clarifications be required, please advise.
