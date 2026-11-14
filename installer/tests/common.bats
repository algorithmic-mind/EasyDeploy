#!/usr/bin/env bats
# Unit tests for installer helpers (run in CI: bats installer/tests). They never touch the host.

setup() {
  export ED_LOG_DIR="$BATS_TEST_TMPDIR/log"
  export ED_LOG="$ED_LOG_DIR/install.log"
  mkdir -p "$ED_LOG_DIR"
  ED_INSTALLER_DIR="$BATS_TEST_DIRNAME/.."
  # shellcheck source=../lib/common.sh
  source "$ED_INSTALLER_DIR/lib/common.sh"
  source "$ED_INSTALLER_DIR/lib/mirrors.sh"
  source "$ED_INSTALLER_DIR/lib/nginx.sh"
}

@test "valid_port accepts unprivileged ports and rejects 80/443" {
  valid_port 28443
  # `! cmd` never fails a bats test (bash ignores it under set -e), so assert explicitly.
  for bad in 80 443 1023 70000 abc; do
    if valid_port "$bad"; then echo "accepted $bad"; return 1; fi
  done
}

@test "random_string has the requested length and charset" {
  value=$(random_string 24)
  [ "${#value}" -eq 24 ]
  [[ $value =~ ^[A-Za-z0-9]+$ ]]
}

@test "version_ge compares dotted versions" {
  version_ge 27.3.1 24.0
  version_ge 24.0 24.0
  if version_ge 20.10.7 24.0; then return 1; fi
}

@test "parse_args reads options and validates them" {
  parse_args --port 30000 --username ops --listen dual --lang fa --docker-mirror https://m1 --docker-mirror https://m2 --yes
  [ "$ED_OPT_PORT" = 30000 ]
  [ "$ED_OPT_USERNAME" = ops ]
  [ "$ED_OPT_LISTEN" = dual ]
  [ "$ED_OPT_LANG" = fa ]
  [ "${#ED_OPT_DOCKER_MIRRORS[@]}" -eq 2 ]
  [ "$ED_OPT_YES" = 1 ]
}

@test "parse_args rejects a bad port and a bad entrance" {
  run parse_args --port 80
  [ "$status" -ne 0 ]
  run parse_args --entrance "../x"
  [ "$status" -ne 0 ]
  run parse_args --password short
  [ "$status" -ne 0 ]
}

@test "--from-source without a path means auto" {
  parse_args --from-source --yes
  [ "$ED_OPT_FROM_SOURCE" = auto ]
}

@test "mirror profiles load and command-line mirrors win" {
  ED_OPT_MIRROR_PROFILE=global
  ED_OPT_DOCKER_MIRRORS=(https://mirror.test)
  mirrors_load_profile
  [ "$ED_DOCKER_APT_URL" = "https://download.docker.com/linux/ubuntu" ]
  [ "${ED_REGISTRY_MIRRORS[0]}" = "https://mirror.test" ]
  [ "$ED_PYPI_INDEX" = "https://pypi.org/simple" ]
}

@test "panel template renders every placeholder" {
  ED_RELEASE_DIR="$BATS_TEST_DIRNAME/../.."
  ED_PANEL_PORT=31000
  ED_OPT_LISTEN=dual
  ED_ROOT=/opt/easydeploy
  ED_ETC=/etc/easydeploy
  out="$BATS_TEST_TMPDIR/panel.conf"
  nginx_render_panel "$out"
  if grep -q '@[A-Z_]*@' "$out"; then return 1; fi
  grep -q 'listen 31000 ssl http2;' "$out"
  grep -q 'listen \[::\]:31000 ssl http2;' "$out"
  grep -q 'server unix:/run/easydeploy/api/api.sock;' "$out"
}
