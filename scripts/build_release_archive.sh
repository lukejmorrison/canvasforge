#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/build_release_archive.sh <version>

Example:
  scripts/build_release_archive.sh 0.6.0-beta.1

Builds dist/canvasforge-<version>.tar.gz from the current git HEAD,
respecting .gitattributes export-ignore rules.
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
dist_dir="$repo_root/dist"
archive="$dist_dir/canvasforge-${version}.tar.gz"

mkdir -p "$dist_dir"
git -C "$repo_root" archive \
  --format=tar \
  --prefix="canvasforge-${version}/" \
  'HEAD^{tree}' | gzip -n > "$archive"

echo "$archive"
