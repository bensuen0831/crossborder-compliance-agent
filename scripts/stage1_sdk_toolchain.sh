#!/usr/bin/env bash
set -Eeuo pipefail
# The full Python suite includes a genuine TypeScript SDK HTTP journey.
# Install only its compiler, at the version already locked by the frontend.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_COMPILER_ROOT="${RUNNER_TEMP:-/tmp}/stage1-sdk-compiler"
TASK_COMPILER_VERSION="$(node -e 'console.log(require(process.argv[1]).packages["node_modules/typescript"].version)' "$ROOT/frontend/package-lock.json")"
npm install --cache "$TASK_COMPILER_ROOT/cache" --prefix "$TASK_COMPILER_ROOT" --no-audit --no-fund --ignore-scripts "typescript@$TASK_COMPILER_VERSION"
if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "STAGE1_TYPESCRIPT_TSC=$TASK_COMPILER_ROOT/node_modules/.bin/tsc" >> "$GITHUB_ENV"
fi
"$TASK_COMPILER_ROOT/node_modules/.bin/tsc" --version
