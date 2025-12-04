# Customizable Toolbar Icons

## Description
Update the toolbar to use icons located in the `assets/toolbar_icons` folder. 
Rename each asset to match the naming of the tool/feature it represents (e.g., `toolbar_icon_pointer_...`).
Include the image resolution in the asset filename (e.g., `toolbar_icon_{usage}_{width}x{height}.png` or `.svg`).

## Goal
This naming convention and structure allow users to easily identify which icon corresponds to which tool. 
It enables users to customize the application by replacing these asset files with their own icons, provided they match the filename pattern.

## Implementation Details
- **Location:** `assets/toolbar_icons/`
- **Naming Convention:** `toolbar_icon_{usage}_{width}x{height}.{ext}`
- **Usage:** The application should load these icons dynamically or explicitly map them to toolbar actions.

## Status
- [x] Implemented in `main.py` (Dark Mode & Icon Refresh update).
- [x] Assets renamed and moved to `assets/toolbar_icons/`.
