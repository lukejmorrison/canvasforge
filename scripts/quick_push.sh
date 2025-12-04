#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v git >/dev/null 2>&1; then
	echo "git is not installed or not in PATH" >&2
	exit 1
fi

CHANGES=$(git status --porcelain)
if [[ -z "$CHANGES" ]]; then
	echo "Nothing to commit. Working tree clean."
	exit 0
fi

echo "Changes detected:"
printf '%s
' "$CHANGES"

echo "\nStaging all tracked/untracked files..."
git add -A

COMMIT_MESSAGE=${1:-}
if [[ -z "$COMMIT_MESSAGE" ]]; then
	COMMIT_MESSAGE="chore: quick sync $(date '+%Y-%m-%d %H:%M:%S')"
fi

echo "Committing with message: $COMMIT_MESSAGE"
git commit -m "$COMMIT_MESSAGE"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Pushing to origin/$CURRENT_BRANCH..."
git push origin "$CURRENT_BRANCH"

echo "Done."
