#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTENSIONS_DIR="${VSCODE_EXTENSIONS_DIR:-$HOME/.vscode/extensions}"
TARGET_DIR="$EXTENSIONS_DIR/kishanpatel.related-tests-controller-0.1.0"

mkdir -p "$EXTENSIONS_DIR"
rm -rf "$TARGET_DIR"
cp -R "$ROOT_DIR/vscode-related-tests" "$TARGET_DIR"

echo "Installed Related Tests Controller to $TARGET_DIR"
echo "Reload VS Code to see the Related Tests controller in the Testing pane."
