# CanvasForge Beta AUR Package

This directory contains the AUR recipe for `canvasforge-beta`, the Arch/Omarchy beta channel for CanvasForge.

## Local Build Test

After a matching GitHub tag exists:

```bash
cd packaging/aur/canvasforge-beta
makepkg -f
sudo pacman -U canvasforge-beta-*.pkg.tar.zst
```

## AUR Publish Flow

1. Build a release archive and prepare the AUR checksum:

   ```bash
   scripts/build_release_archive.sh 0.6.0-beta.1
   scripts/update_aur_beta_pkgbuild.sh 0.6.0-beta.1
   ```

2. Commit the beta version/package metadata, then create and publish the GitHub prerelease:

   ```bash
   scripts/create_beta_release.sh 0.6.0-beta.1 --push --github-release
   ```

3. If the release asset was rebuilt after the checksum step, refresh the tarball checksum and `.SRCINFO` again:

   ```bash
   scripts/update_aur_beta_pkgbuild.sh 0.6.0-beta.1
   ```

4. Copy `PKGBUILD` and `.SRCINFO` into the checked-out AUR package repository.
5. Commit and push to `ssh://aur@aur.archlinux.org/canvasforge-beta.git`.

Omarchy users can install with:

```bash
yay -S canvasforge-beta
```

Future beta updates are discovered by Omarchy's update flow once the AUR recipe is bumped and pushed.
