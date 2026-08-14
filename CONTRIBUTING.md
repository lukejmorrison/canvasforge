# Contributing to CanvasForge

Thank you for wanting to help. CanvasForge is a native PyQt6 desktop app. Please keep it that way: fast, local, and simple to install.

## Where to post

The working backlog is **[GitHub Issues](https://github.com/lukejmorrison/canvasforge/issues)** ([TODO.md](TODO.md) is an index). Pattern: Issue → implement → test → ship. Details: [docs/github-workflow.md](docs/github-workflow.md).

| You have… | Post it here |
|-----------|----------------|
| An open-ended idea or “how do I…” | [Discussions](https://github.com/lukejmorrison/canvasforge/discussions) — Ideas or Q&A |
| Windows / macOS / Linux install or packaging help | [Discussions → Q&A](https://github.com/lukejmorrison/canvasforge/discussions/new?category=q-a&title=Packaging%3A%20) — start the title with `Packaging:` |
| A screenshot or workflow to share | [Discussions → Show and tell](https://github.com/lukejmorrison/canvasforge/discussions/categories/show-and-tell) |
| A reproducible bug | [Issues](https://github.com/lukejmorrison/canvasforge/issues/new?template=bug.yml) |
| An accepted product feature or fix | [Issues](https://github.com/lukejmorrison/canvasforge/issues/new?template=feature.yml) — one Issue per item |
| Work that already has an Issue | Open a pull request linked to that Issue |

Start a Discussion when the idea is still open-ended. Once it is accepted product work, file or use a GitHub Issue so a PR has a home. Tiny docs fixes may link a short Discussion instead of an Issue.

## Development setup

```bash
git clone https://github.com/lukejmorrison/canvasforge.git
cd canvasforge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

That checkout run is for development. After you change the checkout, fully quit CanvasForge, run `bash scripts/install_canvasforge.sh --local`, and launch **`~/.local/bin/canvasforge`** (not `python main.py`, not AUR `/usr/bin/canvasforge`). End users on Omarchy / Arch install with `yay -S canvasforge-beta` (press Enter at the prompts).

Automated tests: `pip install -r requirements-dev.txt && python -m pytest tests/`.

See [README.md](README.md) for the AUR package, the macOS Intel DMG, Flatpak, and Omarchy screenshot-editor setup.

## Pull requests

1. Search [open PRs](https://github.com/lukejmorrison/canvasforge/pulls) and [Issues](https://github.com/lukejmorrison/canvasforge/issues) so you are not duplicating work.
2. Keep the PR focused. Link the Issue in the template (`Fixes #N` when the PR completes it). Open-ended ideas still start in Discussions.
3. Update [CHANGELOG.md](CHANGELOG.md) for every user-facing change.
4. Use British spelling in UI copy (colour, eyedropper).
5. Leave these out of commits: screenshots, `pasted_logs/`, and `wizwam-code-review/`.

## Code conventions

CanvasForge is a **monolith**. [`main.py`](main.py) is large on purpose. Do not split it into a package tree unless a maintainer asks.

Read [AGENT.md](AGENT.md) before a substantial code PR. In short:

- Qt overrides stay `camelCase` (`mousePressEvent`).
- Internal helpers prefer `snake_case`.
- Keep imports at the top of the file.
- Prefer a small, fast change over a new abstraction.

Platform work (Windows installer, macOS Apple Silicon DMG, AppImage, later `mobile/`) is sequenced in [ROADMAP.md](ROADMAP.md). The Intel x86_64 DMG already ships on GitHub Releases. What you can build locally versus what belongs in CI is in [docs/targets.md](docs/targets.md).
