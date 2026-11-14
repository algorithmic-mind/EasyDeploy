#!/usr/bin/env bash
# Copy the working tree to a DISPOSABLE Ubuntu VM and run the installer from source (§12).
#   scripts/vm-test.sh root@203.0.113.10 [extra installer options…]
# Never point this at a server you care about: it installs packages and enables UFW.
set -Eeuo pipefail

TARGET=${1:?usage: scripts/vm-test.sh user@host [installer options]}
shift
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f $ROOT/frontend/dist/index.html ]]; then
  echo "==> building the frontend"
  (cd "$ROOT/frontend" && npm run build)
fi

echo "==> syncing to $TARGET:/root/easydeploy-src"
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude 'var' \
  --exclude '__pycache__' --exclude '.mypy_cache' --exclude '.ruff_cache' --exclude '.pytest_cache' \
  "$ROOT/" "$TARGET:/root/easydeploy-src/"

echo "==> running the installer"
ssh -t "$TARGET" "bash /root/easydeploy-src/installer/install.sh --from-source /root/easydeploy-src --yes $*"
