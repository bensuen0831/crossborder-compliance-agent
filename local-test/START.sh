#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3.12 >/dev/null 2>&1; then
  echo '需要 Ubuntu 24.04 / Linux amd64、Python3.12及venv。請先閱讀 START_HERE.md。'
  exit 1
fi
if [ "$#" -eq 0 ]; then
  echo 'Stage1 本機隔離測試包（不會自動批准安全／法律驗收）'
  echo '1 初始化虛擬環境與專用資料庫；2 啟動；3 建立業務帳號；4 狀態；5 停止並保留資料；6 校驗套件；0 離開'
  read -r -p '請選擇: ' selection
  case "$selection" in
    1) set -- setup;; 2) set -- start;; 3) read -r -p '本機帳號名稱: ' account; set -- account --username "$account" --role business;;
    4) set -- status;; 5) set -- stop;; 6) set -- verify;; 0) exit 0;; *) echo '無效選擇'; exit 1;;
  esac
fi
exec python3.12 "$PACKAGE_ROOT/launcher/local.py" "$@"
