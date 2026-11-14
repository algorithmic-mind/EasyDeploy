#!/usr/bin/env bash
# Phase 0 acceptance checks (§15), run ON the test server as root after installing:
#   sudo bash scripts/vm-acceptance.sh                  full run (resets the admin password at the end)
#   sudo bash scripts/vm-acceptance.sh --after-reboot   only the post-reboot checks
# Prints PASS/FAIL per check and the idle memory of the panel stack. Inside GitHub Actions, failures
# and measurements are also emitted as annotations (readable without signing in).
set -Euo pipefail

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }
ENV=/etc/easydeploy/easydeploy.env
PORT=$(sed -n 's/^ED_PANEL_PORT=//p' "$ENV")
CA=/etc/easydeploy/ssl/panel/fullchain.pem
BASE="https://127.0.0.1:$PORT"
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT
FAILED=0
RSS_TARGET_MB=450

annotate() {  # annotate <error|warning|notice> <message>
  if [[ ${GITHUB_ACTIONS:-} == true ]]; then
    printf '::%s title=Acceptance::%s\n' "$1" "${2//$'\n'/%0A}"
  fi
}
pass() { printf '  \033[32mPASS\033[0m %s\n' "$*"; }
fail() {
  printf '  \033[31mFAIL\033[0m %s\n' "$*"
  annotate error "$*"
  FAILED=$((FAILED + 1))
}
check() { local name=$1; shift; if "$@"; then pass "$name"; else fail "$name"; fi; }

code() {  # code <method> <path> [json-body] → HTTP status
  local method=$1 path=$2 body=${3:-} csrf
  csrf=$(awk '$6 == "ed_csrftoken" {print $7}' "$JAR" | tail -n1)
  curl -s -o /dev/null -w '%{http_code}' --cacert "$CA" -b "$JAR" -c "$JAR" -X "$method" \
    -H "Origin: $BASE" -H "Referer: $BASE/" -H "X-CSRFToken: $csrf" \
    -H 'Content-Type: application/json' ${body:+--data "$body"} "$BASE$path"
}

expect() {  # expect <name> <expected-status> <method> <path> [json-body]
  local name=$1 want=$2 got
  shift 2
  got=$(code "$@")
  if [[ $got == "$want" ]]; then pass "$name"; else fail "$name (expected $want, got $got)"; fi
}

login_body() { printf '{"username":"%s","password":"%s"}' "$USERNAME" "$1"; }

INFO=$(edctl user-info --json)
USERNAME=$(printf '%s' "$INFO" | jq -r .username)
ENTRANCE=$(printf '%s' "$INFO" | jq -r '.urls[0]' | sed 's#.*/##')

echo "EasyDeploy Phase 0 acceptance — $BASE (user $USERNAME)"

echo "Services"
check "all units active" edctl status
if DOCTOR=$(edctl --lang en doctor 2>&1); then
  pass "edctl doctor"
else
  fail "edctl doctor: $(printf '%s\n' "$DOCTOR" | grep -E '✗|fix:' | tr -s ' ')"
fi
check "health endpoint over TLS (verified cert)" \
  bash -c "curl -fsS --cacert '$CA' '$BASE/api/v1/health' | grep -q ok"
check "units enabled for boot" systemctl is-enabled --quiet easydeploy.target

if [[ ${1:-} == --after-reboot ]]; then
  echo
  if [[ $FAILED -eq 0 ]]; then echo "Post-reboot checks passed."; else echo "$FAILED check(s) failed."; fi
  exit "$FAILED"
fi

echo "Security entrance"
expect "SPA hidden without entrance" 404 GET /
expect "API hidden without entrance" 404 GET /api/v1/panel/info
expect "wrong entrance answers 404" 404 GET /wrong-entrance-123
expect "correct entrance redirects" 302 GET "/$ENTRANCE"
expect "panel reachable after entrance" 200 GET /api/v1/panel/info
code GET /api/v1/auth/csrf >/dev/null

echo "Login lockout"
for i in 1 2 3 4 5; do code POST /api/v1/auth/login "$(login_body "wrong-password-$i")" >/dev/null; done
expect "6th attempt is locked" 429 POST /api/v1/auth/login "$(login_body still-wrong-1)"

echo "edctl reset-password"
NEW=$(edctl --lang en reset-password | sed -n 's/^New password (shown once): //p')
check "a new password was printed" test -n "$NEW"
# reset-password ends every session, including the one that passed the entrance.
expect "old session no longer passes the entrance" 404 GET /api/v1/panel/info
expect "entrance again" 302 GET "/$ENTRANCE"
code GET /api/v1/auth/csrf >/dev/null
expect "login with the new password works" 200 POST /api/v1/auth/login "$(login_body "$NEW")"
expect "session is authenticated" 200 GET /api/v1/auth/me
expect "diagnostics task accepted" 202 POST /api/v1/tasks/diagnostics

echo "Memory (idle RSS per unit, from the units' cgroups)"
sleep 15
TOTAL=0
REPORT=""
for unit in easydeploy-agent easydeploy-api easydeploy-worker redis-server; do
  procs="/sys/fs/cgroup/system.slice/$unit.service/cgroup.procs"
  kb=0
  pids=$(paste -sd, "$procs" 2>/dev/null || true)  # cgroup files report size 0; read them
  if [[ -n $pids ]]; then
    kb=$(ps -o rss= -p "$pids" | awk '{s += $1} END {print s + 0}')
  fi
  mb=$((kb / 1024))
  TOTAL=$((TOTAL + mb))
  REPORT+="$unit=${mb}MB "
  printf '  %-20s %5d MB\n' "$unit" "$mb"
done
printf '  %-20s %5d MB (target ≤ %d MB, Phase 6)\n' "total" "$TOTAL" "$RSS_TARGET_MB"
if ((TOTAL <= RSS_TARGET_MB)); then
  annotate notice "idle RSS ${TOTAL} MB (${REPORT% })"
else
  annotate warning "idle RSS ${TOTAL} MB exceeds the ${RSS_TARGET_MB} MB target (${REPORT% })"
fi

echo
echo "New admin password (save it): $NEW"
echo "Next: reboot the server, then run: sudo bash $(cd "$(dirname "$0")" && pwd)/vm-acceptance.sh --after-reboot"
if [[ $FAILED -eq 0 ]]; then echo "All checks passed."; else echo "$FAILED check(s) failed."; fi
exit "$FAILED"
