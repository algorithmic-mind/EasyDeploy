#!/usr/bin/env bash
# Step 4 — Docker Engine CE + Compose v2 (§8.2, ADR-0012).

ED_DOCKER_MIN_VERSION=24.0

docker_present() {
  command -v docker >/dev/null 2>&1 || return 1
  local version
  version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
  [[ -n $version ]] || return 1
  version_ge "$version" "$ED_DOCKER_MIN_VERSION" || return 1
  docker compose version >/dev/null 2>&1
}

docker_install() {
  local keyring=/etc/apt/keyrings/docker.asc
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -s $keyring ]]; then
    run curl -fsSL --retry 3 "$ED_DOCKER_GPG_URL" -o "$keyring" || die "Cannot download Docker GPG key from $ED_DOCKER_GPG_URL"
    chmod a+r "$keyring"
  fi
  local codename=${ED_OS_CODENAME}
  printf 'deb [arch=%s signed-by=%s] %s %s stable\n' "$ED_ARCH" "$keyring" "$ED_DOCKER_APT_URL" "$codename" \
    >/etc/apt/sources.list.d/docker.list
  run apt-get update -q || die "apt-get update failed for the Docker repository"
  run apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    || die "Docker installation failed"
}

# Merge EasyDeploy defaults into daemon.json without dropping the admin's own keys.
docker_configure_daemon() {
  local file=/etc/docker/daemon.json tmp mirrors_json
  mkdir -p /etc/docker
  [[ -s $file ]] || echo '{}' >"$file"
  if [[ ${#ED_REGISTRY_MIRRORS[@]} -gt 0 ]]; then
    mirrors_json=$(printf '%s\n' "${ED_REGISTRY_MIRRORS[@]}" | jq -R . | jq -s .)
  else
    mirrors_json=null
  fi
  tmp=$(mktemp)
  jq --argjson mirrors "$mirrors_json" '
      .["log-driver"] = (.["log-driver"] // "json-file")
    | .["log-opts"] = ((.["log-opts"] // {}) + {"max-size": "20m", "max-file": "3"})
    | .["live-restore"] = true
    | if $mirrors != null then .["registry-mirrors"] = $mirrors else . end
  ' "$file" >"$tmp" || { rm -f "$tmp"; die "Invalid JSON in $file"; }
  if ! cmp -s "$tmp" "$file"; then
    cp -a "$file" "$file.easydeploy.bak"
    install -m 0644 "$tmp" "$file"
    run systemctl restart docker || die "Docker failed to restart with the new daemon.json"
    ok "updated $file"
  fi
  rm -f "$tmp"
}

docker_setup() {
  if docker_present; then
    ok "Docker $(docker version --format '{{.Server.Version}}') with Compose v2 found"
  elif [[ $ED_OPT_SKIP_DOCKER == 1 ]]; then
    die "Docker >= $ED_DOCKER_MIN_VERSION with Compose v2 is required (--skip-docker-install was given)"
  else
    info "installing Docker CE"
    docker_install
    ok "Docker installed"
  fi
  run systemctl enable --now docker
  docker_configure_daemon
  if ! docker network inspect "$ED_NETWORK" >/dev/null 2>&1; then
    run docker network create --label io.easydeploy.managed=true "$ED_NETWORK" \
      || die "Cannot create Docker network $ED_NETWORK"
  fi
  ok "Docker network $ED_NETWORK"
}
