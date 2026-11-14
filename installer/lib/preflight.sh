#!/usr/bin/env bash
# Step 1 — preflight checks (§8.2).

ED_SUPPORTED_UBUNTU=("22.04" "24.04" "26.04")
ED_MIN_RAM_MB=900
ED_MIN_DISK_GB=10

preflight_run() {
  [[ $EUID -eq 0 ]] || die "Run as root (sudo bash install.sh)"

  [[ -r /etc/os-release ]] || die "/etc/os-release not found"
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ ${ID:-} == ubuntu ]] || die "Unsupported OS '${ID:-?}'. EasyDeploy supports Ubuntu ${ED_SUPPORTED_UBUNTU[*]}"
  local supported=0 v
  for v in "${ED_SUPPORTED_UBUNTU[@]}"; do [[ ${VERSION_ID:-} == "$v" ]] && supported=1; done
  [[ $supported == 1 ]] || die "Unsupported Ubuntu ${VERSION_ID:-?}; supported: ${ED_SUPPORTED_UBUNTU[*]}"
  ED_OS_VERSION=$VERSION_ID
  ED_OS_CODENAME=${VERSION_CODENAME:-}
  ok "Ubuntu $ED_OS_VERSION ($ED_OS_CODENAME)"

  case "$(uname -m)" in
    x86_64) ED_ARCH=amd64 ;;
    aarch64) ED_ARCH=arm64 ;;
    *) die "Unsupported architecture $(uname -m); amd64 and arm64 are supported" ;;
  esac
  ok "architecture $ED_ARCH"

  [[ "$(ps -p 1 -o comm= 2>/dev/null)" == systemd ]] || die "systemd must be PID 1"

  local mem_mb
  mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  ((mem_mb >= ED_MIN_RAM_MB)) || die "At least 1 GB RAM is required (found ${mem_mb} MB)"
  if ((mem_mb < 1900)); then warn "Less than 2 GB RAM (${mem_mb} MB): consider adding swap"; else ok "RAM ${mem_mb} MB"; fi

  local disk_gb
  disk_gb=$(df -BG --output=avail /opt 2>/dev/null | tail -n1 | tr -dc '0-9')
  ((${disk_gb:-0} >= ED_MIN_DISK_GB)) || die "At least ${ED_MIN_DISK_GB} GB free disk is required on /opt (found ${disk_gb:-0} GB)"
  ok "free disk ${disk_gb} GB"

  local virt
  virt=$(systemd-detect-virt 2>/dev/null || true)
  case $virt in
    openvz|lxc|lxc-libvirt) warn "Container virtualization ($virt): Docker needs nesting enabled" ;;
    "") ;;
    *) ok "virtualization: $virt" ;;
  esac

  if [[ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" != yes ]]; then
    warn "System clock is not NTP-synchronized (certificates and 2FA codes need correct time)"
  else
    ok "clock synchronized"
  fi

  preflight_ports
  preflight_existing

  # Reachability of configured sources is reported by the mirrors step.
}

preflight_ports() {
  local port owner
  for port in 80 443; do
    if port_in_use "$port"; then
      owner=$(port_owner "$port")
      if [[ $owner == nginx ]]; then
        ok "port $port is used by nginx (will be configured)"
        continue
      fi
      warn "Port $port is in use by '${owner:-unknown}'"
      if [[ -n $owner ]] && confirm "Stop and disable ${owner} so EasyDeploy can use port ${port}?"; then
        run systemctl disable --now "$owner" || die "Could not stop $owner"
      else
        die "Free port $port (e.g. systemctl disable --now ${owner:-<service>}) and run again"
      fi
    fi
  done
  if [[ -n $ED_OPT_PORT ]] && port_in_use "$ED_OPT_PORT"; then
    die "Panel port $ED_OPT_PORT is already in use by '$(port_owner "$ED_OPT_PORT")'"
  fi
}

preflight_existing() {
  if [[ -f $ED_ROOT/.installed ]]; then
    if [[ $ED_OPT_REINSTALL == 1 ]]; then
      warn "Existing installation found; continuing because --reinstall was given"
    else
      die "EasyDeploy is already installed. Use 'edctl update' (or upgrade.sh) instead, or pass --reinstall"
    fi
  fi
}
