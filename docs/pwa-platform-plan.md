# Native packages and mobile companion (from the PWA question)

On 13 Aug 2026 the question was: make CanvasForge a “self-hosted progressive web app” for Mac, Linux, Windows, and later Android/iOS, without hosting it on the web.

**Answer already in [ROADMAP.md](../ROADMAP.md):** it is a native desktop app. Do not rewrite it as a PWA ([#38](https://github.com/lukejmorrison/canvasforge/issues/38), closed as not planned). What was wanted is **OS-native installers** plus a later **phone companion**.

Knock-off order vs canvas work:

1. **Now — 0.6.0-beta.11** canvas ([#8](https://github.com/lukejmorrison/canvasforge/issues/8)–[#11](https://github.com/lukejmorrison/canvasforge/issues/11)). Do not start this track instead of U1.
2. **Next canvas — 0.6.0-beta.12** T1/T2 ([#12](https://github.com/lukejmorrison/canvasforge/issues/12), [#13](https://github.com/lukejmorrison/canvasforge/issues/13)).
3. **Packaging in parallel** (does not block Arch AUR betas).
4. **This track last** unless an item is clearly “installability of the desktop app” (still plan-only until Phase 1 packaging Issues are in progress).

## Phase 1 — desktop packages (milestone `packaging`)

| Order | Issue | Depends on | Test / deploy |
|-------|--------|------------|----------------|
| 1 | [#28](https://github.com/lukejmorrison/canvasforge/issues/28) OS defaults | — | Linux defaults must not regress; other OS via CI |
| 2 | [#24](https://github.com/lukejmorrison/canvasforge/issues/24) Windows `.exe` | Discussion `Packaging: …` | Windows canary |
| 3 | [#25](https://github.com/lukejmorrison/canvasforge/issues/25) macOS arm64 DMG | Intel script already exists | macOS CI |
| 4 | [#26](https://github.com/lukejmorrison/canvasforge/issues/26) Linux AppImage | — | Ubuntu smoke; AUR unchanged |
| 5 | [#27](https://github.com/lukejmorrison/canvasforge/issues/27) Multi-asset Releases + CI | Real artifacts from 2–4 | Same GitHub tag; AUR still uses the source tarball |

## Phase 2 — mobile sister (milestone `pwa-platform`)

Desktop stays PyQt6. Phone is a capture puck, not the editor.

| Order | Issue | Depends on | Test / deploy |
|-------|--------|------------|----------------|
| 6 | [#29](https://github.com/lukejmorrison/canvasforge/issues/29) Flutter `mobile/` | Phase 1 in motion | LAN capture page in `mobile/` ships first; Flutter APK later |
| 7 | [#30](https://github.com/lukejmorrison/canvasforge/issues/30) QR pairing | #29 | Settings → Mobile; LAN/Tailscale; no public host |
| 8 | [#31](https://github.com/lukejmorrison/canvasforge/issues/31) Capture sync | #30 | Shared Image Library folder + local POST |
| 9 | [#32](https://github.com/lukejmorrison/canvasforge/issues/32) Android APK | #29 | Sideload from GitHub Release |

## Phase 3 — stores and iOS

| Order | Issue | Depends on |
|-------|--------|------------|
| 10 | [#34](https://github.com/lukejmorrison/canvasforge/issues/34) winget | #24 |
| 11 | [#35](https://github.com/lukejmorrison/canvasforge/issues/35) Homebrew cask | #25 |
| 12 | [#36](https://github.com/lukejmorrison/canvasforge/issues/36) Flathub | existing Flatpak |
| 13 | [#33](https://github.com/lukejmorrison/canvasforge/issues/33) iOS TestFlight | macOS CI; last |
| 14 | [#37](https://github.com/lukejmorrison/canvasforge/issues/37) Phone annotation subset | pairing works; optional |

Local vs CI: [targets.md](targets.md).
