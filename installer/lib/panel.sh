#!/usr/bin/env bash
# Steps 5, 7–10 — release files, users & directories, config & secrets, Redis, database, lego.

# ------------------------------------------------------------------ step 5: release
# Sets ED_MODE (release|source), ED_SOURCE_DIR, ED_VERSION, ED_RELEASE_DIR.
release_detect() {
  local here=$ED_INSTALLER_DIR/..
  if [[ -n $ED_OPT_OFFLINE_BUNDLE ]]; then
    die "Offline bundles arrive with signed releases (Phase 6)"
  fi
  if [[ -n $ED_OPT_RELEASE_FILE ]]; then
    [[ -f $ED_OPT_RELEASE_FILE ]] || die "Release file not found: $ED_OPT_RELEASE_FILE"
    ED_MODE=release
    ED_SOURCE_DIR=$ED_ROOT/tmp/release-extract
  elif [[ -n $ED_OPT_FROM_SOURCE ]]; then
    ED_MODE=source
    if [[ $ED_OPT_FROM_SOURCE == auto ]]; then ED_SOURCE_DIR=$(cd "$here" && pwd)
    else ED_SOURCE_DIR=$(cd "$ED_OPT_FROM_SOURCE" && pwd); fi
    [[ -f $ED_SOURCE_DIR/backend/manage.py ]] || die "$ED_SOURCE_DIR is not an EasyDeploy source checkout"
  elif [[ -f $here/VERSION && -d $here/wheels ]]; then
    ED_MODE=release  # running from an extracted release tarball
    ED_SOURCE_DIR=$(cd "$here" && pwd)
  else
    die "No release to install. Use --release-file <tarball> or --from-source (online downloads of signed releases arrive in Phase 6)."
  fi
}

release_place() {
  if [[ -n $ED_OPT_RELEASE_FILE ]]; then
    local sums
    sums="$(dirname "$ED_OPT_RELEASE_FILE")/SHA256SUMS"
    if [[ -f $sums ]]; then
      (cd "$(dirname "$ED_OPT_RELEASE_FILE")" && sha256sum --ignore-missing -c SHA256SUMS) >>"$ED_LOG" 2>&1 \
        || die "Checksum verification of $(basename "$ED_OPT_RELEASE_FILE") failed"
      ok "checksum verified"
    else
      warn "No SHA256SUMS next to the release file; signature verification arrives in Phase 6"
    fi
    rm -rf "$ED_SOURCE_DIR"
    mkdir -p "$ED_SOURCE_DIR"
    run tar -xzf "$ED_OPT_RELEASE_FILE" -C "$ED_SOURCE_DIR" --strip-components=1 --no-same-owner \
      || die "Cannot extract $ED_OPT_RELEASE_FILE"
  fi

  if [[ -n $ED_OPT_VERSION ]]; then ED_VERSION=$ED_OPT_VERSION
  elif [[ -f $ED_SOURCE_DIR/VERSION ]]; then ED_VERSION=$(tr -d '[:space:]' <"$ED_SOURCE_DIR/VERSION")
  else ED_VERSION="0.1.0-dev.$(date -u +%Y%m%d%H%M)"; fi
  [[ $ED_VERSION =~ ^[0-9A-Za-z.+_-]+$ ]] || die "Invalid version string: $ED_VERSION"

  ED_RELEASE_DIR=$ED_ROOT/releases/$ED_VERSION
  mkdir -p "$ED_RELEASE_DIR" "$ED_ROOT/tmp"
  if [[ $ED_MODE == source ]]; then
    mkdir -p "$ED_RELEASE_DIR/app"
    local item
    for item in backend agent cli pyproject.toml uv.lock; do
      [[ -e $ED_SOURCE_DIR/$item ]] || die "Missing $item in $ED_SOURCE_DIR"
      rm -rf "${ED_RELEASE_DIR:?}/app/$item"
      cp -a "$ED_SOURCE_DIR/$item" "$ED_RELEASE_DIR/app/$item"
    done
    find "$ED_RELEASE_DIR/app" -name '__pycache__' -type d -prune -exec rm -rf {} +
    find "$ED_RELEASE_DIR/app" \( -name '*.db' -o -name '.venv' \) -prune -exec rm -rf {} +
    rm -rf "$ED_RELEASE_DIR/deploy" "$ED_RELEASE_DIR/installer" "$ED_RELEASE_DIR/frontend"
    cp -a "$ED_SOURCE_DIR/deploy" "$ED_SOURCE_DIR/installer" "$ED_RELEASE_DIR/"
    if [[ -f $ED_SOURCE_DIR/frontend/dist/index.html ]]; then
      cp -a "$ED_SOURCE_DIR/frontend/dist" "$ED_RELEASE_DIR/frontend"
    else
      warn "frontend/dist is missing: build it first (cd frontend && npm run build); the API still works"
      mkdir -p "$ED_RELEASE_DIR/frontend"
    fi
  else
    local item
    for item in app deploy installer frontend; do
      rm -rf "${ED_RELEASE_DIR:?}/$item"
      cp -a "$ED_SOURCE_DIR/$item" "$ED_RELEASE_DIR/$item"
    done
  fi
  printf '%s\n' "$ED_VERSION" >"$ED_RELEASE_DIR/VERSION"
  ok "release $ED_VERSION ($ED_MODE) in $ED_RELEASE_DIR"
}

# ------------------------------------------------------------------ step 7: users & directories
users_and_dirs() {
  if ! getent group "$ED_USER" >/dev/null; then run groupadd --system "$ED_USER"; fi
  if ! id -u "$ED_USER" >/dev/null 2>&1; then
    run useradd --system --gid "$ED_USER" --home-dir "$ED_ROOT" --no-create-home \
      --shell /usr/sbin/nologin "$ED_USER"
  fi
  # The API/worker reach Redis through its Unix socket (group redis).
  getent group redis >/dev/null && run usermod -aG redis "$ED_USER"

  install -d -m 0755 -o root -g root "$ED_ROOT" "$ED_ROOT/releases" "$ED_ROOT/venvs"
  install -d -m 0750 -o "$ED_USER" -g "$ED_USER" "$ED_ROOT/data" "$ED_ROOT/logs" \
    "$ED_ROOT/logs/tasks" "$ED_ROOT/logs/deploys" "$ED_ROOT/tmp" "$ED_ROOT/backups" \
    "$ED_ROOT/backups/panel"
  install -d -m 0755 -o root -g root "$ED_ROOT/apps" "$ED_ROOT/projects" "$ED_ROOT/www" \
    "$ED_ROOT/catalog" "$ED_ROOT/acme" "$ED_ROOT/backups/local"
  install -d -m 0750 -o root -g "$ED_USER" "$ED_ETC" "$ED_ETC/secrets"
  install -d -m 0750 -o root -g root "$ED_ETC/ssl" "$ED_LOG_DIR"
  ok "user '$ED_USER' and directories"
}

# ------------------------------------------------------------------ step 8: config & secrets
write_secret() {
  local name=$1 value=$2 file=$ED_ETC/secrets/$1
  [[ -s $file ]] && return 0
  (umask 0137 && printf '%s\n' "$value" >"$file")
  chown root:"$ED_USER" "$file"
  chmod 0640 "$file"
}

choose_panel_port() {
  local port
  if [[ -n $ED_OPT_PORT ]]; then printf '%s' "$ED_OPT_PORT"; return; fi
  local existing
  existing=$(sed -n 's/^ED_PANEL_PORT=//p' "$ED_ETC/easydeploy.env" 2>/dev/null || true)
  if [[ -n $existing ]]; then printf '%s' "$existing"; return; fi
  for _ in $(seq 1 50); do
    port=$((10000 + RANDOM % 50000))
    port_in_use "$port" || { printf '%s' "$port"; return; }
  done
  die "Could not find a free panel port"
}

config_and_secrets() {
  write_secret django.secret "$(random_string 64)"
  write_secret fernet.keys "$(head -c 32 /dev/urandom | base64 | tr '+/' '-_')"
  write_secret agent.token "$(random_string 48)"
  write_secret redis.password "$(random_string 40)"

  ED_PANEL_PORT=$(choose_panel_port)
  local env=$ED_ETC/easydeploy.env tmp
  tmp=$(mktemp)
  cat >"$tmp" <<EOF
# EasyDeploy bootstrap configuration (generated by the installer, §5.5).
# Runtime settings are edited in the panel; secrets live in $ED_ETC/secrets/.
ED_VERSION=$ED_VERSION
ED_DATA_DIR=$ED_ROOT/data
ED_LOG_DIR=$ED_ROOT/logs
ED_TMP_DIR=$ED_ROOT/tmp
ED_SECRETS_DIR=$ED_ETC/secrets
ED_FRONTEND_DIR=$ED_ROOT/current/frontend
ED_REDIS_SOCKET=/run/redis/redis-server.sock
ED_AGENT_SOCKET=/run/easydeploy/agent/agent.sock
ED_PANEL_PORT=$ED_PANEL_PORT
ED_PANEL_LISTEN=$ED_OPT_LISTEN
ED_LOG_LEVEL=info
ED_MIRROR_PROFILE=$ED_OPT_MIRROR_PROFILE
EOF
  install -m 0640 -o root -g "$ED_USER" "$tmp" "$env"
  rm -f "$tmp"
  ok "configuration $env (panel port $ED_PANEL_PORT)"
}

# ------------------------------------------------------------------ Redis (ADR-0008)
redis_configure() {
  local conf=/etc/redis/redis.conf extra=/etc/redis/easydeploy.conf tmp
  [[ -f $conf ]] || die "$conf not found (redis-server not installed?)"
  tmp=$(mktemp)
  cat "$ED_RELEASE_DIR/deploy/redis/easydeploy.conf" >"$tmp"
  printf 'requirepass %s\n' "$(cat "$ED_ETC/secrets/redis.password")" >>"$tmp"
  install -m 0640 -o redis -g redis "$tmp" "$extra"
  rm -f "$tmp"
  grep -qxF "include $extra" "$conf" || printf '\ninclude %s\n' "$extra" >>"$conf"
  run systemctl enable redis-server
  run systemctl restart redis-server || die "redis-server failed to start with the EasyDeploy config"
  local i
  for i in $(seq 1 20); do
    [[ -S /run/redis/redis-server.sock ]] && break
    sleep 0.5
  done
  [[ -S /run/redis/redis-server.sock ]] || die "Redis socket did not appear"
  ok "Redis on a password-protected Unix socket"
}

# ------------------------------------------------------------------ step 9: database
manage() {
  runuser -u "$ED_USER" -- env DJANGO_SETTINGS_MODULE=easydeploy.settings.prod \
    "$ED_ROOT/venvs/$ED_VERSION/bin/python" "$ED_RELEASE_DIR/app/backend/manage.py" "$@"
}

database_setup() {
  ln -sfn "$ED_RELEASE_DIR" "$ED_ROOT/current"
  manage migrate --noinput --database default >>"$ED_LOG" 2>&1 || die "Database migration failed"
  manage migrate --noinput --database monitor >>"$ED_LOG" 2>&1 || die "Monitor database migration failed"
  chmod 0640 "$ED_ROOT"/data/*.db 2>/dev/null || true
  ok "databases migrated"

  if manage ed_create_admin --if-missing --username "$ED_OPT_USERNAME" --password-stdin \
    </dev/null 2>/dev/null | grep -q "admin exists"; then
    ok "admin user exists (password unchanged)"
  elif [[ -n $ED_OPT_PASSWORD ]]; then
    printf '%s\n' "$ED_OPT_PASSWORD" | manage ed_create_admin --username "$ED_OPT_USERNAME" \
      --language "$ED_OPT_LANG" --password-stdin >>"$ED_LOG" 2>&1 || die "Cannot create the admin (password policy?)"
    ok "admin '$ED_OPT_USERNAME' created"
  else
    # The generated password is captured, never logged, and printed once in the summary.
    ED_GENERATED_PASSWORD=$(manage ed_create_admin --username "$ED_OPT_USERNAME" --language "$ED_OPT_LANG" 2>>"$ED_LOG") \
      || die "Cannot create the admin user"
    ok "admin '$ED_OPT_USERNAME' created"
  fi

  local entrance
  entrance=$(manage ed_setting get security.entrance 2>>"$ED_LOG" | tr -d '"')
  if [[ -z $entrance || -n $ED_OPT_ENTRANCE ]]; then
    entrance=${ED_OPT_ENTRANCE:-$(random_string 12)}
    manage ed_setting set security.entrance "$entrance" >>"$ED_LOG" 2>&1 || die "Cannot set the entrance"
  fi
  ED_ENTRANCE=$entrance
  manage ed_setting set panel.default_language "$ED_OPT_LANG" >>"$ED_LOG" 2>&1 || true
  ok "security entrance configured"
}

# ------------------------------------------------------------------ step 10: lego
lego_install() {
  if [[ -x $ED_SOURCE_DIR/bin/lego ]]; then
    if [[ -f $ED_SOURCE_DIR/bin/lego.sha256 ]]; then
      (cd "$ED_SOURCE_DIR/bin" && sha256sum -c lego.sha256) >>"$ED_LOG" 2>&1 || die "lego checksum mismatch"
    fi
    install -m 0755 "$ED_SOURCE_DIR/bin/lego" /usr/local/bin/lego
    ok "lego $(/usr/local/bin/lego --version 2>/dev/null | awk '{print $3}')"
  else
    warn "lego is not bundled with this build; certificates (Phase 2) need it"
  fi
}
