#!/usr/bin/env bash
# Step 3 — base packages (§8.2).

ED_BASE_PACKAGES=(
  ca-certificates curl gnupg tar zstd unzip git jq sqlite3 openssl
  nginx redis-server ufw logrotate fail2ban iproute2 procps
)

packages_install() {
  export DEBIAN_FRONTEND=noninteractive
  local -a pkgs=("${ED_BASE_PACKAGES[@]}")
  # Source installs bootstrap uv with the system Python (python3-venv).
  [[ $ED_MODE == source ]] && pkgs+=(python3 python3-venv)

  local missing=() p
  for p in "${pkgs[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    ok "base packages already installed"
  else
    info "installing: ${missing[*]}"
    run apt-get update -q || die "apt-get update failed (check the apt mirror / network)"
    run apt-get install -y -q --no-install-recommends "${missing[@]}" \
      || die "apt-get install failed"
    ok "installed ${#missing[@]} packages"
  fi

  # Fail2ban is installed but its jails stay disabled until configured in the panel (§8.2).
  if systemctl is-enabled --quiet fail2ban 2>/dev/null && [[ ! -f /etc/fail2ban/jail.d/easydeploy.conf ]]; then
    run systemctl disable --now fail2ban || true
  fi
  # The distribution's default site would answer for unknown hosts on port 80.
  rm -f /etc/nginx/sites-enabled/default
}
