#!/bin/bash
set -e

WORKSPACE_DIR="/mnt/c/Users/rishi/Desktop/CD EL/compile-time-stack-usage-analyser"
BUILD_SRC="/tmp/build_src"

echo "=== Setting up build directory in native storage ==="
mkdir -p "$BUILD_SRC"
cp "$WORKSPACE_DIR/CMakeLists.txt" "$WORKSPACE_DIR/StackExtractor.cpp" "$WORKSPACE_DIR/StackSizeCollector.cpp" "$BUILD_SRC/"

echo "=== Running CMake configuration ==="
cd "$BUILD_SRC"
cmake -B build -S .

echo "=== Building targets ==="
cmake --build build

echo "=== Copying binaries back to workspace ==="
mkdir -p "$WORKSPACE_DIR/build"
cp build/stack-extractor build/stack-size-collector "$WORKSPACE_DIR/build/"
echo "=== Build finished successfully ==="
