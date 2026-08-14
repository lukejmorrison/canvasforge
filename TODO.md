# TODO

**Source of truth is [GitHub Issues](https://github.com/lukejmorrison/canvasforge/issues).** This file is an index. Do not add new product work here without opening an Issue first. Historical rows below stay so old links still make sense.

Knock-off order: **0.6.0-beta.12** Image Library → **0.6.0-beta.13** (T1, maybe T2) → packaging in parallel → PWA/mobile as its own later track. See [docs/github-workflow.md](docs/github-workflow.md) and [docs/pwa-platform-plan.md](docs/pwa-platform-plan.md).

## 0.6.0-beta.11 (shipped)

| ID | Issue | Notes |
|----|--------|--------|
| U1 | [#8](https://github.com/lukejmorrison/canvasforge/issues/8) Text colour and combined B/I/U | Uncommitted `main.py` at plan time |
| U2 | [#9](https://github.com/lukejmorrison/canvasforge/issues/9) Text box Pointer/Move resize | Implemented on HEAD; ships in .11 |
| U3 | [#10](https://github.com/lukejmorrison/canvasforge/issues/10) Eyedropper hang / tiled checkerboard | Implemented on HEAD; ships in .11 |
| U4 | [#11](https://github.com/lukejmorrison/canvasforge/issues/11) AUR installer, README, roadmap | Implemented on HEAD; ships in .11 |

## 0.6.0-beta.12 (shipped)

| ID | Issue | Notes |
|----|--------|--------|
| IL | [#39](https://github.com/lukejmorrison/canvasforge/issues/39) Image Library large thumbnails, columns, copy path | Ships in .12 |

## 0.6.0-beta.13

| ID | Issue |
|----|--------|
| T1 | [#12](https://github.com/lukejmorrison/canvasforge/issues/12) Shape stretching (edge handles non-uniform) |
| T2 | [#13](https://github.com/lukejmorrison/canvasforge/issues/13) Fill polish (shapes / cutouts) — confirm scope first |

## Later canvas

| ID | Issue | Was |
|----|--------|-----|
| T3 | [#14](https://github.com/lukejmorrison/canvasforge/issues/14) | Image Library Flatpak notes, thumbnail stress, screenshots |
| T4 | [#15](https://github.com/lukejmorrison/canvasforge/issues/15) | Theme toggle Light / Dark |
| T5 | [#16](https://github.com/lukejmorrison/canvasforge/issues/16) | Icon customisation UI |
| T6 | [#17](https://github.com/lukejmorrison/canvasforge/issues/17) | Persist colour / callout / text-style palettes (after U1) |
| T7 | [#18](https://github.com/lukejmorrison/canvasforge/issues/18) | Better export: filename, recents, JPEG/SVG |
| T8 | [#19](https://github.com/lukejmorrison/canvasforge/issues/19) | Undo/redo granularity |
| T9 | [#20](https://github.com/lukejmorrison/canvasforge/issues/20) | SVG node editing, morphing, template palette |
| T10 | [#21](https://github.com/lukejmorrison/canvasforge/issues/21) | Mojo compilation experiment (research, not a beta) |
| FR | [#22](https://github.com/lukejmorrison/canvasforge/issues/22) | Plugin in-app editor / live reload leftover |
| FR | [#23](https://github.com/lukejmorrison/canvasforge/issues/23) | Toolbar icon validation script |

## Packaging (parallel; does not block Arch)

From ROADMAP Phase 1 and the [PWA question](https://github.com/lukejmorrison/canvasforge/issues/38) (native installers, not a web app):

| ID | Issue |
|----|--------|
| R1 | [#24](https://github.com/lukejmorrison/canvasforge/issues/24) Windows `.exe` installer |
| R2 | [#25](https://github.com/lukejmorrison/canvasforge/issues/25) macOS Apple Silicon DMG |
| R3 | [#26](https://github.com/lukejmorrison/canvasforge/issues/26) Linux AppImage |
| R4 | [#27](https://github.com/lukejmorrison/canvasforge/issues/27) Multi-asset GitHub Releases + CI canaries |
| — | [#28](https://github.com/lukejmorrison/canvasforge/issues/28) OS-native defaults (paths, Ctrl vs Cmd, Omarchy hooks off elsewhere) |

## PWA / platform (later track)

Not a hosted Progressive Web App. Sequence in [docs/pwa-platform-plan.md](docs/pwa-platform-plan.md).

| Issue | Item |
|--------|------|
| [#29](https://github.com/lukejmorrison/canvasforge/issues/29) | Flutter companion under `mobile/` |
| [#30](https://github.com/lukejmorrison/canvasforge/issues/30) | Desktop Link phone QR pairing |
| [#31](https://github.com/lukejmorrison/canvasforge/issues/31) | LAN / Tailscale capture sync |
| [#32](https://github.com/lukejmorrison/canvasforge/issues/32) | Android APK |
| [#33](https://github.com/lukejmorrison/canvasforge/issues/33) | iOS TestFlight (macOS CI) |
| [#34](https://github.com/lukejmorrison/canvasforge/issues/34) | winget |
| [#35](https://github.com/lukejmorrison/canvasforge/issues/35) | Homebrew cask |
| [#36](https://github.com/lukejmorrison/canvasforge/issues/36) | Flathub listing |
| [#37](https://github.com/lukejmorrison/canvasforge/issues/37) | Optional phone annotation subset |
| [#38](https://github.com/lukejmorrison/canvasforge/issues/38) | Non-goal: do not rewrite as a hosted PWA (closed, not planned) |

## Historical wording (pre-Issues)

These sentences are the old TODO.md body, kept for search. Status now lives on the Issues above.

- **Shape stretching:** Add edge handles that scale items non-uniformly (corners remain uniform) without degrading raster quality; selection overlay math must update bounding boxes accordingly. → [#12](https://github.com/lukejmorrison/canvasforge/issues/12)
- **Fill tool + eyedropper:** Introduce a fill mode with a zoomed preview eyedropper, allowing users to sample on-canvas colors and fill selection cutouts or shapes. (Core fill/eyedropper + performance path landed; polish remains.) → [#13](https://github.com/lukejmorrison/canvasforge/issues/13)
- **CanvasForge Image Library:** Track follow-up tasks for the new `image_library_panel.py` widget—add Flatpak sandbox notes, automate thumbnail stress tests, and capture release screenshots once QA completes. → [#14](https://github.com/lukejmorrison/canvasforge/issues/14)
- **Theme toggle:** Add a settings option to switch between Light and Dark modes (currently defaults to Dark). → [#15](https://github.com/lukejmorrison/canvasforge/issues/15)
- **Icon Customization UI:** Interface to easily swap toolbar icons without manually renaming files. → [#16](https://github.com/lukejmorrison/canvasforge/issues/16)
- **Color/asset palettes:** Persist frequently used colors, callouts, and text styles for faster reuse across sessions. → [#17](https://github.com/lukejmorrison/canvasforge/issues/17)
- **Better export management:** Support manual filename entry, recent-save history, and optional JPEG/SVG exports. → [#18](https://github.com/lukejmorrison/canvasforge/issues/18)
- **Undo/redo polish:** Expand undo granularity for selection overlays, flatten operations, and save-directory changes. → [#19](https://github.com/lukejmorrison/canvasforge/issues/19)
- **Packaging:** Provide a platform-specific bundle (AppImage/Windows installer) so users can run CanvasForge without a dev environment. macOS Intel DMG ships on GitHub Releases (`CanvasForge-*-macos-x64.dmg`). → [#24](https://github.com/lukejmorrison/canvasforge/issues/24) [#25](https://github.com/lukejmorrison/canvasforge/issues/25) [#26](https://github.com/lukejmorrison/canvasforge/issues/26)
- **SVG editing & morphing** / **SVG template library:** → [#20](https://github.com/lukejmorrison/canvasforge/issues/20)
- **Mojo compilation experiment:** → [#21](https://github.com/lukejmorrison/canvasforge/issues/21)
