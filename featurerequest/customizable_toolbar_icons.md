# Feature Request: Customizable Toolbar Icons

## Document Metadata
| Field | Value |
| --- | --- |
| Doc ID | FR-20251203-ToolbarIcons |
| Version | v1.1 |
| Date | 2025-12-04 17:30 |
| Owner / Author | Luke Morrison |
| Status | Complete |
| Priority | Medium |
| Changelog Tag | [2025-12-04 17:30] Simplified Icon Loading |
| Related Files | main.py; assets/toolbar_icons/; README.md |

## Overview
The toolbar relies on branded icon assets stored under `assets/toolbar_icons/`. Each filename mirrors the tool it represents and includes the rendered resolution, making it straightforward to drop in replacement art. The PyQt6 action setup automatically loads these assets, which keeps the UI in sync with any custom icon packs users provide.

## Goals
- **Consistency**: Align icon names with their tools so maintenance and search stay simple.
- **Customization**: Let artists swap icons by dropping a file with the same name and dimensions.
- **Scalability**: Support PNG or SVG sources without changing application logic.
- **Documentation**: Capture the contract (location, naming, expected sizes) for future contributors.

## Requirements

### Asset Location and Naming
- Store every toolbar asset in `assets/toolbar_icons/`.
- Follow the pattern `toolbar_icon_{usage}_{width}x{height}.{ext}` (example: `toolbar_icon_pointer_95x108.png`).
- Prefer PNG assets; fall back to SVG files if a PNG is not present.

### Loading Behavior
- `main.py` exposes `get_icon()` to search for PNG first, then SVG, before attaching the asset to the QAction.
- Icon definitions live next to the toolbar action map so adding a new tool only requires supplying the correctly named file.
- Logical icon size targets 48x48px, matching the December 4 UI polish update.

### Customization Workflow
- Replacing an icon is as simple as copying a new file with the same name into the folder.
- Mixed PNG + SVG sets are supported with no additional configuration.
- README.md and the installer scripts mention the folder path plus cache-refresh steps.

## Dependencies
- PyQt6 icon loading in `main.py`.
- `assets/toolbar_icons/` packaged via Flatpak manifest and installer scripts.
- Optional documentation callouts inside `README.md`.

## Risks
- **Mismatched Sizes**: Incorrect dimensions lead to blurry or stretched assets; stick to 48x48px outputs.
- **Missing Files**: Deleting a required icon shows the Qt placeholder; add linting later if it becomes an issue.
- **Naming Drift**: When contributors skip the naming convention, runtime lookups fail silently.

## Success Metrics
- Toolbar initializes without warnings on Pop!_OS, Windows, and Flatpak builds.
- Dropping replacement assets reflects in-app on next launch without code edits.
- README traffic or support tickets confirm that users can discover the customization workflow unaided.

## Next Steps
1. Add preview thumbnails of the default set to README or the Image Library doc.
2. Provide a validation script to ensure every QAction has a corresponding icon file.
3. Gather community icon packs for optional download bundles.

## Timeline
| Changelog Timestamp | Feature Doc Version | Summary of Change | Link to Evidence |
| --- | --- | --- | --- |
| [2025-12-04 17:00] | v1.0 | Dark Mode & Icon Refresh introduced the new toolbar asset pipeline. | CHANGELOG.md |
| [2025-12-04 17:30] | v1.1 | Simplified icon loading plus naming guidance for customization. | CHANGELOG.md |
