#!/usr/bin/env bash
# shellcheck disable=SC2029  # remote paths are expanded locally on purpose
# Copy the working tree to a DISPOSABLE Ubuntu VM, install from source, run the acceptance checks (§12).
#   scripts/vm-test.sh root@203.0.113.10 [extra installer options…]
# Works from Linux, macOS and Git Bash on Windows (uses rsync when present, tar over ssh otherwise).
# Never point this at a server you care about: it installs packages and enables UFW.
set -Eeuo pipefail

TARGET=${1:?usage: scripts/vm-test.sh user@host [installer options]}
shift
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR=/root/easydeploy-src
EXCLUDES=(.git .venv node_modules var __pycache__ .mypy_cache .ruff_cache .pytest_cache release)

if [[ ! -f $ROOT/frontend/dist/index.html ]]; then
  echo "==> building the frontend"
  (cd "$ROOT/frontend" && npm run build)
fi

# One SSH connection for all steps (one password prompt) where ControlMaster is supported.
SOCK="${TMPDIR:-/tmp}/ed-vm-test-$$"
SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=$SOCK" -o ControlPersist=600)
if ! ssh "${SSH_OPTS[@]}" -O check "$TARGET" 2>/dev/null; then
  ssh "${SSH_OPTS[@]}" -fN "$TARGET" 2>/dev/null || SSH_OPTS=()
fi
cleanup() {
  if [[ ${#SSH_OPTS[@]} -gt 0 ]]; then
    ssh "${SSH_OPTS[@]}" -O exit "$TARGET" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> copying the source to $TARGET:$REMOTE_DIR"
if command -v rsync >/dev/null; then
  rsync -az --delete "${EXCLUDES[@]/#/--exclude=}" -e "ssh ${SSH_OPTS[*]}" "$ROOT/" "$TARGET:$REMOTE_DIR/"
else
  tar -C "$ROOT" "${EXCLUDES[@]/#/--exclude=}" -czf - . \
    | ssh "${SSH_OPTS[@]}" "$TARGET" "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR && tar -xzf - -C $REMOTE_DIR"
fi
# Line endings must be LF on the server (the checkout may be CRLF on Windows).
ssh "${SSH_OPTS[@]}" "$TARGET" "find $REMOTE_DIR/installer $REMOTE_DIR/scripts $REMOTE_DIR/deploy -type f \
  \\( -name '*.sh' -o -name '*.env' -o -name '*.conf' -o -name '*.service' -o -name '*.target' -o -name '*.template' \\) \
  -exec sed -i 's/\\r\$//' {} +"

echo "==> running the installer"
START=$(date +%s)
ssh -t "${SSH_OPTS[@]}" "$TARGET" "bash $REMOTE_DIR/installer/install.sh --from-source $REMOTE_DIR --yes $*"
echo "==> install took $(( $(date +%s) - START )) s"

echo "==> acceptance checks"
ssh -t "${SSH_OPTS[@]}" "$TARGET" "bash $REMOTE_DIR/scripts/vm-acceptance.sh"
