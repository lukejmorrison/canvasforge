# CanvasForge Roadmap

CanvasForge is a **native desktop app**. You install it on your machine and it runs locally. It is not a hosted website and not a Progressive Web App.

This page is the public platform roadmap: how CanvasForge reaches Windows, macOS, more Linux downloads, and later a phone companion. Canvas polish and tool work are tracked as [GitHub Issues](https://github.com/lukejmorrison/canvasforge/issues) (index: [TODO.md](TODO.md)). The sequenced native-package / mobile plan from the PWA question is [docs/pwa-platform-plan.md](docs/pwa-platform-plan.md).

One GitHub repository. One version tag. Several **release assets** (installers and bundles) plus a few **packages** (AUR today; winget, Homebrew, Flathub later).

## Now

These already ship:

| Path | What you get |
|------|----------------|
| Omarchy / Arch | AUR [`canvasforge-beta`](https://aur.archlinux.org/packages/canvasforge-beta). Recipe in [`packaging/aur/canvasforge-beta/`](packaging/aur/canvasforge-beta/). |
| Other Linux | Flatpak via [`scripts/build_flatpak.sh`](scripts/build_flatpak.sh), or a local venv via [`scripts/install_canvasforge.sh`](scripts/install_canvasforge.sh). |
| macOS Intel | Ad-hoc-signed `.app` / DMG via [`scripts/build_macos_app.sh`](scripts/build_macos_app.sh) (older Mac Minis, macOS 11+). |
| GitHub Releases | Source tarball from [`scripts/create_beta_release.sh`](scripts/create_beta_release.sh). AUR consumes that tarball. |

Arch remains the first-class daily driver. Omarchy hooks (Print Screen, scratchpad, `hyprpicker`) stay Linux-only.

## Phase 1 — Desktop packages (help wanted)

Goal: a friend on Windows or a Mac downloads an installer from the same GitHub Release that Arch already uses. No website to host. AUR keeps pulling the source tarball.

| Item | Status | Notes |
|------|--------|--------|
| Windows PyInstaller + `.exe` installer | Help wanted | Bundle Python and Qt so users never install a toolchain. |
| macOS Apple Silicon (or universal) DMG | Help wanted | Intel path exists; arm64 / notarization come next. |
| Linux AppImage | Help wanted | One file to download and run on non-Arch distros. |
| Multi-asset GitHub Releases | Planned | One tag uploads Windows, macOS, Linux, and source. |
| CI canaries | Planned | GitHub Actions for Windows and macOS. Local loop stays Arch. See [docs/targets.md](docs/targets.md). |
| OS defaults | Planned | Pictures / Screenshots paths, Ctrl vs Cmd. Omarchy features stay off elsewhere. |

Start a [Q&A discussion](https://github.com/lukejmorrison/canvasforge/discussions/new?category=q-a&title=Packaging%3A%20) titled `Packaging: …` before opening a packaging PR.

How a release should look once this phase lands:

```text
CanvasForge v0.7.0-beta.1
  canvasforge-0.7.0-beta.1.tar.gz          ← AUR already uses this
  CanvasForge-0.7.0-windows-x64-setup.exe
  CanvasForge-0.7.0-macos-arm64.dmg
  CanvasForge-0.7.0-macos-x64.dmg
  CanvasForge-0.7.0-linux-x86_64.AppImage
  com.lukejmorrison.CanvasForge.flatpak
```

## Phase 2 — Mobile sister app

Desktop stays PyQt6. The phone is a companion, not a rewrite of [`main.py`](main.py).

- Desktop **Settings → Mobile → Pair Mobile Device** shows a QR code and a short security code (Buzz-style). The phone stores the link and sends screenshots into the desktop Image Library.
- Sync on LAN or Tailscale only. No hosted backend. How to run: [docs/mobile-pairing.md](docs/mobile-pairing.md).
- Phone companion today is the LAN capture page under `mobile/` (iOS/Android browser). Flutter APK later.
- Android APK first (sideload). Play Store later if it is useful.

## Phase 3 — Stores and iOS

- iOS via TestFlight, built on macOS CI — not a daily Omarchy task. See [docs/targets.md](docs/targets.md).
- Optional store recipes: winget (Windows), Homebrew cask (macOS), Flathub (Linux).
- Optional phone annotation subset (crop / arrow / text), not a clone of the desktop editor.
- Hosted web / PWA stays out of scope unless we later choose it.

## Non-goals

- Do not rewrite the desktop canvas as a PWA, Electron, or Tauri app to “get all five OSes.”
- Do not split CanvasForge into five GitHub repositories. One repo, many release assets.
- Do not require a public host so a phone can send a PNG.
- Do not treat missing Windows or Mac hardware as a blocker when Linux works and CI can cover the rest.

## How to help

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/github-workflow.md](docs/github-workflow.md).
2. Open-ended ideas, questions, and packaging offers go in [Discussions](https://github.com/lukejmorrison/canvasforge/discussions).
3. Accepted product features, fixes, and bugs go in [Issues](https://github.com/lukejmorrison/canvasforge/issues).
4. Implementation is a pull request linked to an Issue (or a short Discussion for tiny docs fixes).
