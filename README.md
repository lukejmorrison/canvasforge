# CanvasForge

CanvasForge is a PyQt6-powered canvas utility focused on quickly remixing screenshots, UI snippets, and vector assets. It combines clipboard-aware importing, precise selection overlays, and flatten/save workflows so you can compose documentation-ready visuals without leaving the desktop.

## Highlights

- **Flexible importing:** Paste raster images, SVG markup, file paths, or plain text directly from the clipboard; SVGs stay editable as vector items.
- **Selection overlays & cutouts:** Draw rectangular cutouts on raster layers, drag them elsewhere, duplicate them, or delete them, all while keeping handles and overlays responsive.
- **Consistent context menus:** Every canvas item (text, vector, raster, overlays) forwards right-clicks to a unified menu for copy/delete and other actions.
- **Text tooling:** Double-click to edit text items with proper cursor management; escape exits edit mode cleanly.
- **Flattening & saving:** Convert selected layers or the entire scene into new raster artifacts, then auto-save to a Pictures/CanvasForge folder (configurable in settings). Blue control handles are hidden before rendering so exports stay clean.
- **Layer + artifact lists:** Side panels keep imported resources and active scene layers in sync, supporting Ctrl/Cmd multi-select for flattening or deletion.
- **Dark Mode & Custom Icons:** The application features a sleek dark mode and uses external icon files in `assets/toolbar_icons/`. Users can customize the toolbar by replacing these images. The system will load `icon_name.png` first; if missing, it falls back to `icon_name.svg`. Filenames are stripped of resolution info (e.g. `toolbar_icon_pointer`).
- **Desktop-ready branding:** A dedicated app icon in `assets/app_icons/canvasForge_app_icon.png` keeps the Pop!_OS launcher and task switcher on-brand. The installer script copies this icon system-wide so CanvasForge shows up under Audio & Video.

## Getting Started

1. **Clone the repo**

   ```bash
   git clone https://github.com/lukejmorrison/canvasforge.git
   cd canvasforge
   ```

2. **Create a virtual environment** (optional but recommended)

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run CanvasForge**

   ```bash
   python main.py
   ```

### Pop!_OS desktop installs

#### Flatpak (recommended)

```bash
bash scripts/build_flatpak.sh
flatpak run com.lukejmorrison.CanvasForge
```

The script wraps `flatpak-builder`, automatically installs the KDE 6.8 runtime/SDK the first time, downloads the required PyPI wheels on the host, and then performs the build fully offline inside the sandbox. Subsequent runs rebuild and update in place.

#### Local virtual environment

```bash
bash scripts/install_canvasforge.sh
```

This legacy helper installs into `~/.local/share/canvasforge`, drops a `canvasforge` launcher in `~/.local/bin`, copies the branded icon, and registers a `.desktop` entry in the Audio & Video category.

## Usage Notes

- Use the toolbar or keyboard shortcuts (`S` for select) to switch tools. The selection marquee collaborates with the layer list so you can target multiple items quickly.
- Paste content from the clipboard (Ctrl/Cmd+V). SVG markup from the clipboard remains editable; bitmap content becomes raster layers.
- Right-click anywhere on an item to open the shared context menu for copy/delete and future actions.
- Use *Flatten Selected* or *Flatten All* from the toolbar/menu to rasterize layers. The operations create a new raster artifact without destroying originals until you remove them.
- Saving (`Ctrl/Cmd+S`) renders the scene without showing selection handles and writes a PNG to your default Pictures/CanvasForge directory. Change this directory via **Edit → Settings → Save Directory**; CanvasForge persists the choice using `QSettings`.

## Project Layout

- `main.py` – Entire PyQt6 application, including the custom `CanvasView`, item classes, selection overlay, flatten/save helpers, and menu/toolbar wiring.
- `assets/toolbar_icons/` – Toolbar icon PNGs.
- `artifacts/` – Sample vector callouts bundled for quick use.
- `requirements.txt` – Runtime dependencies (currently only PyQt6).

## Contributing

Issues and pull requests are welcome. Please keep screenshots, `pasted_logs/`, and `wizwam-code-review/` folders out of commits as they are environment-specific.
