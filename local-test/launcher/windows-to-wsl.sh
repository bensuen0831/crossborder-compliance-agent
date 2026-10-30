#!/usr/bin/env bash
set -euo pipefail
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/stage1-local-20261030-1"
if [ ! -d "$TARGET_DIR" ]; then
  mkdir -m 700 -- "$TARGET_DIR"
  cp -a -- "$SOURCE_DIR/." "$TARGET_DIR/"
else
  if [ ! -f "$TARGET_DIR/PACKAGE_ID.txt" ] || [ "$(cat "$TARGET_DIR/PACKAGE_ID.txt")" != 'stage1-local-20261030-1' ]; then
    echo '既有目錄不是此套件，拒絕覆蓋或執行。'; exit 1
  fi
  echo '沿用WSL內既有套件與資料；不覆蓋、不重新複製。'
fi
cd -- "$TARGET_DIR"
exec bash ./START.sh "$@"
