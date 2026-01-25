#!/bin/bash
# =============================================================================
# VyapaarAI Pre-Deployment Checks
# Run this before ANY deployment to production
#
# Checks:
# 1. Git working directory is clean
# 2. Git author is correct
# 3. All critical regression tests pass
# 4. All unit tests pass
#
# Author: DevPrakash
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "=============================================="
echo " VyapaarAI Pre-Deployment Checks"
echo "=============================================="
echo ""

# Check 1: Uncommitted changes
echo -n "Checking git status... "
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}FAIL${NC}"
    echo "Uncommitted changes detected:"
    git status --short
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}OK${NC} (working directory clean)"
fi

# Check 2: Git author
echo -n "Checking git author... "
if [ "$(git config user.name)" != "DevPrakash" ]; then
    echo -e "${YELLOW}WARN${NC} (git author: $(git config user.name))"
else
    echo -e "${GREEN}OK${NC} (DevPrakash)"
fi

# Check 3: Run comprehensive test suite
echo ""
echo "Running comprehensive test suite..."
echo ""

"$SCRIPT_DIR/run_all_tests.sh" quick || {
    echo ""
    echo -e "${RED}=== PRE-DEPLOYMENT CHECK FAILED ===${NC}"
    echo "Fix the failing tests before deploying."
    exit 1
}

echo ""
echo -e "${GREEN}=== PRE-DEPLOYMENT CHECK PASSED ===${NC}"
echo "Ready to deploy!"
echo ""
