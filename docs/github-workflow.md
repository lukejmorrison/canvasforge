# GitHub workflow — CanvasForge

Repeatable pattern for product work:

**Issue → implement → test (pytest + daily-driver local install) → GitHub prerelease + AUR `canvasforge-beta`.**

The working backlog is [Issues](https://github.com/lukejmorrison/canvasforge/issues). [TODO.md](../TODO.md) is an index. [Discussions](https://github.com/lukejmorrison/canvasforge/discussions) stay for open-ended ideas, questions, and packaging offers that are not yet accepted work.

## 1. New feature or bug

1. Search Issues and Discussions so you are not duplicating work.
2. Open-ended idea → Discussion. If a maintainer accepts it, they (or you, with agreement) open an Issue.
3. Reproducible bug or accepted product work → [Issue](https://github.com/lukejmorrison/canvasforge/issues/new/choose). One Issue per item.
4. Issue body should include: restatement, acceptance criteria, likely files, test plan, and which beta it ships in.

## 2. Implement

- Link the Issue from the PR or commit (`Fixes #N` when that commit series completes it).
- Keep the change focused. Do not mix unrelated workstreams (for example U1 text colour with T1 shape stretch).
- British spelling in UI copy (colour, eyedropper).
- Update `CHANGELOG.md` for user-facing changes.
- Follow `AGENTS.md` and `AGENT.md` (monolith, Qt naming).

## 3. Test

Automated, when a hook exists:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

Daily-driver (required for UI):

1. Fully quit any running CanvasForge window.
2. `bash scripts/install_canvasforge.sh --local`
3. Launch **`~/.local/bin/canvasforge`** — not `python main.py`, not AUR `/usr/bin/canvasforge`.

Two install trees exist; the app menu often runs the AUR copy. Checkout `main.py` is dead until reinstall + restart. Details in `AGENTS.md`.

## 4. Ship

User-facing updates are a GitHub **prerelease** plus AUR **`canvasforge-beta`** so Omarchy can pull them (`omarchy update` / `yay -S canvasforge-beta`).

1. Bump `__version__` in `main.py` only on a ready tree.
2. Move `[Unreleased]` changelog bullets into `## [x.y.z-beta.N]`.
3. `scripts/build_release_archive.sh <version>`
4. `scripts/update_aur_beta_pkgbuild.sh <version>`
5. Commit PKGBUILD / `.SRCINFO` / version / changelog.
6. `scripts/create_beta_release.sh <version> --push --github-release`
7. **Maintainer only:** copy `packaging/aur/canvasforge-beta/{PKGBUILD,.SRCINFO}` into the AUR clone and `git push` to `ssh://aur@aur.archlinux.org/canvasforge-beta.git`. Cloud agents stop here.
8. End users: `yay -S canvasforge-beta` only (not `yay -Syu`); press Enter at prompts.

Board: [CanvasForge project](https://github.com/users/lukejmorrison/projects/2).
