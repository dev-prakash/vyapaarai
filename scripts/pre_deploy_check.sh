#!/bin/bash
# Pre-deployment checks
set -e

echo "=== Pre-Deploy Check ==="

# Check uncommitted changes
[ -n "$(git status --porcelain)" ] && { echo "Uncommitted changes detected"; exit 1; }
echo "Working directory clean"

# Check git author
[ "$(git config user.name)" != "DevPrakash" ] && { echo "Wrong git author"; exit 1; }
echo "Git author: DevPrakash"

# Run regression tests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/run_tests.sh" regression || { echo "Tests failed"; exit 1; }
echo "Regression tests passed"

echo ""
echo "Ready to deploy!"
