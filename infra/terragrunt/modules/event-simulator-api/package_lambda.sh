#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$1"
BUILD_DIR="$2"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if [[ -f "$APP_DIR/requirements.txt" ]] && [[ -s "$APP_DIR/requirements.txt" ]]; then
  python3 -m pip install \
    --requirement "$APP_DIR/requirements.txt" \
    --target "$BUILD_DIR"
fi

cp -R "$APP_DIR/." "$BUILD_DIR/"
find "$BUILD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete
