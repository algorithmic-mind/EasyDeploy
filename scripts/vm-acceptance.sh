#!/usr/bin/env bash
# Phase 0 acceptance checks (§15), run ON the test server as root after installing:
#   sudo bash scripts/vm-acceptance.sh            full run (resets the admin password at the end)
#   sudo bash scripts/vm-acceptance.sh --after-reboot   only the post-reboot checks
# Prints PASS/FAIL per check and the idle memory of the panel stack.
set -Euo pipefail

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }
ENV=/etc/easydeploy/easydeploy.env
PORT=$(sed -n 's/^ED_PANEL_PORT=//p' "$ENV")
CA=/etc/easydeploy/ssl/panel/fullchain.pem
BASE="https://127.0.0.1:$PORT"
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT
FAILED=0

pass() { printf '  \033[32mPASS\033[0m %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAILED=$((FAILED + 1)); }
check() { local name=$1; shift; if "$@"; then pass "$name"; else fail "$name"; fi; }

code() {  # code <method> <path> [json-body]
  local method=$1 path=$2 body=${3:-} csrf
  csrf=$(awk '$6 == "ed_csrftoken" {print $7}' "$JAR" | tail -n1)
  curl -s -o /dev/null -w '%{http_code}' --cacert "$CA" -b "$JAR" -c "$JAR" -X "$method" \
    -H "Origin: $BASE" -H "Referer: $BASE/" -H "X-CSRFToken: $csrf" \
    -H 'Content-Type: application/json' ${body:+--data "$body"} "$BASE$path"
}

login_code() { code POST /api/v1/auth/login "{\"username\":\"$USERNAME\",\"password\":\"$1\"}"; }

INFO=$(edctl user-info --json)
USERNAME=$(printf '%s' "$INFO" | jq -r .username)
ENTRANCE=$(printf '%s' "$INFO" | jq -r '.urls[0]' | sed 's#.*/##')

echo "EasyDeploy Phase 0 acceptance — $BASE (user $USERNAME)"

echo "Services"
check "all units active" edctl status >/dev/null
check "edctl doctor" edctl doctor >/dev/null
check "health endpoint over TLS (verified cert)" \
  bash -c "curl -fsS --cacert '$CA' '$BASE/api/v1/health' | grep -q ok"
check "units enabled for boot" systemctl is-enabled --quiet easydeploy.target

if [[ ${1:-} == --after-reboot ]]; then
  echo; [[ $FAILED -eq 0 ]] && echo "Post-reboot checks passed." || echo "$FAILED check(s) failed."
  exit "$FAILED"
fi

echo "Security entrance"
check "SPA hidden without entrance (404)" test "$(code GET /)" = 404
check "API hidden without entrance (404)" test "$(code GET /api/v1/panel/info)" = 404
check "wrong entrance answers 404" test "$(code GET /wrong-entrance-123)" = 404
check "correct entrance redirects (302)" test "$(code GET "/$ENTRANCE")" = 302
check "panel reachable after entrance" test "$(code GET /api/v1/panel/info)" = 200
code GET /api/v1/auth/csrf >/dev/null

echo "Login lockout"
for i in 1 2 3 4 5; do login_code "wrong-password-$i" >/dev/null; done
check "6th attempt is locked (429)" test "$(login_code "still-wrong-1")" = 429

echo "edctl reset-password"
NEW=$(edctl --lang en reset-password | sed -n 's/^New password (shown once): //p')
check "a new password was printed" test -n "$NEW"
code GET /api/v1/auth/csrf >/dev/null
check "login with the new password works" test "$(login_code "$NEW")" = 200
check "session is authenticated" test "$(code GET /api/v1/auth/me)" = 200
check "diagnostics task accepted (202)" test "$(code POST /api/v1/tasks/diagnostics)" = 202

echo "Memory (idle RSS of agent + api + worker + redis)"
sleep 10
# shellcheck disable=SC2009  # match full command lines, not process names
RSS=$(ps -eo rss=,args= | grep -E 'easydeploy_agent|uvicorn easydeploy|celery -A easydeploy|redis-server' \
  | grep -v grep | awk '{s += $1} END {printf "%.0f", s / 1024}')
if ((RSS <= 450)); then pass "idle RSS ${RSS} MB (target ≤ 450 MB)"; else fail "idle RSS ${RSS} MB (target ≤ 450 MB)"; fi

echo
echo "New admin password (save it): $NEW"
echo "Next: reboot the server, then run: sudo bash $(cd "$(dirname "$0")" && pwd)/vm-acceptance.sh --after-reboot"
[[ $FAILED -eq 0 ]] && echo "All checks passed." || echo "$FAILED check(s) failed."
exit "$FAILED"
