#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/update_aur_beta_pkgbuild.sh <version>

Example:
  scripts/update_aur_beta_pkgbuild.sh 0.6.0-beta.1

Updates packaging/aur/canvasforge-beta/PKGBUILD to the Arch-friendly
pkgver form, calculates the matching release tarball sha256sum, and
regenerates .SRCINFO.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

version="$1"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+$ ]]; then
  echo "Error: version must look like 0.6.0-beta.1" >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pkgdir="$repo_root/packaging/aur/canvasforge-beta"
pkgbuild="$pkgdir/PKGBUILD"
tag="v${version}"
pkgver="${version/-beta./_beta}"
asset_name="canvasforge-${version}.tar.gz"
local_asset="$repo_root/dist/$asset_name"
url="https://github.com/lukejmorrison/canvasforge/releases/download/${tag}/${asset_name}"
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

command -v curl >/dev/null 2>&1 || { echo "Error: curl is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "Error: sha256sum is required" >&2; exit 1; }
command -v makepkg >/dev/null 2>&1 || { echo "Error: makepkg is required" >&2; exit 1; }

if [[ -f "$local_asset" ]]; then
  cp "$local_asset" "$tmpfile"
else
  curl -fsSL "$url" -o "$tmpfile"
fi
sum="$(sha256sum "$tmpfile" | awk '{print $1}')"

sed -i \
  -e "s/^pkgver=.*/pkgver=${pkgver}/" \
  -e "s/^sha256sums=.*/sha256sums=('${sum}')/" \
  "$pkgbuild"

(cd "$pkgdir" && makepkg --printsrcinfo > .SRCINFO)

echo "Updated $pkgbuild for ${tag}"
echo "sha256sum=${sum}"
