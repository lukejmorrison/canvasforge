## Learned User Preferences

- Daily-driver testing is the installed `canvasforge` launcher (app menu or `canvasforge`), not `python main.py` from the checkout.
- After checkout changes, fully quit the running CanvasForge window, then reinstall with `scripts/install_canvasforge.sh --local` and launch `~/.local/bin/canvasforge` (not AUR `/usr/bin/canvasforge`).
- Update CanvasForge with `yay -S canvasforge-beta` only; do not use `yay -Syu` just to get a CanvasForge update.
- End-user install should be the `canvasforge-beta` AUR package, with prompts that say to press Enter to accept defaults.
- Ship user-facing updates as a GitHub prerelease plus AUR `canvasforge-beta` so Omarchy can pull them (`omarchy update` / `yay -S canvasforge-beta`).
- Use British spelling in UI copy (colour, eyedropper).

## Learned Workspace Facts

- Two install trees exist: AUR `canvasforge-beta` (`/usr/bin/canvasforge`, `/usr/share/canvasforge`) and a local venv (`~/.local/bin/canvasforge`, `~/.local/share/canvasforge`). The app menu typically runs the AUR copy; checkout `main.py` is not live until reinstalled and the process is restarted.
- AUR publish is a local SSH push to `ssh://aur@aur.archlinux.org/canvasforge-beta.git` (copy `packaging/aur/canvasforge-beta` PKGBUILD and `.SRCINFO` into a separate AUR clone). Cloud agents cannot do this; the maintainer SSH key is local-only.
- GitHub repo is `lukejmorrison/canvasforge`; AUR `canvasforge-beta` consumes the GitHub release tarball.
- On Wayland, `scene.render()` into a viewport-child `paintEvent` causes recursive repaint, hang, and crash; magnifiers must render offscreen first.
- Canvas checkerboard must use a tiled pixmap; a Python per-tile `fillRect` loop on large canvases (~5800px) takes hundreds of ms per paint and hangs eyedropper hover and selection.
