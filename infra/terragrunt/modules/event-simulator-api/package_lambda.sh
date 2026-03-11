#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$1"
BUILD_DIR="$2"
RUNTIME="$3"
ARCHITECTURE="$4"

case "$RUNTIME" in
  python3.12) PYTHON_VERSION="3.12" ;;
  python3.11) PYTHON_VERSION="3.11" ;;
  python3.10) PYTHON_VERSION="3.10" ;;
  *) echo "Unsupported runtime for packaging: $RUNTIME" >&2; exit 1 ;;
esac

case "$ARCHITECTURE" in
  x86_64) PLATFORM="manylinux2014_x86_64" ;;
  arm64) PLATFORM="manylinux2014_aarch64" ;;
  *) echo "Unsupported Lambda architecture: $ARCHITECTURE" >&2; exit 1 ;;
esac

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if [[ -f "$APP_DIR/requirements.txt" ]] && [[ -s "$APP_DIR/requirements.txt" ]]; then
  python3 -m pip install \
    --requirement "$APP_DIR/requirements.txt" \
    --only-binary=:all: \
    --platform "$PLATFORM" \
    --implementation cp \
    --python-version "$PYTHON_VERSION" \
    --target "$BUILD_DIR"
fi

cp -R "$APP_DIR/." "$BUILD_DIR/"
find "$BUILD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete
