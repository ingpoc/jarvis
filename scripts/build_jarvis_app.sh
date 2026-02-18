#!/bin/bash
# Build and verify JarvisApp for menu bar

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

JARVIS_DIR="/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac"
BUILD_DIR="$JARVIS_DIR/JarvisApp"
DERIVED_DATA="/tmp/jarvis-swift-build-$$"

echo "=========================================="
echo "JarvisApp Swift Build Verification"
echo "=========================================="

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf "$DERIVED_DATA"
rm -rf "$BUILD_DIR/.build/debug/JarvisApp.app"

# Build with fresh DerivedData
echo ""
echo "Building JarvisApp..."
if cd "$BUILD_DIR" && xcodebuild \
    -scheme JarvisApp \
    -configuration Debug \
    -destination 'platform=macOS' \
    -derivedDataPath "$DERIVED_DATA" \
    build 2>&1 | tail -20; then
    echo ""
    echo -e "${GREEN}✓ Build succeeded${NC}"
else
    echo ""
    echo -e "${RED}✗ Build failed${NC}"
    rm -rf "$DERIVED_DATA"
    exit 1
fi

# Verify app bundle exists
echo ""
echo "Verifying app bundle..."
if [ -f "$DERIVED_DATA/Build/Products/Debug/JarvisApp" ]; then
    echo -e "${GREEN}✓ Executable found${NC}"
else
    echo -e "${RED}✗ Executable not found${NC}"
    rm -rf "$DERIVED_DATA"
    exit 1
fi

# Copy to debug location
echo ""
echo "Installing to debug location..."
mkdir -p "$BUILD_DIR/.build/debug/JarvisApp.app/Contents/MacOS"
cp "$DERIVED_DATA/Build/Products/Debug/JarvisApp" "$BUILD_DIR/.build/debug/JarvisApp.app/Contents/MacOS/"

# Copy frameworks if present
if [ -d "$DERIVED_DATA/Build/Products/Debug/PackageFrameworks" ]; then
    mkdir -p "$BUILD_DIR/.build/debug/JarvisApp.app/Contents/Frameworks"
    cp -r "$DERIVED_DATA/Build/Products/Debug/PackageFrameworks" "$BUILD_DIR/.build/debug/JarvisApp.app/Contents/Frameworks/"
fi

echo -e "${GREEN}✓ JarvisApp ready${NC}"

# Cleanup
rm -rf "$DERIVED_DATA"

echo ""
echo "=========================================="
echo "Build verification complete!"
echo "=========================================="
