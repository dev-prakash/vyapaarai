#!/bin/bash
# Create new feature branch
set -e

[ -z "$1" ] && { echo "Usage: ./new_feature.sh <feature-name>"; exit 1; }

git config user.name "DevPrakash"
git config user.email "dev.prakash@gmail.com"

git checkout develop
git pull origin develop 2>/dev/null || true
git checkout -b "feature/$1"

echo "Created feature/$1"
echo "When done: ./scripts/finish_feature.sh"
