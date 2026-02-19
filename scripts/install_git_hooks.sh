#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p .githooks
chmod +x .githooks/pre-commit

git config core.hooksPath .githooks
echo "Installed git hooks: core.hooksPath=.githooks"
