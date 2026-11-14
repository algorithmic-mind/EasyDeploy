#!/usr/bin/env bash
# EasyDeploy uninstaller (§8.4). Removes the panel; asks separately (default: keep) about user data.
#   sudo bash uninstall.sh            interactive
#   sudo bash uninstall.sh --purge --yes   remove everything non-interactively
set -Eeuo pipefail

ED_INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$ED_INSTALLER_DIR/lib/common.sh"
ED_LOG=$ED_LOG_DIR/uninstall.log

PURGE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE=1; shift ;;
    --yes|-y) ED_OPT_YES=1; shift ;;
    -h|--help) echo "Usage: sudo bash uninstall.sh [--purge] [--yes]"; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done
[[ $EUID -eq 0 ]] || die "Run as root"
init_logging

ask_remove() {
  # Default answer is "keep"; --purge removes without asking.
  [[ $PURGE == 1 ]] && return 0
  [[ $ED_OPT_YES == 1 ]] && return 1
  confirm "$1"
}

if [[ $PURGE == 0 && $ED_OPT_YES == 0 ]]; then
  confirm "Remove EasyDeploy from this server?" || { info "Cancelled."; exit 0; }
fi

ED_CURRENT_STEP=services
for unit in easydeploy.target easydeploy-api.service easydeploy-worker.service easydeploy-agent.service; do
  systemctl disable --now "$unit" >>"$ED_LOG" 2>&1 || true
  rm -f "/etc/systemd/system/$unit"
done
rm -f /etc/tmpfiles.d/easydeploy.conf /etc/logrotate.d/easydeploy
systemctl daemon-reload
rm -rf /run/easydeploy
ok "services removed"

ED_CURRENT_STEP=nginx
rm -f /etc/nginx/conf.d/easydeploy.conf /etc/nginx/easydeploy/panel.conf \
  /etc/nginx/easydeploy/default-server.conf
if ask_remove "Remove user website configurations (/etc/nginx/easydeploy/sites)?"; then
  rm -rf /etc/nginx/easydeploy
fi
if nginx -t >>"$ED_LOG" 2>&1; then systemctl reload nginx >>"$ED_LOG" 2>&1 || true; fi
ok "Nginx panel configuration removed"

ED_CURRENT_STEP=files
rm -f /usr/local/bin/edctl
rm -rf "$ED_ROOT/releases" "$ED_ROOT/venvs" "$ED_ROOT/python" "$ED_ROOT/current" "$ED_ROOT/tmp" \
  "$ED_ROOT/catalog" "$ED_ROOT/.installed"
if ask_remove "Remove panel data (database, logs, settings, secrets)?"; then
  rm -rf "$ED_ROOT/data" "$ED_ROOT/logs" "$ED_ETC"
fi

if ask_remove "Remove app/project containers and their data (/opt/easydeploy/apps, projects)?"; then
  if command -v docker >/dev/null; then
    docker ps -aq --filter label=io.easydeploy.managed=true | xargs -r docker rm -f >>"$ED_LOG" 2>&1 || true
    docker network rm easydeploy-net >>"$ED_LOG" 2>&1 || true
  fi
  rm -rf "$ED_ROOT/apps" "$ED_ROOT/projects" "$ED_ROOT/www" "$ED_ROOT/acme"
fi
if ask_remove "Remove backups (/opt/easydeploy/backups)?"; then
  rm -rf "$ED_ROOT/backups"
fi
if ask_remove "Remove certificates (/etc/easydeploy/ssl)?"; then
  rm -rf "$ED_ETC/ssl"
fi
if ask_remove "Uninstall Docker itself?"; then
  apt-get purge -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    >>"$ED_LOG" 2>&1 || true
fi
rmdir "$ED_ROOT" 2>/dev/null || true
if [[ $PURGE == 1 ]]; then
  sed -i '\#^include /etc/redis/easydeploy.conf$#d' /etc/redis/redis.conf 2>/dev/null || true
  rm -f /etc/redis/easydeploy.conf
  systemctl restart redis-server >>"$ED_LOG" 2>&1 || true
  userdel easydeploy >>"$ED_LOG" 2>&1 || true
fi
ok "EasyDeploy removed. Firewall rules were left unchanged (ufw status numbered)."
