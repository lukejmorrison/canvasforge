# Contributing to CanvasForge

Thank you for wanting to help. CanvasForge is a native PyQt6 desktop app. Please keep it that way: fast, local, and simple to install.

## Where to post

| You have… | Post it here |
|-----------|----------------|
| An idea, question, or “how do I…” | [Discussions](https://github.com/lukejmorrison/canvasforge/discussions) — Ideas or Q&A |
| Windows / macOS / Linux install or packaging help | [Discussions → Q&A](https://github.com/lukejmorrison/canvasforge/discussions/new?category=q-a&title=Packaging%3A%20) — start the title with `Packaging:` |
| A screenshot or workflow to share | [Discussions → Show and tell](https://github.com/lukejmorrison/canvasforge/discussions/categories/show-and-tell) |
| A reproducible bug | [Issues](https://github.com/lukejmorrison/canvasforge/issues/new?template=bug.yml) |
| Work a maintainer has already accepted | Open a pull request linked to that Issue |

Do not open an Issue for a feature idea. Start a Discussion. If the idea is accepted, a maintainer will open or convert an Issue so a PR has a home.

Tiny docs fixes may link a short Discussion instead of an Issue.

## Development setup

```bash
git clone https://github.com/lukejmorrison/canvasforge.git
cd canvasforge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

That checkout run is for development. End users on Omarchy / Arch install with `yay -S canvasforge-beta` (press Enter at the prompts) and launch `canvasforge` from the app menu. After you change the checkout, a local reinstall is `bash scripts/install_canvasforge.sh --local`.

See [README.md](README.md) for Flatpak, macOS Intel builds, and Omarchy screenshot-editor setup.

## Pull requests

1. Search [open PRs](https://github.com/lukejmorrison/canvasforge/pulls) and [Issues](https://github.com/lukejmorrison/canvasforge/issues) so you are not duplicating work.
2. For anything beyond a small fix, start in Discussions first.
3. Keep the PR focused. Link the Issue (or Discussion) in the template.
4. Update [CHANGELOG.md](CHANGELOG.md) for every user-facing change.
5. Use British spelling in UI copy (colour, eyedropper).
6. Leave these out of commits: screenshots, `pasted_logs/`, and `wizwam-code-review/`.

## Code conventions

CanvasForge is a **monolith**. [`main.py`](main.py) is large on purpose. Do not split it into a package tree unless a maintainer asks.

Read [AGENT.md](AGENT.md) before a substantial code PR. In short:

- Qt overrides stay `camelCase` (`mousePressEvent`).
- Internal helpers prefer `snake_case`.
- Keep imports at the top of the file.
- Prefer a small, fast change over a new abstraction.

Platform work (Windows installer, macOS DMG, AppImage, later `mobile/`) is sequenced in [ROADMAP.md](ROADMAP.md). What you can build locally versus what belongs in CI is in [docs/targets.md](docs/targets.md).
