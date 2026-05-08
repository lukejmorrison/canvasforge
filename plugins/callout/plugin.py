"""Callout plugin for CanvasForge.

Creates a user-editable callout template library in:
~/Templates/CanvasForge

On load, this plugin seeds the folder with SVG files from the app's
`artifacts` directory (without overwriting user changes) and ensures a
README.md is present with source recommendations.
"""

from pathlib import Path
import shutil


README_CONTENT = """# CanvasForge Callout Templates

This folder contains SVG templates used by the CanvasForge Callout plugin.

## How to use
- Add your own `.svg` files here.
- Edit existing files with tools like Inkscape, Illustrator, or any SVG editor.
- Remove any templates you no longer want.

## Free SVG resources
- https://freesvg.org/
- https://openclipart.org/
- https://www.svgrepo.com/
- https://undraw.co/illustrations

## Notes
- CanvasForge only seeds missing default templates and does **not** overwrite your edited files.
- Use the Callout toolbar button (or Plugins > Load Callout Templates) to load templates into the repository panel.
"""


class Plugin:
    """Callout plugin."""

    def __init__(self, api):
        self.api = api
        self._template_dir = Path.home() / "Templates" / "CanvasForge"

    def on_load(self):
        copied_count, total_sources = self._seed_template_folder()
        self.api.show_status_message(
            f"Callout ready: {copied_count} template(s) copied to {self._template_dir}",
            5000,
        )
        if total_sources == 0:
            self.api.show_status_message(
                "Callout: no source SVGs found in artifacts folder", 5000
            )

    def on_unload(self):
        pass

    def load_callout_templates(self):
        self._seed_template_folder()

        main_window = getattr(self.api, "_main_window", None)
        if not main_window or not hasattr(main_window, "add_artifact"):
            self.api.show_status_message("Callout failed: unable to access add_artifact", 5000)
            return

        svg_files = sorted(self._template_dir.glob("*.svg"))
        if not svg_files:
            self.api.show_status_message(
                "Callout: no SVG templates found in ~/Templates/CanvasForge", 5000
            )
            return

        existing_keys = self._existing_callout_keys(main_window)

        loaded = 0
        for index, svg_file in enumerate(svg_files, start=1):
            svg_path_key = str(svg_file.resolve())
            svg_name_key = svg_file.name.lower()
            if svg_path_key in existing_keys or svg_name_key in existing_keys:
                continue

            try:
                main_window.add_artifact(
                    str(svg_file),
                    display_name=f"Callout {index} - {svg_file.name}",
                )
                existing_keys.add(svg_path_key)
                existing_keys.add(svg_name_key)
                loaded += 1
            except Exception:
                continue

        self._renumber_callout_entries(main_window)

        self.api.show_status_message(
            f"Callout loaded {loaded} new template(s) from {self._template_dir}", 5000
        )

    def _existing_callout_keys(self, main_window):
        keys = set()
        artifact_list = getattr(main_window, "artifact_list", None)
        if artifact_list is None:
            return keys

        for row in range(artifact_list.count()):
            list_item = artifact_list.item(row)
            if not list_item:
                continue

            payload = list_item.data(0x0100)  # Qt.ItemDataRole.UserRole
            if isinstance(payload, dict) and payload.get("kind") == "vector":
                source_path = payload.get("source_path")
                if source_path:
                    try:
                        keys.add(str(Path(source_path).resolve()))
                    except Exception:
                        keys.add(str(source_path))

            text = list_item.text() or ""
            if text.lower().startswith("callout "):
                parts = text.split(" - ", 1)
                if len(parts) == 2:
                    keys.add(parts[1].strip().lower())

        return keys

    def _renumber_callout_entries(self, main_window):
        artifact_list = getattr(main_window, "artifact_list", None)
        if artifact_list is None:
            return

        callout_items = []

        for row in range(artifact_list.count()):
            list_item = artifact_list.item(row)
            if not list_item:
                continue

            payload = list_item.data(0x0100)  # Qt.ItemDataRole.UserRole
            source_path = None
            if isinstance(payload, dict) and payload.get("kind") == "vector":
                source_path = payload.get("source_path")

            if not source_path:
                text = list_item.text() or ""
                if text.lower().startswith("callout "):
                    parts = text.split(" - ", 1)
                    if len(parts) == 2 and parts[1].strip():
                        source_path = str(self._template_dir / parts[1].strip())

            if not source_path:
                continue

            try:
                source_resolved = Path(source_path).resolve()
            except Exception:
                source_resolved = Path(source_path)

            if source_resolved.parent != self._template_dir.resolve():
                continue

            callout_items.append((list_item, source_resolved.name))

        for index, (list_item, file_name) in enumerate(callout_items, start=1):
            list_item.setText(f"Callout {index} - {file_name}")

    def _seed_template_folder(self):
        self._template_dir.mkdir(parents=True, exist_ok=True)

        readme_path = self._template_dir / "README.md"
        if not readme_path.exists():
            readme_path.write_text(README_CONTENT, encoding="utf-8")

        source_dir = self._find_artifacts_dir()
        if source_dir is None:
            return 0, 0

        source_svgs = sorted(source_dir.glob("*.svg"))
        copied_count = 0

        for source_svg in source_svgs:
            destination = self._template_dir / source_svg.name
            if destination.exists():
                continue
            try:
                shutil.copy2(source_svg, destination)
                copied_count += 1
            except Exception:
                continue

        return copied_count, len(source_svgs)

    def _find_artifacts_dir(self):
        plugin_path = Path(__file__).resolve()
        repo_root = plugin_path.parents[2]

        candidates = [
            repo_root / "artifacts",
            Path.cwd() / "artifacts",
            plugin_path.parent / "artifacts",
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None
