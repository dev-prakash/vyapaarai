#!/bin/bash
# Create bug fix branch
set -e

[ -z "$1" ] && { echo "Usage: ./new_fix.sh <fix-name>"; exit 1; }

git config user.name "DevPrakash"
git config user.email "dev.prakash@gmail.com"

git checkout develop
git pull origin develop 2>/dev/null || true
git checkout -b "fix/$1"

echo "Created fix/$1"
echo "When done: ./scripts/finish_feature.sh"
