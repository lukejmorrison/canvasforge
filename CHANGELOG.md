# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- Track new tooling such as stretch handles, fill/eyedropper workflows, and any future export options.

## [2025-12-03] - Alpha foundations

### Added

- Clipboard-driven importing that keeps SVG content as editable vectors and supports pasted raster images or text.
- Selection overlay tooling with context-menu delete/copy, cursor cleanup, and consistent blue handles.
- Shared context menu routing for every canvas object, including overlays, raster items, text, and vectors.
- Flatten Selected / Flatten All actions with Ctrl multi-select support plus automatic artifact creation.
- Auto-save pipeline that hides selection handles, renders to PNG, and writes into a configurable default directory managed by `QSettings`.
- Default assets (toolbar icons + sample callout SVGs) bundled with the application.

### Fixed

- Text editing glitches (delete/backspace affecting items, focus/escape handling) and rotation-center accuracy.
- Startup crash caused by `_ensure_save_directory` referencing UI elements before initialization.
- Overlay artifacts persisting after moves or save operations; selections now clear before rendering.
