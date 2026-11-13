"""Server paths and the bootstrap env file (``/etc/easydeploy/easydeploy.env``)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


@dataclass(frozen=True)
class Paths:
    root: Path  # /opt/easydeploy
    etc: Path  # /etc/easydeploy
    nginx_dir: Path  # /etc/nginx/easydeploy
    run_dir: Path  # /run/easydeploy

    @property
    def env_file(self) -> Path:
        return self.etc / "easydeploy.env"

    @property
    def current(self) -> Path:
        return self.root / "current"

    @property
    def python(self) -> Path:
        return self.current / "venv" / "bin" / "python"

    @property
    def manage_py(self) -> Path:
        return self.current / "app" / "backend" / "manage.py"

    @property
    def panel_template(self) -> Path:
        return self.current / "deploy" / "nginx" / "panel.conf.template"

    @property
    def panel_conf(self) -> Path:
        return self.nginx_dir / "panel.conf"

    @property
    def panel_cert(self) -> Path:
        return self.etc / "ssl" / "panel" / "fullchain.pem"

    @property
    def version_file(self) -> Path:
        return self.current / "VERSION"


def paths() -> Paths:
    """Real paths; ``ED_TEST_ROOT`` relocates everything under one directory (tests only)."""
    base = os.environ.get("ED_TEST_ROOT")
    if base:
        b = Path(base)
        return Paths(b / "opt", b / "etc", b / "nginx", b / "run")
    return Paths(
        Path("/opt/easydeploy"),
        Path("/etc/easydeploy"),
        Path("/etc/nginx/easydeploy"),
        Path("/run/easydeploy"),
    )


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        match = _LINE.match(raw)
        if match:
            data[match.group(1)] = match.group(2).strip("\"'")
    return data


def update_env(path: Path, key: str, value: str) -> None:
    """Set ``key=value`` in the env file, keeping comments and order; atomic replace."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, found = [], False
    for raw in lines:
        match = _LINE.match(raw)
        if match and match.group(1) == key and not raw.lstrip().startswith("#"):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(raw)
    if not found:
        out.append(f"{key}={value}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    tmp.replace(path)
