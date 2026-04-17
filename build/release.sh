#!/bin/bash
# Release script for OpenClaw Brain

set -e

VERSION=$(cat version.txt)
TAG="v${VERSION}"

echo "🚀 Releasing OpenClaw Brain v${VERSION}"

# Check if tag exists
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "❌ Tag $TAG already exists!"
    exit 1
fi

# Verify no uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Uncommitted changes detected. Please commit or stash first."
    exit 1
fi

# Create tag
echo "📌 Creating tag $TAG..."
git tag -a "$TAG" -m "Release OpenClaw Brain $VERSION"

# Push tag (triggers GitHub Actions)
echo "🚀 Pushing tag to GitHub (this triggers automated builds)..."
git push origin "$TAG"

echo "✅ Release initiated! GitHub Actions will build for all platforms."
echo "📊 Monitor progress at: https://github.com/1h0lde4/OpenClaw-Brain/actions"
echo "📦 Releases will appear at: https://github.com/1h0lde4/OpenClaw-Brain/releases"
