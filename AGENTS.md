## Learned User Preferences

- Daily-driver testing is the installed `canvasforge` launcher (app menu or `canvasforge`), not `python main.py` from the checkout.
- After checkout changes, fully quit the running CanvasForge window, then reinstall with `scripts/install_canvasforge.sh --local` and launch `~/.local/bin/canvasforge` (not AUR `/usr/bin/canvasforge`).
- Update CanvasForge with `yay -S canvasforge-beta` only; do not use `yay -Syu` just to get a CanvasForge update.
- End-user install should be the `canvasforge-beta` AUR package, with prompts that say to press Enter to accept defaults.
- Ship user-facing updates as a GitHub prerelease plus AUR `canvasforge-beta` so Omarchy can pull them (`omarchy update` / `yay -S canvasforge-beta`).
- Use British spelling in UI copy (colour, eyedropper).
- Text boxes should follow Photoshop: Pointer/Move select, drag, and resize; clicking existing text edits it rather than creating another box. Corner handles scale type size; edge handles change box size only.
- Colour Selector Palette should recolour or restyle selected text: the whole box with Pointer/Move, and the current word or selection with the Text tool.
- Bold, italic, and underline must combine (BI, BIU, and so on), not act as exclusive single styles.

## Learned Workspace Facts

- Two install trees exist: AUR `canvasforge-beta` (`/usr/bin/canvasforge`, `/usr/share/canvasforge`) and a local venv (`~/.local/bin/canvasforge`, `~/.local/share/canvasforge`). The app menu typically runs the AUR copy; checkout `main.py` is not live until reinstalled and the process is restarted.
- AUR publish is a local SSH push to `ssh://aur@aur.archlinux.org/canvasforge-beta.git` (copy `packaging/aur/canvasforge-beta` PKGBUILD and `.SRCINFO` into a separate AUR clone). Cloud agents cannot do this; the maintainer SSH key is local-only.
- GitHub repo is `lukejmorrison/canvasforge`; AUR `canvasforge-beta` consumes the GitHub release tarball.
- On Wayland, `scene.render()` into a viewport-child `paintEvent` causes recursive repaint, hang, and crash; magnifiers must render offscreen first.
- Canvas checkerboard must use a tiled pixmap; a Python per-tile `fillRect` loop on large canvases (~5800px) takes hundreds of ms per paint and hangs eyedropper hover and selection.
- CanvasTextItem must leave text interaction off outside edit mode, or pointer drags select characters instead of moving the box. Text edge-handle drags must ignore default aspect-lock (it recentres the unused axis); keep resize handles synced to the live box after type or resize.
- Text B/I/U and colour must merge into the existing QTextCharFormat; `setCharFormat` alone replaces the insertion format and drops combined styles.

## Definition of Done

Agents must not claim a task is complete until the applicable checks below pass (or Luke waives them). Pattern: **GitHub Issue → implement → automated tests (when they exist) → daily-driver local install → GitHub prerelease + AUR `canvasforge-beta`**. See [docs/github-workflow.md](docs/github-workflow.md).

### Always

1. **Scope:** Changes match the requested Issue; no drive-by refactors. One feature or fix per PR/commit series. Do not mix canvas work (e.g. text colour) with later items (e.g. shape stretch) in one commit.
2. **British UI copy:** colour, eyedropper — not color/eyedropper in user-visible strings.
3. **Secrets:** No secrets in code, logs, or commits. AUR publish uses the maintainer SSH key only.
4. **Evidence:** Note what you ran and the outcome.

### Before claiming done

| Check | Command / action |
|-------|------------------|
| Syntax | `python -m py_compile main.py image_library_panel.py undo_manager.py plugin_manager.py` |
| Unit / widget tests | `pip install -r requirements-dev.txt && python -m pytest tests/` (skip only if the change has no test hook) |
| Daily-driver install | Fully quit CanvasForge, then `bash scripts/install_canvasforge.sh --local` |
| Daily-driver launch | `~/.local/bin/canvasforge` — **not** `python main.py`, **not** AUR `/usr/bin/canvasforge` |
| Changelog | User-facing changes listed in `CHANGELOG.md` |
| Issue | Linked GitHub Issue; close it only when the work is in the tagged beta |

### Two install trees

| Tree | Paths | When to use |
|------|--------|-------------|
| Local venv | `~/.local/bin/canvasforge`, `~/.local/share/canvasforge` | After checkout changes (`scripts/install_canvasforge.sh --local`) |
| AUR `canvasforge-beta` | `/usr/bin/canvasforge`, `/usr/share/canvasforge` | End-user / Omarchy (`yay -S canvasforge-beta` only; press Enter at prompts). App menu often runs this copy. |

Checkout `main.py` is not live until reinstalled and the process is restarted.

### Ship

1. Bump `__version__` in `main.py` only when the tree is ready to tag.
2. Move `CHANGELOG.md` `[Unreleased]` bullets into `## [x.y.z-beta.N]`.
3. `scripts/build_release_archive.sh`, `scripts/update_aur_beta_pkgbuild.sh`, `scripts/create_beta_release.sh` (GitHub prerelease).
4. **Stop before AUR git push.** Only the maintainer can push `ssh://aur@aur.archlinux.org/canvasforge-beta.git`. Cloud agents cannot.

### Out of scope for local agents

- Do not block on platforms listed as CI-only in `docs/targets.md`.
- Do not start T1–T10 while the current beta.11 canvas Issue is unfinished, unless Luke asks.
- Do not rewrite CanvasForge as a hosted PWA ([#38](https://github.com/lukejmorrison/canvasforge/issues/38)).
