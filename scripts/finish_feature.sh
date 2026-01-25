#!/bin/bash
# Finish feature and merge to develop
set -e

CURRENT=$(git branch --show-current)
[[ ! "$CURRENT" =~ ^(feature|fix|refactor)/ ]] && { echo "Not on feature/fix branch"; exit 1; }

git config user.name "DevPrakash"
git config user.email "dev.prakash@gmail.com"

# Run regression tests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/run_tests.sh" regression || { echo "Tests failed!"; exit 1; }

# Merge to develop
git checkout develop
git pull origin develop 2>/dev/null || true
git merge "$CURRENT" --no-ff -m "Merge $CURRENT into develop"

echo "Merged $CURRENT into develop"
echo "Next: git push origin develop"
