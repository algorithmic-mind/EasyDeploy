#!/usr/bin/env bash
# Steps 15–16 — health check and the final summary (the password is printed once, never logged).

health_check() {
  local url="https://127.0.0.1:$ED_PANEL_PORT/api/v1/health" i
  for i in $(seq 1 60); do
    if curl -fsS --max-time 3 --cacert "$ED_ETC/ssl/panel/fullchain.pem" "$url" 2>/dev/null | grep -q '"ok"'; then
      ok "panel is healthy"
      touch "$ED_ROOT/.installed"
      return 0
    fi
    sleep 1
  done
  warn "The panel did not become healthy within 60 s. Diagnostics:"
  "$ED_ROOT/current/venv/bin/edctl" doctor 2>&1 | tee -a "$ED_LOG" || true
  journalctl -u easydeploy-api -n 20 --no-pager 2>/dev/null | tee -a "$ED_LOG" || true
  die "Health check failed"
}

panel_urls() {
  local ip
  while read -r ip; do
    [[ -n $ip ]] && printf 'https://%s:%s/%s\n' "$ip" "$ED_PANEL_PORT" "$ED_ENTRANCE"
  done < <(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
  if [[ $ED_OPT_LISTEN != ipv4 ]]; then
    while read -r ip; do
      [[ -n $ip ]] && printf 'https://[%s]:%s/%s\n' "$ip" "$ED_PANEL_PORT" "$ED_ENTRANCE"
    done < <(ip -6 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
  fi
}

summary_print() {
  local line="────────────────────────────────────────────────────────────"
  printf '\n%s\n' "${C_GREEN}${line}${C_RESET}"
  printf '%s\n' "${C_BOLD}  EasyDeploy $ED_VERSION is installed${C_RESET}"
  printf '%s\n' "${C_GREEN}${line}${C_RESET}"
  local url
  while read -r url; do printf '  %-12s %s\n' "Panel URL:" "$url"; done < <(panel_urls)
  printf '  %-12s %s\n' "Username:" "$ED_OPT_USERNAME"
  if [[ -n $ED_GENERATED_PASSWORD ]]; then
    printf '  %-12s %s\n' "Password:" "${C_BOLD}${ED_GENERATED_PASSWORD}${C_RESET}"
    printf '  %s\n' "${C_YELLOW}Save this password now — it is shown only once and is not stored.${C_RESET}"
  elif [[ -n $ED_OPT_PASSWORD ]]; then
    printf '  %-12s %s\n' "Password:" "(the one you passed with --password)"
  fi
  printf '\n  %s\n' "The browser will warn about the self-signed certificate; that is expected."
  printf '  %s\n' "Next steps:"
  printf '    %s\n' "edctl user-info        # show the URL and username again" \
    "edctl reset-password   # set a new admin password" \
    "edctl doctor           # check the installation"
  printf '%s\n\n' "${C_GREEN}${line}${C_RESET}"
  ED_GENERATED_PASSWORD=""
}
