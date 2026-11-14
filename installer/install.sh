#!/usr/bin/env bash
# EasyDeploy installer (v0) — MASTER_PROMPT §8.
#
#   One command (downloads the latest release):
#     curl -fsSL https://raw.githubusercontent.com/algorithmic-mind/EasyDeploy/main/installer/install.sh -o install.sh && sudo bash install.sh
#   From a release tarball:      sudo bash install.sh --release-file easydeploy-<ver>-linux-<arch>.tar.gz
#   From a source checkout:      sudo bash installer/install.sh --from-source   (development only)
#
# Every step is idempotent: after a failure, fix the cause and run the same command again.
set -Eeuo pipefail

ED_DEFAULT_RELEASE_URL=https://github.com/algorithmic-mind/EasyDeploy/releases

# ------------------------------------------------------------------ bootstrap
# When install.sh runs on its own (downloaded with curl), fetch the release tarball, verify its
# SHA-256 against SHA256SUMS (fail closed) and run the installer bundled in the release.
# Release layout (GitHub Releases or a mirror with the same paths):
#   <base>/latest/download/VERSION
#   <base>/download/v<ver>/easydeploy-<ver>-linux-<arch>.tar.gz  and  .../SHA256SUMS
ed_bootstrap() {
  local base=${ED_RELEASE_URL:-$ED_DEFAULT_RELEASE_URL} version=${ED_VERSION:-} file="" arg prev=""
  for arg in "$@"; do
    case $prev in
      --release-url) base=$arg ;;
      --version) version=$arg ;;
      --release-file) file=$arg ;;
    esac
    prev=$arg
  done
  [[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash install.sh" >&2; exit 1; }
  local cmd
  for cmd in curl tar sha256sum; do
    command -v "$cmd" >/dev/null || { echo "$cmd is required (apt-get install -y $cmd)" >&2; exit 1; }
  done
  local work
  work=$(mktemp -d /var/tmp/easydeploy-bootstrap.XXXXXX)

  if [[ -z $file ]]; then
    local arch
    case "$(uname -m)" in
      x86_64) arch=amd64 ;;
      aarch64) arch=arm64 ;;
      *) echo "Unsupported architecture $(uname -m)" >&2; exit 1 ;;
    esac
    base=${base%/}
    if [[ -z $version ]]; then
      echo "==> Looking up the latest release at $base"
      version=$(curl -fsSL --retry 3 "$base/latest/download/VERSION" | tr -d '[:space:]') \
        || { echo "Cannot reach $base (use --release-url <mirror> or --release-file <tarball>)" >&2; exit 1; }
    fi
    version=${version#v}
    [[ $version =~ ^[0-9A-Za-z.+_-]+$ ]] || { echo "Invalid version '$version'" >&2; exit 1; }
    local name="easydeploy-$version-linux-$arch.tar.gz"
    echo "==> Downloading EasyDeploy $version ($arch)"
    curl -fSL --retry 3 --progress-bar "$base/download/v$version/$name" -o "$work/$name" \
      || { echo "Download failed: $base/download/v$version/$name" >&2; exit 1; }
    curl -fsSL --retry 3 "$base/download/v$version/SHA256SUMS" -o "$work/SHA256SUMS" \
      || { echo "Cannot download SHA256SUMS; refusing to install an unverified release" >&2; exit 1; }
    file="$work/$name"
  fi

  local dir sums
  dir=$(dirname "$file")
  sums="$dir/SHA256SUMS"
  [[ -f $sums ]] || { echo "SHA256SUMS not found next to $file; refusing to install" >&2; exit 1; }
  # Lines look like "<hash>  <name>" (or "<hash> *<name>" when written in binary mode).
  (cd "$dir" && awk -v f="$(basename "$file")" '$2 == f || $2 == "*" f' SHA256SUMS | sha256sum -c -) \
    || { echo "Checksum verification FAILED for $(basename "$file")" >&2; exit 1; }
  echo "==> Checksum verified (signature verification arrives with Phase 6)"

  mkdir -p "$work/release"
  tar -xzf "$file" -C "$work/release" --strip-components=1 --no-same-owner
  [[ -f $work/release/installer/install.sh ]] || { echo "The release has no installer" >&2; exit 1; }
  exec bash "$work/release/installer/install.sh" "$@"
}

ED_INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
if [[ ! -f $ED_INSTALLER_DIR/lib/common.sh ]]; then
  ed_bootstrap "$@"
fi

# shellcheck source=lib/common.sh
source "$ED_INSTALLER_DIR/lib/common.sh"
# shellcheck source=lib/preflight.sh
source "$ED_INSTALLER_DIR/lib/preflight.sh"
# shellcheck source=lib/mirrors.sh
source "$ED_INSTALLER_DIR/lib/mirrors.sh"
# shellcheck source=lib/packages.sh
source "$ED_INSTALLER_DIR/lib/packages.sh"
# shellcheck source=lib/docker.sh
source "$ED_INSTALLER_DIR/lib/docker.sh"
# shellcheck source=lib/python.sh
source "$ED_INSTALLER_DIR/lib/python.sh"
# shellcheck source=lib/panel.sh
source "$ED_INSTALLER_DIR/lib/panel.sh"
# shellcheck source=lib/nginx.sh
source "$ED_INSTALLER_DIR/lib/nginx.sh"
# shellcheck source=lib/firewall.sh
source "$ED_INSTALLER_DIR/lib/firewall.sh"
# shellcheck source=lib/systemd.sh
source "$ED_INSTALLER_DIR/lib/systemd.sh"
# shellcheck source=lib/summary.sh
source "$ED_INSTALLER_DIR/lib/summary.sh"

main() {
  parse_args "$@"
  init_logging
  trap 'on_error $? $LINENO' ERR
  umask 0022

  printf '%s\n' "${C_BOLD}EasyDeploy installer${C_RESET}  (log: $ED_LOG)"
  run_step "preflight" preflight_run
  release_detect
  if [[ $ED_OPT_DRY_RUN == 1 ]]; then
    mirrors_load_profile
    info "dry run: mode=$ED_MODE source=$ED_SOURCE_DIR profile=$ED_OPT_MIRROR_PROFILE"
    ok "preflight passed; nothing was changed"
    exit 0
  fi
  run_step "mirrors" mirrors_apply
  run_step "packages" packages_install
  run_step "docker" docker_setup
  run_step "release" release_place
  run_step "users" users_and_dirs
  run_step "python" python_setup
  run_step "config" config_and_secrets
  run_step "redis" redis_configure
  run_step "database" database_setup
  run_step "lego" lego_install
  run_step "nginx" nginx_setup
  run_step "systemd" systemd_setup
  run_step "firewall" firewall_setup
  run_step "edctl" edctl_link
  run_step "health" health_check
  # Remove the temporary download of a bootstrapped install (the release now lives in $ED_ROOT).
  if [[ $ED_SOURCE_DIR == /var/tmp/easydeploy-bootstrap.*/release ]]; then
    rm -rf -- "${ED_SOURCE_DIR%/release}"
  fi
  summary_print
}

main "$@"
