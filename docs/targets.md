# Build and ship targets — CanvasForge

Agents and contributors implement and verify on **Omarchy Arch Linux** first. Other desktop and mobile targets ship later through GitHub Actions. Missing Windows, Mac, or iPhone hardware is not a blocker when the Linux path works.

## Local (Omarchy Linux)

| Target | How |
|--------|-----|
| Daily driver | Installed `canvasforge` (`yay -S canvasforge-beta` or `scripts/install_canvasforge.sh --local`) |
| Checkout run | `python main.py` from a venv (development only) |
| Flatpak | `scripts/build_flatpak.sh` |
| AUR recipe | `packaging/aur/canvasforge-beta/` |

## Planned CI (not required for local PRs yet)

| Target | Role |
|--------|------|
| Linux canary | Lint / import / packaging smoke on Ubuntu or Arch |
| Windows canary | PyInstaller + installer |
| macOS canary | Intel and Apple Silicon `.app` / DMG |
| Android | Flutter companion APK (Phase 2) |
| iOS | TestFlight / signed IPA on macOS runners (Phase 3) |

See [ROADMAP.md](../ROADMAP.md) for phase order.

## Needs Mac?

Yes for signed macOS and iOS ship paths — via CI or a rare interactive Mac, not the daily desktop. The Intel x86_64 DMG already ships on [GitHub Releases](https://github.com/lukejmorrison/canvasforge/releases) (`CanvasForge-*-macos-x64.dmg`). Rebuilding it with [`scripts/build_macos_app.sh`](../scripts/build_macos_app.sh) still has to run on macOS.

## Needs Windows?

Yes for a Windows canary and `.exe` installer — via CI, not a local Windows install requirement.

## Agent and contributor rules

- Do not block a Linux-complete change on Windows or macOS hardware.
- Do not require physical phones that are not attached; use an Android emulator or document the CI path.
- Omarchy-only features (Print Screen hook, Hyprland scratchpad, `hyprpicker`) must stay off or no-ops on other operating systems.
