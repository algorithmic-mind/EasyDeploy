#!/usr/bin/env bash
# EasyDeploy installer (v0) — MASTER_PROMPT §8.
#
#   From an extracted release:   sudo bash install.sh
#   From a release tarball:      sudo bash install.sh --release-file easydeploy-<ver>-linux-<arch>.tar.gz
#   From a source checkout:      sudo bash installer/install.sh --from-source   (development only)
#
# Every step is idempotent: after a failure, fix the cause and run the same command again.
set -Eeuo pipefail

ED_INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f $ED_INSTALLER_DIR/lib/common.sh ]]; then
  echo "install.sh must run from an extracted release or a source checkout (lib/ not found)." >&2
  echo "One-line online installs with signed releases arrive in Phase 6." >&2
  exit 1
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
  summary_print
}

main "$@"
