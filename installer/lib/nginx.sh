#!/usr/bin/env bash
# Step 11 — Nginx: managed include, default 444 servers, panel vhost with a self-signed cert.

ED_NGINX_DIR=/etc/nginx/easydeploy

primary_ipv4() {
  ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1
}

nginx_self_signed_cert() {
  local dir=$ED_ETC/ssl/panel
  [[ -s $dir/fullchain.pem && -s $dir/privkey.pem ]] && return 0
  install -d -m 0750 -o root -g root "$dir"
  local san ip
  san="IP:127.0.0.1,DNS:localhost,DNS:$(hostname -s)"
  ip=$(primary_ipv4)
  [[ -n $ip ]] && san+=",IP:$ip"
  has_ipv6 && san+=",IP:::1"
  run openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 3650 \
    -subj "/CN=EasyDeploy panel" -addext "subjectAltName=$san" \
    -keyout "$dir/privkey.pem" -out "$dir/fullchain.pem" || die "Cannot create the panel certificate"
  chmod 0600 "$dir/privkey.pem"
  chmod 0644 "$dir/fullchain.pem"
  ok "self-signed panel certificate ($san)"
}

nginx_listen_lines() {
  local port=$1 mode=$2 lines=()
  [[ $mode == ipv4 || $mode == dual ]] && lines+=("listen $port ssl http2;")
  [[ $mode == ipv6 || $mode == dual ]] && lines+=("listen [::]:$port ssl http2;")
  local IFS=$'\n'
  printf '%s' "${lines[*]}" | sed '2,$s/^/    /'
}

nginx_render_panel() {
  local template=$ED_RELEASE_DIR/deploy/nginx/panel.conf.template out=$1 listen
  listen=$(nginx_listen_lines "$ED_PANEL_PORT" "$ED_OPT_LISTEN")
  awk -v listen="$listen" \
      -v sock="/run/easydeploy/api/api.sock" \
      -v front="$ED_ROOT/current/frontend" \
      -v cert="$ED_ETC/ssl/panel/fullchain.pem" \
      -v key="$ED_ETC/ssl/panel/privkey.pem" '
    { gsub(/@LISTEN@/, listen); gsub(/@API_SOCKET@/, sock); gsub(/@FRONTEND_DIR@/, front);
      gsub(/@SSL_CERT@/, cert); gsub(/@SSL_KEY@/, key); print }' "$template" >"$out"
}

nginx_setup() {
  nginx_self_signed_cert
  local deploy=$ED_RELEASE_DIR/deploy/nginx staging
  install -d -m 0755 "$ED_NGINX_DIR" "$ED_NGINX_DIR/sites" "$ED_NGINX_DIR/snippets" "$ED_NGINX_DIR/upstreams"
  staging=$(mktemp -d)
  cp -a "$deploy/snippets/." "$staging/"
  if has_ipv6; then cp "$deploy/default-server.conf" "$staging/default-server.conf"
  else grep -v '# ipv6$' "$deploy/default-server.conf" >"$staging/default-server.conf"; fi
  nginx_render_panel "$staging/panel.conf"

  # Transactional apply: keep the previous files, validate, roll back on failure (§2.2).
  local backup
  backup=$(mktemp -d)
  cp -a "$ED_NGINX_DIR/." "$backup/" 2>/dev/null || true
  [[ -f /etc/nginx/conf.d/easydeploy.conf ]] && cp -a /etc/nginx/conf.d/easydeploy.conf "$backup/conf.d-easydeploy.conf"
  install -m 0644 "$staging/default-server.conf" "$ED_NGINX_DIR/default-server.conf"
  install -m 0644 "$staging/panel.conf" "$ED_NGINX_DIR/panel.conf"
  install -m 0644 "$staging/acme-challenge.conf" "$ED_NGINX_DIR/snippets/acme-challenge.conf"
  install -m 0644 "$staging/panel-security-headers.conf" "$ED_NGINX_DIR/snippets/panel-security-headers.conf"
  install -m 0644 "$deploy/easydeploy.conf" /etc/nginx/conf.d/easydeploy.conf
  rm -rf "$staging"

  if ! nginx -t >>"$ED_LOG" 2>&1; then
    rm -rf "${ED_NGINX_DIR:?}"/*
    cp -a "$backup/." "$ED_NGINX_DIR/" 2>/dev/null || true
    if [[ -f $backup/conf.d-easydeploy.conf ]]; then
      mv "$backup/conf.d-easydeploy.conf" /etc/nginx/conf.d/easydeploy.conf
      rm -f "$ED_NGINX_DIR/conf.d-easydeploy.conf"
    else
      rm -f /etc/nginx/conf.d/easydeploy.conf
    fi
    rm -rf "$backup"
    die "nginx -t rejected the configuration (previous files restored): $(nginx -t 2>&1 | tail -n 2)"
  fi
  rm -rf "$backup"
  run systemctl enable nginx
  if systemctl is-active --quiet nginx; then run systemctl reload nginx; else run systemctl start nginx; fi
  ok "Nginx configured (panel on port $ED_PANEL_PORT)"
}
