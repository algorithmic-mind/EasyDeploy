#!/usr/bin/env bash
# Build a release tarball for the current architecture (§8.5). Run on Linux (CI or WSL):
#   scripts/build_release.sh [version]
# Produces release/easydeploy-<ver>-linux-<arch>.tar.gz and release/SHA256SUMS.
# Signing (minisign), the bundled lego binary and offline bundles are added in Phase 6.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=${1:-$(git -C "$ROOT" describe --tags --always 2>/dev/null | sed 's/^v//' || echo 0.1.0-dev)}
case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64) ARCH=arm64 ;;
  *) echo "unsupported architecture" >&2; exit 1 ;;
esac
NAME="easydeploy-$VERSION-linux-$ARCH"
OUT="$ROOT/release"
STAGE="$OUT/$NAME"

command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
rm -rf "$STAGE" && mkdir -p "$STAGE/app" "$STAGE/wheels"

echo "==> frontend"
(cd "$ROOT/frontend" && npm ci --no-audit --no-fund && npm run build)
cp -a "$ROOT/frontend/dist" "$STAGE/frontend"

echo "==> application"
for item in backend agent cli pyproject.toml uv.lock; do cp -a "$ROOT/$item" "$STAGE/app/"; done
find "$STAGE/app" \( -name '__pycache__' -o -name 'tests' -o -name '*.db' \) -prune -exec rm -rf {} +
cp -a "$ROOT/deploy" "$ROOT/installer" "$STAGE/"
cat >"$STAGE/install.sh" <<'WRAPPER'
#!/usr/bin/env bash
# Entry point of an extracted release: sudo bash install.sh [options]
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/installer/install.sh" "$@"
WRAPPER
chmod +x "$STAGE/install.sh"
printf '%s\n' "$VERSION" >"$STAGE/VERSION"

echo "==> bundled CPython 3.12"
PYDIR=$(mktemp -d)
UV_PYTHON_INSTALL_DIR="$PYDIR" uv python install 3.12
PYHOME=$(find "$PYDIR" -maxdepth 1 -type d -name 'cpython-3.12*' | head -n1)
cp -a "$PYHOME" "$STAGE/python"
rm -rf "$PYDIR"

echo "==> wheelhouse"
(cd "$ROOT" && uv export --frozen --no-dev --all-packages --no-emit-workspace --no-hashes \
  --output-file "$STAGE/wheels/requirements.txt")
# Build wheels with the bundled interpreter (correct ABI/platform tags) from a throwaway venv,
# because uv-managed Pythons are marked externally managed.
BUILDVENV=$(mktemp -d)
"$STAGE/python/bin/python3" -m venv "$BUILDVENV"
"$BUILDVENV/bin/pip" install --quiet --upgrade pip wheel
"$BUILDVENV/bin/pip" wheel --quiet -r "$STAGE/wheels/requirements.txt" -w "$STAGE/wheels"
rm -rf "$BUILDVENV"
(cd "$ROOT" && uv build --wheel --package easydeploy-agent --out-dir "$STAGE/wheels" \
  && uv build --wheel --package edctl --out-dir "$STAGE/wheels")

echo "==> archive"
tar -C "$OUT" -czf "$OUT/$NAME.tar.gz" "$NAME"
(cd "$OUT" && sha256sum "$NAME.tar.gz" >SHA256SUMS)
rm -rf "$STAGE"
echo "built $OUT/$NAME.tar.gz"
