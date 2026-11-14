#!/usr/bin/env bash
# Shared helpers for the EasyDeploy installer: options, logging, steps, small utilities.
# shellcheck disable=SC2034  # variables are used by the other lib/*.sh files

ED_ROOT=${ED_ROOT:-/opt/easydeploy}
ED_ETC=${ED_ETC:-/etc/easydeploy}
ED_LOG_DIR=${ED_LOG_DIR:-/var/log/easydeploy}
ED_LOG=${ED_LOG:-$ED_LOG_DIR/install.log}
ED_USER=easydeploy
ED_NETWORK=easydeploy-net

# ------------------------------------------------------------------ options (§8.1; ED_* env vars)
ED_OPT_VERSION=${ED_VERSION:-}
ED_OPT_CHANNEL=${ED_CHANNEL:-stable}
ED_OPT_PORT=${ED_PORT:-}
ED_OPT_ENTRANCE=${ED_ENTRANCE:-}
ED_OPT_USERNAME=${ED_USERNAME:-admin}
ED_OPT_PASSWORD=${ED_PASSWORD:-}
ED_OPT_LISTEN=${ED_LISTEN:-ipv4}
ED_OPT_LANG=${ED_LANG:-en}
ED_OPT_MIRROR_PROFILE=${ED_MIRROR_PROFILE:-global}
ED_OPT_APT_MIRROR=${ED_APT_MIRROR:-}
ED_OPT_PYPI_INDEX=${ED_PYPI_INDEX:-}
ED_OPT_DOCKER_MIRRORS=()
ED_OPT_RELEASE_URL=${ED_RELEASE_URL:-}
ED_OPT_RELEASE_FILE=${ED_RELEASE_FILE:-}
ED_OPT_OFFLINE_BUNDLE=${ED_OFFLINE_BUNDLE:-}
ED_OPT_FROM_SOURCE=${ED_FROM_SOURCE:-}
ED_OPT_SKIP_DOCKER=${ED_SKIP_DOCKER_INSTALL:-0}
ED_OPT_NO_FIREWALL=${ED_NO_FIREWALL:-0}
ED_OPT_YES=${ED_YES:-0}
ED_OPT_DRY_RUN=${ED_DRY_RUN:-0}
ED_OPT_VERBOSE=${ED_VERBOSE:-0}
ED_OPT_REINSTALL=${ED_REINSTALL:-0}
ED_OPT_ALLOW_ONLINE_WHEELS=${ED_ALLOW_ONLINE_WHEELS:-0}

ED_CURRENT_STEP="init"
ED_GENERATED_PASSWORD=""

usage() {
  cat <<'EOF'
EasyDeploy installer

Usage: sudo bash install.sh [options]

  --version <ver>            Release version (default: latest of the channel)
  --channel stable|beta      Release channel (default: stable)
  --port <port>              Panel HTTPS port (default: random 10000-60000)
  --entrance <path>          Security entrance (default: random 12 characters)
  --username <name>          Admin username (default: admin)
  --password <password>      Admin password (default: generated, printed once)
  --listen ipv4|ipv6|dual    Panel listen addresses (default: ipv4)
  --lang en|fa               Panel default language (default: en)
  --mirror-profile <name>    global | ir | custom (default: global)
  --apt-mirror <url>         Ubuntu archive mirror
  --pypi-index <url>         Python package index (fallback / source installs)
  --docker-mirror <url>      Docker registry mirror (repeatable)
  --release-url <url>        Base URL for releases
  --release-file <path>      Install from a local release tarball
  --offline-bundle <path>    Install from an offline bundle (Phase 6)
  --from-source [<path>]     Install from a source checkout (development only)
  --skip-docker-install      Do not install Docker (it must already be present)
  --no-firewall              Do not touch UFW
  --reinstall                Allow running over an existing installation
  --yes                      Non-interactive: accept defaults
  --dry-run                  Run the preflight checks only
  --verbose                  Show command output
  -h, --help                 This help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version) ED_OPT_VERSION=$2; shift 2 ;;
      --channel) ED_OPT_CHANNEL=$2; shift 2 ;;
      --port) ED_OPT_PORT=$2; shift 2 ;;
      --entrance) ED_OPT_ENTRANCE=$2; shift 2 ;;
      --username) ED_OPT_USERNAME=$2; shift 2 ;;
      --password) ED_OPT_PASSWORD=$2; shift 2 ;;
      --listen) ED_OPT_LISTEN=$2; shift 2 ;;
      --lang) ED_OPT_LANG=$2; shift 2 ;;
      --mirror-profile) ED_OPT_MIRROR_PROFILE=$2; shift 2 ;;
      --apt-mirror) ED_OPT_APT_MIRROR=$2; shift 2 ;;
      --pypi-index) ED_OPT_PYPI_INDEX=$2; shift 2 ;;
      --docker-mirror) ED_OPT_DOCKER_MIRRORS+=("$2"); shift 2 ;;
      --release-url) ED_OPT_RELEASE_URL=$2; shift 2 ;;
      --release-file) ED_OPT_RELEASE_FILE=$2; shift 2 ;;
      --offline-bundle) ED_OPT_OFFLINE_BUNDLE=$2; shift 2 ;;
      --from-source)
        if [[ $# -gt 1 && $2 != --* ]]; then ED_OPT_FROM_SOURCE=$2; shift 2
        else ED_OPT_FROM_SOURCE=auto; shift; fi ;;
      --skip-docker-install) ED_OPT_SKIP_DOCKER=1; shift ;;
      --no-firewall) ED_OPT_NO_FIREWALL=1; shift ;;
      --reinstall) ED_OPT_REINSTALL=1; shift ;;
      --allow-online-wheels) ED_OPT_ALLOW_ONLINE_WHEELS=1; shift ;;
      --yes|-y) ED_OPT_YES=1; shift ;;
      --dry-run) ED_OPT_DRY_RUN=1; shift ;;
      --verbose|-v) ED_OPT_VERBOSE=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1 (see --help)" ;;
    esac
  done
  validate_args
}

validate_args() {
  if [[ -n $ED_OPT_PORT ]] && ! valid_port "$ED_OPT_PORT"; then
    die "--port must be 1024-65535 and not 80/443"
  fi
  if [[ -n $ED_OPT_ENTRANCE && ! $ED_OPT_ENTRANCE =~ ^[A-Za-z0-9]{6,64}$ ]]; then
    die "--entrance must be 6-64 letters or digits"
  fi
  [[ $ED_OPT_USERNAME =~ ^[A-Za-z0-9._@+-]{1,150}$ ]] || die "--username contains invalid characters"
  if [[ -n $ED_OPT_PASSWORD && ${#ED_OPT_PASSWORD} -lt 12 ]]; then
    die "--password must have at least 12 characters"
  fi
  case $ED_OPT_LISTEN in ipv4|ipv6|dual) ;; *) die "--listen must be ipv4, ipv6 or dual" ;; esac
  case $ED_OPT_LANG in en|fa) ;; *) die "--lang must be en or fa" ;; esac
  case $ED_OPT_CHANNEL in stable|beta) ;; *) die "--channel must be stable or beta" ;; esac
  [[ $ED_OPT_MIRROR_PROFILE =~ ^[a-z0-9_-]+$ ]] || die "invalid --mirror-profile"
}

# ------------------------------------------------------------------ logging
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi

init_logging() {
  mkdir -p "$ED_LOG_DIR"
  chmod 0750 "$ED_LOG_DIR"
  touch "$ED_LOG"
  chmod 0640 "$ED_LOG"
  printf '\n===== EasyDeploy install %s =====\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$ED_LOG"
}

_log() {
  local level=$1; shift
  printf '%s [%s] [%s] %s\n' "$(date -u +%H:%M:%S)" "$level" "$ED_CURRENT_STEP" "$*" \
    >>"$ED_LOG" 2>/dev/null || true
}

info() { _log INFO "$*"; printf '%s\n' "  $*"; }
ok() { _log OK "$*"; printf '%s\n' "  ${C_GREEN}✓${C_RESET} $*"; }
warn() { _log WARN "$*"; printf '%s\n' "  ${C_YELLOW}!${C_RESET} $*" >&2; }
die() {
  _log ERROR "$*"
  printf '%s\n' "${C_RED}✗ $*${C_RESET}" >&2
  exit 1
}

# Run a command; output goes to the log (and the terminal with --verbose).
run() {
  _log CMD "$*"
  if [[ $ED_OPT_VERBOSE == 1 ]]; then
    "$@" 2>&1 | tee -a "$ED_LOG"
    return "${PIPESTATUS[0]}"
  fi
  "$@" >>"$ED_LOG" 2>&1
}

on_error() {
  local code=$1 line=$2
  _log ERROR "step '$ED_CURRENT_STEP' failed (exit $code, line $line)"
  printf '\n%s\n' "${C_RED}✗ Installation failed in step '${ED_CURRENT_STEP}' (exit ${code}).${C_RESET}" >&2
  printf '%s\n' "  Details: $ED_LOG (last lines below)" >&2
  tail -n 15 "$ED_LOG" 2>/dev/null | sed 's/^/    /' >&2 || true
  printf '%s\n' "  The installer is idempotent: fix the problem and run it again." >&2
}

run_step() {
  local name=$1 fn=$2
  ED_CURRENT_STEP=$name
  printf '%s\n' "${C_BOLD}${C_BLUE}==>${C_RESET} ${C_BOLD}${name}${C_RESET}"
  _log STEP "begin $name"
  "$fn"
  _log STEP "end $name"
}

confirm() {
  local prompt=$1
  if [[ $ED_OPT_YES == 1 ]]; then return 0; fi
  if [[ ! -t 0 ]]; then return 1; fi
  local answer
  read -r -p "  $prompt [y/N] " answer
  [[ $answer =~ ^[Yy] ]]
}

# ------------------------------------------------------------------ utilities
valid_port() {
  local p=$1
  [[ $p =~ ^[0-9]+$ ]] && ((p >= 1024 && p <= 65535 && p != 80 && p != 443))
}

random_string() {
  local length=${1:-16}
  local out=""
  while [[ ${#out} -lt $length ]]; do
    out+=$(head -c 256 /dev/urandom | tr -dc 'A-Za-z0-9')
  done
  printf '%s' "${out:0:length}"
}

port_in_use() {
  ss -Htln "sport = :$1" 2>/dev/null | grep -q .
}

port_owner() {
  ss -Htlnp "sport = :$1" 2>/dev/null | sed -n 's/.*users:(("\([^"]*\)".*/\1/p' | head -n1
}

# version_ge A B: true if A >= B (dotted numeric versions)
version_ge() {
  [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

# Write a file atomically with mode and owner.
install_file() {
  local src=$1 dest=$2 mode=${3:-0644} owner=${4:-root:root}
  install -D -m "$mode" -o "${owner%%:*}" -g "${owner##*:}" "$src" "$dest"
}

has_ipv6() {
  [[ -f /proc/net/if_inet6 ]] && [[ -s /proc/net/if_inet6 ]]
}
