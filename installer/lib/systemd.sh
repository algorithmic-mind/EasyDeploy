#!/usr/bin/env bash
# Steps 12 and 14 — systemd units + target, logrotate, edctl symlink.

ED_UNITS=(easydeploy-agent.service easydeploy-api.service easydeploy-worker.service easydeploy.target)

systemd_setup() {
  local src=$ED_RELEASE_DIR/deploy/systemd unit
  for unit in "${ED_UNITS[@]}"; do
    install -m 0644 "$src/$unit" "/etc/systemd/system/$unit"
  done
  install -m 0644 "$src/easydeploy.tmpfiles.conf" /etc/tmpfiles.d/easydeploy.conf
  install -m 0644 "$ED_RELEASE_DIR/deploy/logrotate/easydeploy" /etc/logrotate.d/easydeploy
  run systemd-tmpfiles --create /etc/tmpfiles.d/easydeploy.conf
  run systemctl daemon-reload
  for unit in "${ED_UNITS[@]}"; do run systemctl enable "$unit"; done
  run systemctl restart easydeploy.target || die "Starting easydeploy.target failed (journalctl -u 'easydeploy-*')"
  ok "services enabled and started"
}

edctl_link() {
  ln -sfn "$ED_ROOT/current/venv/bin/edctl" /usr/local/bin/edctl
  ok "edctl available at /usr/local/bin/edctl"
}
