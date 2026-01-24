#!/bin/bash
# Create release
set -e

[ -z "$1" ] && { echo "Usage: ./release.sh <version>"; exit 1; }
[[ ! "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && { echo "Invalid version. Use X.Y.Z"; exit 1; }

VERSION=$1

git config user.name "DevPrakash"
git config user.email "dev.prakash@gmail.com"

# Run checks
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/pre_deploy_check.sh" || exit 1

# Merge and tag
git checkout main
git pull origin main 2>/dev/null || true
git merge develop --no-ff -m "Release v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin main
git push origin "v$VERSION"
git checkout develop

echo "Released v$VERSION"
