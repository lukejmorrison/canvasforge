#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/create_beta_release.sh <version> [--push] [--github-release]

Example:
  scripts/create_beta_release.sh 0.6.0-beta.1 --push --github-release

Creates an annotated beta tag and release archive. With --push, pushes
the tag to origin. With --github-release, creates a GitHub prerelease
for the tag using gh and uploads the archive asset.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

version="${1:-}"
if [[ $# -gt 0 ]]; then
  shift
fi

push_tag=false
github_release=false
for arg in "$@"; do
  case "$arg" in
    --push) push_tag=true ;;
    --github-release) github_release=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Error: unknown argument: $arg" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$version" || ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+$ ]]; then
  usage
  exit 1
fi

tag="v${version}"
repo_root="$(git rev-parse --show-toplevel)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree must be clean before tagging" >&2
  exit 1
fi

if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "Error: tag $tag already exists" >&2
  exit 1
fi

git tag -a "$tag" -m "CanvasForge ${version}"

archive="$("$repo_root/scripts/build_release_archive.sh" "$version")"

if [[ "$push_tag" == true ]]; then
  git push origin "$tag"
fi

if [[ "$github_release" == true ]]; then
  command -v gh >/dev/null 2>&1 || { echo "Error: gh is required" >&2; exit 1; }
  gh release create "$tag" \
    "$archive" \
    --title "CanvasForge ${version}" \
    --notes-from-tag \
    --prerelease
fi

echo "Created beta release tag $tag"
echo "Release archive: $archive"
