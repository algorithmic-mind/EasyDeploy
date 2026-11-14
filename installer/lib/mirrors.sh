#!/usr/bin/env bash
# Step 2 — mirror profiles (§11). Mirror URLs live only in installer/mirrors/<profile>.env.

ED_DOCKER_APT_URL=""
ED_DOCKER_GPG_URL=""
ED_REGISTRY_MIRRORS=()
ED_PYPI_INDEX=""
ED_PYTHON_DOWNLOAD_MIRROR=""

mirrors_load_profile() {
  local profile_file="$ED_INSTALLER_DIR/mirrors/${ED_OPT_MIRROR_PROFILE}.env"
  [[ -f $profile_file ]] || die "Mirror profile '$ED_OPT_MIRROR_PROFILE' not found ($profile_file)"
  # Profiles are simple KEY=value files maintained by the owner.
  local key value
  while IFS='=' read -r key value; do
    [[ -z $key || $key == \#* ]] && continue
    value=${value%\"}; value=${value#\"}
    case $key in
      APT_MIRROR) [[ -z $ED_OPT_APT_MIRROR ]] && ED_OPT_APT_MIRROR=$value ;;
      DOCKER_APT_URL) ED_DOCKER_APT_URL=$value ;;
      DOCKER_GPG_URL) ED_DOCKER_GPG_URL=$value ;;
      REGISTRY_MIRRORS) [[ -n $value ]] && read -r -a ED_REGISTRY_MIRRORS <<<"${value//,/ }" ;;
      PYPI_INDEX) [[ -z $ED_OPT_PYPI_INDEX ]] && ED_OPT_PYPI_INDEX=$value ;;
      PYTHON_DOWNLOAD_MIRROR) ED_PYTHON_DOWNLOAD_MIRROR=$value ;;
      RELEASE_URL) [[ -z $ED_OPT_RELEASE_URL ]] && ED_OPT_RELEASE_URL=$value ;;
    esac
  done <"$profile_file"
  if [[ ${#ED_OPT_DOCKER_MIRRORS[@]} -gt 0 ]]; then
    ED_REGISTRY_MIRRORS=("${ED_OPT_DOCKER_MIRRORS[@]}")
  fi
  ED_PYPI_INDEX=$ED_OPT_PYPI_INDEX
}

mirrors_check() {
  local url
  for url in "$@"; do
    [[ -z $url ]] && continue
    if curl -fsS --max-time 10 -o /dev/null -I "$url" 2>/dev/null \
      || curl -fsS --max-time 10 -o /dev/null "$url" 2>/dev/null; then
      ok "reachable: $url"
    else
      warn "not reachable: $url"
    fi
  done
}

mirrors_apply_apt() {
  [[ -z $ED_OPT_APT_MIRROR ]] && return 0
  local sources=/etc/apt/sources.list.d/ubuntu.sources
  if [[ -f $sources ]]; then
    [[ -f $sources.easydeploy.bak ]] || cp -a "$sources" "$sources.easydeploy.bak"
    sed -i -E "s#^URIs: .*#URIs: ${ED_OPT_APT_MIRROR}#" "$sources"
  elif [[ -f /etc/apt/sources.list ]]; then
    [[ -f /etc/apt/sources.list.easydeploy.bak ]] || cp -a /etc/apt/sources.list /etc/apt/sources.list.easydeploy.bak
    sed -i -E "s#https?://[^ ]*(archive|ports|security)\.ubuntu\.com/ubuntu(-ports)?/?#${ED_OPT_APT_MIRROR}#g" /etc/apt/sources.list
  fi
  ok "apt mirror: $ED_OPT_APT_MIRROR"
}

mirrors_apply() {
  mirrors_load_profile
  info "mirror profile: $ED_OPT_MIRROR_PROFILE"
  mirrors_apply_apt
  local checks=("$ED_OPT_APT_MIRROR" "$ED_DOCKER_APT_URL" "$ED_PYPI_INDEX")
  [[ ${#ED_REGISTRY_MIRRORS[@]} -gt 0 ]] && checks+=("${ED_REGISTRY_MIRRORS[@]}")
  mirrors_check "${checks[@]}"
}
