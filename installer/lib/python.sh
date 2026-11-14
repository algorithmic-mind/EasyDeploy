#!/usr/bin/env bash
# Step 6 — Python runtime and the release virtualenv (ADR-0003).
#
# Release tarball: bundled CPython (python/) + wheelhouse (wheels/), installed with --no-index.
# Source install (development): uv installs CPython 3.12 (hash-verified download) and the locked
# dependencies from uv.lock.

ED_UV_VERSION=0.13.8

python_setup() {
  local venv="$ED_ROOT/venvs/$ED_VERSION"
  if [[ -x $venv/bin/python && -x $venv/bin/edctl && $ED_OPT_REINSTALL != 1 ]]; then
    ok "virtualenv $venv exists"
  elif [[ $ED_MODE == release ]]; then
    python_from_release "$venv"
  else
    python_from_source "$venv"
  fi
  ln -sfn "$venv" "$ED_RELEASE_DIR/venv"
  "$venv/bin/python" -c 'import django, easydeploy_agent, edctl' >>"$ED_LOG" 2>&1 \
    || die "The virtualenv is incomplete (see $ED_LOG)"
  ok "Python $("$venv/bin/python" -c 'import platform; print(platform.python_version())') in $venv"
}

python_from_release() {
  local venv=$1 src=$ED_SOURCE_DIR
  [[ -x $src/python/bin/python3 ]] || die "Release has no bundled Python (python/bin/python3)"
  rm -rf "$ED_ROOT/python"
  cp -a "$src/python" "$ED_ROOT/python"
  run "$ED_ROOT/python/bin/python3" -m venv --clear "$venv" || die "Cannot create virtualenv"
  local -a pip_args=(--no-index --find-links "$src/wheels")
  if [[ $ED_OPT_ALLOW_ONLINE_WHEELS == 1 && -n $ED_PYPI_INDEX ]]; then
    pip_args=(--find-links "$src/wheels" --index-url "$ED_PYPI_INDEX")
  fi
  run "$venv/bin/pip" install --disable-pip-version-check "${pip_args[@]}" \
    -r "$src/wheels/requirements.txt" || die "Installing wheels failed"
  run "$venv/bin/pip" install --disable-pip-version-check "${pip_args[@]}" --no-deps \
    easydeploy-agent edctl || die "Installing EasyDeploy wheels failed"
}

python_from_source() {
  local venv=$1 app=$ED_RELEASE_DIR/app
  local bootstrap=$ED_ROOT/tmp/uv-bootstrap
  local -a index=()
  [[ -n $ED_PYPI_INDEX ]] && index=(--index-url "$ED_PYPI_INDEX")

  if [[ ! -x $bootstrap/bin/uv ]]; then
    run python3 -m venv "$bootstrap" || die "python3 -m venv failed (is python3-venv installed?)"
    run "$bootstrap/bin/pip" install --disable-pip-version-check -q "${index[@]}" "uv==$ED_UV_VERSION" \
      || die "Cannot install uv from the Python package index"
  fi
  local uv=$bootstrap/bin/uv
  export UV_PYTHON_INSTALL_DIR=$ED_ROOT/python
  [[ -n $ED_PYTHON_DOWNLOAD_MIRROR ]] && export UV_PYTHON_INSTALL_MIRROR=$ED_PYTHON_DOWNLOAD_MIRROR
  [[ -n $ED_PYPI_INDEX ]] && export UV_DEFAULT_INDEX=$ED_PYPI_INDEX
  run "$uv" python install 3.12 || die "uv could not install CPython 3.12"
  run "$uv" venv --python 3.12 --seed "$venv" || die "Cannot create virtualenv"
  (
    cd "$app" || exit 1
    "$uv" export --frozen --no-dev --all-packages --no-emit-workspace --no-hashes \
      --output-file "$ED_ROOT/tmp/requirements.txt"
  ) >>"$ED_LOG" 2>&1 || die "uv export failed (is uv.lock present?)"
  run "$uv" pip install --python "$venv/bin/python" -r "$ED_ROOT/tmp/requirements.txt" \
    || die "Installing Python dependencies failed"
  run "$uv" pip install --python "$venv/bin/python" --no-deps "$app/agent" "$app/cli" \
    || die "Installing agent/cli failed"
}
