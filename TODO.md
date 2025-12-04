# TODO

## High Priority

- **Shape stretching:** Add edge handles that scale items non-uniformly (corners remain uniform) without degrading raster quality; selection overlay math must update bounding boxes accordingly.
- **Fill tool + eyedropper:** Introduce a fill mode with a zoomed preview eyedropper, allowing users to sample on-canvas colors and fill selection cutouts or shapes.

## Planned Enhancements

- **Color/asset palettes:** Persist frequently used colors, callouts, and text styles for faster reuse across sessions.
- **Better export management:** Support manual filename entry, recent-save history, and optional JPEG/SVG exports.
- **Undo/redo polish:** Expand undo granularity for selection overlays, flatten operations, and save-directory changes.
- **Packaging:** Provide a platform-specific bundle (AppImage/Windows installer) so users can run CanvasForge without a dev environment.
- **SVG editing & morphing:** Provide on-canvas vector node editing, path combination, and shape-morphing tools so pasted SVGs stay fully editable.
- **SVG template library:** Let users pin favorite SVG snippets/templates to a palette for single-click insertion.
- **Mojo compilation experiment:** Investigate compiling core routines with Modular's Mojo to evaluate performance gains.
