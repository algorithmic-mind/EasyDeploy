#!/usr/bin/env bash
# Step 13 — UFW. The real SSH port is allowed FIRST so enabling the firewall cannot lock us out.

ssh_ports() {
  local ports
  ports=$(sshd -T 2>/dev/null | awk '$1 == "port" {print $2}' | sort -u)
  [[ -n $ports ]] || ports=22
  printf '%s\n' "$ports"
}

firewall_setup() {
  if [[ $ED_OPT_NO_FIREWALL == 1 ]]; then
    warn "--no-firewall: UFW left unchanged; open ports 80, 443 and $ED_PANEL_PORT yourself"
    return 0
  fi
  command -v ufw >/dev/null || die "ufw is not installed"
  local active=0 port
  ufw status 2>/dev/null | grep -q "^Status: active" && active=1

  while read -r port; do
    run ufw allow "$port/tcp" comment "SSH"
  done < <(ssh_ports)
  run ufw allow 80/tcp comment "HTTP"
  run ufw allow 443/tcp comment "HTTPS"
  run ufw allow "$ED_PANEL_PORT/tcp" comment "EasyDeploy panel"

  if [[ $active == 0 ]]; then
    run ufw --force enable || die "Could not enable UFW"
    ok "UFW enabled (SSH $(ssh_ports | paste -sd, -), 80, 443, $ED_PANEL_PORT)"
  else
    ok "UFW rules added (SSH $(ssh_ports | paste -sd, -), 80, 443, $ED_PANEL_PORT)"
  fi
}
