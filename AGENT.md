---
name: CanvasForge Agent Instructions
description: Guidelines for AI agents working on this codebase.
applyTo: "**/*"
---

# 🛑 STOP & READ: The Philosophy
**"Boundaries? Only the ones that matter."**

This is a **Monolith**. We nurture it. We do not dismember it into micro-packages or over-abstracted layers unless absolutely necessary.
-   **Speed is King**: Code for the *now*. Optimise for velocity and responsiveness.
-   **Coherence over Decoupling**: It is better to have one large, well-organized file where you can see the whole logic flow than 20 tiny files jumping around. `main.py` is huge. That is fine. It is a "War Story", not a crime.
-   **Operational Simplicity**: Boring deploys. Simple scripts.

# Overview
CanvasForge is a **PyQt6** desktop application for remixing screenshots and creating documentation visuals.
-   **Core**: `main.py` (The Monolith). Contains the Scene, View, and Item classes.
-   **Extensions**: `image_library_panel.py` (Sidebar), `undo_manager.py`, `plugin_manager.py`.
-   **Assets**: `assets/` (Icons), `artifacts/` (Vector capabilities).

# Conventions & Patterns
-   **Style**:
    -   **Qt Overrides**: Use `camelCase` (e.g., `mousePressEvent`, `contextMenuEvent`) to match PyQt signatures.
    -   **Internal Logic**: Prefer `snake_case` (e.g., `handle_resize_press`), but follow local consistency if the class uses camelCase.
    -   **Imports**: Keep them clean. Group PyQt imports.
-   **Architecture**:
    -   **Items**: Inherit from `QGraphicsItem` (or subclasses like `QGraphicsRectItem`).
    -   **Events**: Use standard Qt event bubbling.
    -   **State**: Local state in Items or the main Window. No complex external state stores.

# Workflows

## 1. Development
-   **Run**: `python main.py`
-   **Install Dependencies**: `pip install -r requirements.txt`
-   **Environment**: `.venv` is standard.

## 2. Documentation Rules
We treat documentation as a first-class citizen.
-   **`CHANGELOG.md`**: **MUST** be updated for *every* user-facing change.
    -   Format: `[YYYY-MM-DD HH:MM] Summary`.
    -   If implementing a Feature Request, link to it.
-   **`README.md`**: Update ONLY if:
    -   New key features are added.
    -   Installation instructions change.
    -   Project structure changes significantly.
-   **`TODO.md`**:
    -   **Add**: New ideas or future technical debt.
    -   **Remove/Check**: When completing a task.
-   **Feature Requests**: See `featurerequest/AGENT.md` for the strict lifecycle.

## 3. Deployment / Packaging
-   **Flatpak**: `bash scripts/build_flatpak.sh`
-   **Local**: `bash scripts/install_canvasforge.sh`

# Integration Points
-   **Plugins**: `/plugins/` via `plugin_manager.py`.
-   **Image Library**: `image_library_panel.py` watches `~/Pictures/Screenshots`.

# Examples
-   **Adding a Tool**: Add to `ToolType` enum in `main.py`, add button in `_setup_toolbar`, implement logic in `CanvasView.mouse*Event`.
-   **Adding a Hotkey**: Define in `_setup_menus` or `keyPressEvent`.

If in doubt: **Keep it simple, keep it fast, keep it in the monolith.**
