#!/bin/bash
# Cross-platform build script for OpenClaw Brain

set -e

VERSION=$(cat version.txt)
BUILD_DIR="build/dist"
DIST_DIR="dist"

echo "🏗️  Building OpenClaw Brain v${VERSION}"

# Create directories
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel pyinstaller build

# Build source distribution
echo "📚 Building source distribution..."
python -m build --sdist --outdir "$DIST_DIR"

# Build platform-specific wheels
echo "🛞 Building wheels..."
python -m build --wheel --outdir "$DIST_DIR"

# Build standalone executables
echo "🔨 Building executables..."
python -m PyInstaller build/openclaw.spec --distpath "$BUILD_DIR"

# Package executables by platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "📦 Packaging Linux executable..."
    cd "$BUILD_DIR"
    tar -czf "openclaw-brain-${VERSION}-linux-x86_64.tar.gz" openclaw-brain
    mv "openclaw-brain-${VERSION}-linux-x86_64.tar.gz" "../../$DIST_DIR/"
    cd ../../
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "📦 Packaging macOS executable..."
    cd "$BUILD_DIR"
    zip -r "openclaw-brain-${VERSION}-macos-universal2.zip" openclaw-brain
    mv "openclaw-brain-${VERSION}-macos-universal2.zip" "../../$DIST_DIR/"
    cd ../../
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "📦 Packaging Windows executable..."
    cd "$BUILD_DIR"
    powershell -Command "Compress-Archive -Path openclaw-brain -DestinationPath \"openclaw-brain-${VERSION}-windows-x86_64.zip\""
    move "openclaw-brain-${VERSION}-windows-x86_64.zip" "..\..\$DIST_DIR\"
    cd ../../
fi

echo "✅ Build complete! Artifacts in $DIST_DIR/"
ls -lah "$DIST_DIR"
