# CanvasForge

[![Release](https://img.shields.io/github/v/release/lukejmorrison/canvasforge?include_prereleases&sort=semver)](https://github.com/lukejmorrison/canvasforge/releases)
[![AUR](https://img.shields.io/aur/version/canvasforge-beta)](https://aur.archlinux.org/packages/canvasforge-beta)
[![License](https://img.shields.io/github/license/lukejmorrison/canvasforge)](LICENSE)

**The polished screenshot annotation canvas for Omarchy Arch Linux + Hyprland.**

CanvasForge is a fast PyQt6 canvas made for turning raw screenshots into beautiful, documentation-ready visuals. It shines brightest on **Omarchy**, where it integrates deeply as a first-class screenshot editor, scratchpad citizen, and Grok TUI companion.

## 🚀 Omarchy Integration (First-Class Citizen)

CanvasForge is designed from the ground up to feel native on Omarchy Arch Linux:

- **Print Screen → CanvasForge** — Set `OMARCHY_SCREENSHOT_EDITOR=canvasforge` and every screenshot opens directly in CanvasForge with the correct monitor resolution.
- **Super + S Scratchpad** — Enable "Launch in Omarchy Scratchpad" in Preferences. CanvasForge lives in your scratchpad and appears on whatever monitor your mouse is on.
- **Monitor-Accurate Canvas** — Automatically creates a canvas that matches your physical monitor resolution (correctly handles fractional scaling like `scale 1.2`).
- **Grok TUI Optimized** — One-click **Send to Agent → Clipboard (base64 JPEG)** puts clean, properly-sized images on the clipboard that paste perfectly into Grok.
- **HiDPI & Fractional Scaling** — Proper support for modern high-DPI and scaled displays common in Omarchy setups.

See the [full Omarchy setup guide](#omarchy-setup) below.

## ✨ Features

- **Screenshot Editor for Omarchy** — Deep integration as a Print Screen replacement with monitor-accurate canvases and scratchpad support.
- **Powerful Annotation Tools** — Arrows, callouts, steps, blur, highlight, borders, text, and vector shapes with live previews.
- **Smart Selection & Cutouts** — Draw regions on images, move them around, or extract them cleanly.
- **Colour Picker + Fill** — Pick colours from the canvas or Omarchy `hyprpicker`, then bucket-fill connected raster-image regions with undo and transparent fill support.
- **Layer & Repository System** — Full layer management + a persistent image library that watches your Screenshots folder.
- **One-Click Agent Handoff** — Send to Claude, Codex, OpenClaw, Wizwam, or directly to Grok TUI via clean clipboard JPEG.
- **Flawless Export** — Flatten selected or all layers with hidden handles for pixel-perfect output.
- **Beautiful Theming** — Multiple icon themes, dark mode, and fully customizable toolbar.
- **HiDPI & Fractional Scaling** — Excellent support for modern displays with non-integer scaling (common in Omarchy).

## Getting Started

### Omarchy / Arch Linux (Recommended)

```bash
yay -S canvasforge-beta
```

Then just press **Print Screen**. CanvasForge will handle the rest.

See the [full Omarchy setup](#omarchy-setup) above for scratchpad + multi-monitor configuration.

### Other Systems

**Flatpak**
```bash
bash scripts/build_flatpak.sh
flatpak run com.lukejmorrison.CanvasForge
```

**Local Install (any Linux)**
```bash
bash scripts/install_canvasforge.sh --local
canvasforge
```

**From Source**
```bash
git clone https://github.com/lukejmorrison/canvasforge.git
cd canvasforge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Other Distributions

**Flatpak**
```bash
bash scripts/build_flatpak.sh
flatpak run com.lukejmorrison.CanvasForge
```

**Local Install**
```bash
bash scripts/install_canvasforge.sh --local
```

The installer is robust and works well on Pop!_OS, Fedora, and other distributions.

```bash
# Standard install/update from GitHub
bash scripts/install_canvasforge.sh

# Full reinstall (recommended when recovering from broken .venv state)
bash scripts/install_canvasforge.sh --clean

# Install from your current local checkout
bash scripts/install_canvasforge.sh --local

# Full reinstall from your current local checkout
bash scripts/install_canvasforge.sh --local --clean

# Show installer options
bash scripts/install_canvasforge.sh --help
```

The installer now auto-heals unhealthy virtual environments and retries Python dependency installs, which makes reinstalls more reliable on Arch/Omarchy systems.

## Usage Notes

- Use the toolbar or keyboard shortcuts (`S` for select) to switch tools. Select supports click, Ctrl/Cmd-click toggles, Ctrl/Cmd+A select-all, and marquee selection that stays in sync with the layer list.
- Use **Eyedropper** (`I`) to choose the active fill colour with the canvas picker preview, then **Fill** (`F`) to bucket-fill a connected area inside a raster image layer. Hold Alt while clicking Eyedropper to use Omarchy's `hyprpicker` screen picker instead.
- Use the right-side **Details - [Tool] Tool - Colour Selector Pallet** panel above Repository to pick Fill colours from swatches, choose a custom alpha-aware colour, or select Transparent for cutaway fills.
- Use the **View** menu for zoom in/out, zoom to fit, actual size, shrink-to-fit, pixel grid, background color, sidebar visibility, and quick focus actions for Details, Library, and Recent Captures.
- Enable **Edit → Preferences → Canvas → Zoom with Scroll Wheel** for Photoshop-style wheel zoom at the cursor. Turn it off to use Photoshop's stock wheel behavior: wheel pans vertically, Alt+wheel zooms. The same Canvas preferences also expose Animated Zoom and sensitivity controls for smoother wheel flicks.
- Alt-drag canvas edges or corners to snap the workspace to common X.com, social, video, web, and connected-monitor sizes. The resize badge names the snapped preset, and the tag below the canvas shows resolution, aspect ratio, PNG type, and transparency status.
- The **Image Library** panel on the left auto-scans `~/Pictures/Screenshots` (with fallbacks) for PNG/JPG/WebP/GIF/SVG files. Double-click or drag thumbnails onto the canvas, use the zoom slider for larger previews, and tap *Export Canvas* to flatten the scene back into the monitored folder.
- Switch the watched folder any time via **Edit → Change Image Library Folder...**. CanvasForge stores the selection in `QSettings` so it persists between launches, and the combo box in the panel remembers common screenshot directories.
- Paste content from the clipboard (Ctrl/Cmd+V). SVG markup from the clipboard remains editable; bitmap content becomes raster layers.
- Right-click anywhere on an item to open the shared context menu for copy/delete and future actions.
- Drag resize handles with standard modifiers: no key keeps proportions, Shift/Ctrl allows independent width/height, Alt resizes from center, Ctrl+Shift skews where supported, and Ctrl+Alt+Shift applies perspective-style transforms where supported.
- Use *Flatten Selected* or *Flatten All* from the toolbar/menu to rasterize layers. The operations create a new raster artifact without destroying originals until you remove them.
- Saving (`Ctrl/Cmd+S`) renders the scene without showing selection handles and writes a PNG to your default Pictures/CanvasForge directory. Change this directory via **Edit → Settings → Save Directory**; CanvasForge persists the choice using `QSettings`.
- Use *Save Selected* (`Ctrl+Alt+S`) to write just the selected layers. Use *Send to Agent* (`Ctrl+Shift+A`) to create a temp bundle with `selected.png` and `annotations.json`; configure the command, VS Code Codex folder handoff, HTTP endpoint, Clipboard image-path handoff, or Clipboard base64 JPEG handoff under **Edit → Preferences → Agent**. The base64 JPEG handoff targets Grok-friendly defaults: longest side 1440px, quality 88.

## Omarchy Setup (Recommended)

CanvasForge is built to feel at home on **Omarchy Arch Linux**.

### 1. Set as Default Screenshot Editor

```bash
# One-time
OMARCHY_SCREENSHOT_EDITOR=canvasforge omarchy capture screenshot

# Permanent (recommended)
echo 'OMARCHY_SCREENSHOT_EDITOR=canvasforge' > ~/.config/environment.d/omarchy-screenshot.conf
```

Or use the dedicated flag for scripts and agents:

```bash
canvasforge --screenshot-editor /path/to/screenshot.png
```

### 2. Enable Scratchpad Mode (Power User Favorite)

1. In CanvasForge go to **Preferences → Canvas → Screenshot Editor**
2. Check **"Launch screenshot editor in Omarchy Scratchpad"**
3. In **Window → Startup Behavior**, select **"Open on Screen with Mouse"**

Add these lines to your Hyprland config:

```hyprland
# Toggle CanvasForge
bind = SUPER, S, togglespecialworkspace, canvasforge

# Rules
windowrulev2 = workspace special:canvasforge, class:^(canvasforge|CanvasForge)$
windowrulev2 = float, class:^(canvasforge|CanvasForge)$
windowrulev2 = size 80% 80%, class:^(canvasforge|CanvasForge)$
```

Now **Print Screen** sends the capture to your scratchpad. Press **Super + S** and CanvasForge appears on whatever monitor your mouse is on, with a perfectly sized canvas.

### 3. Monitor Resolution & Scaling

CanvasForge automatically uses your monitor’s **physical** resolution (correctly handles `scale 1.2`, `1.6`, etc.). You can also force a specific monitor in Preferences.

See the full list of options in **Preferences → Canvas → Screenshot Editor**.

**Advanced / AI Agent Usage**

You can force screenshot editor mode with a dedicated flag:

```bash
canvasforge --screenshot-editor /path/to/screenshot.png
```

This is useful for scripts, Omarchy hooks, or AI agents.

In **Preferences → Canvas → Screenshot Editor**, you can also enable:
- "Launch screenshot editor in Omarchy Scratchpad" (hides the window until you press your toggle key)
- Choose which monitor's resolution to use for the canvas

This makes `Super + S` (scratchpad toggle) bring up CanvasForge on the monitor your mouse is currently on.

## Project Layout

- `main.py` – Entire PyQt6 application, including the custom `CanvasView`, item classes, selection overlay, flatten/save helpers, and menu/toolbar wiring.
- `assets/toolbar_icons/` – Toolbar icon PNGs.
- `artifacts/` – Sample vector callouts bundled for quick use.
- `packaging/aur/canvasforge-beta/` – AUR beta package recipe and release checklist.
- `requirements.txt` – Runtime dependencies (currently only PyQt6).

## Contributing

Issues and pull requests are welcome. Please keep screenshots, `pasted_logs/`, and `wizwam-code-review/` folders out of commits as they are environment-specific.
