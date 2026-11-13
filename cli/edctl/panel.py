"""Panel vhost rendering (shared template with the installer) and transactional apply."""

from __future__ import annotations

import secrets
import shutil
import string
from pathlib import Path

from edctl.config import Paths
from edctl.system import Result, run

LISTEN_MODES = ("ipv4", "ipv6", "dual")
ENTRANCE_ALPHABET = string.ascii_letters + string.digits


def new_entrance(length: int = 12) -> str:
    return "".join(secrets.choice(ENTRANCE_ALPHABET) for _ in range(length))


def listen_lines(port: int, mode: str) -> str:
    lines = []
    if mode in ("ipv4", "dual"):
        lines.append(f"listen {port} ssl;")
    if mode in ("ipv6", "dual"):
        lines.append(f"listen [::]:{port} ssl;")
    return "\n    ".join(lines)


def render(template: str, *, port: int, listen: str, p: Paths) -> str:
    values = {
        "@LISTEN@": listen_lines(port, listen),
        "@PANEL_PORT@": str(port),
        "@API_SOCKET@": str(p.run_dir / "api" / "api.sock"),
        "@FRONTEND_DIR@": str(p.current / "frontend"),
        "@SSL_CERT@": str(p.etc / "ssl" / "panel" / "fullchain.pem"),
        "@SSL_KEY@": str(p.etc / "ssl" / "panel" / "privkey.pem"),
    }
    out = template
    for token, value in values.items():
        out = out.replace(token, value)
    return out


def apply(p: Paths, *, port: int, listen: str) -> Result:
    """Write panel.conf, validate with ``nginx -t``, reload; restore the old file on failure."""
    content = render(p.panel_template.read_text(encoding="utf-8"), port=port, listen=listen, p=p)
    target: Path = p.panel_conf
    backup = target.with_suffix(".conf.bak")
    had_old = target.exists()
    if had_old:
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".conf.new")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    check = run(["nginx", "-t"], timeout=30)
    if check.ok:
        reload = run(["systemctl", "reload", "nginx"], timeout=60)
        if reload.ok:
            backup.unlink(missing_ok=True)
            return reload
        check = reload
    if had_old:
        backup.replace(target)
    else:
        target.unlink(missing_ok=True)
    return check


def port_in_use(port: int) -> bool:
    result = run(["ss", "-Htln", f"sport = :{port}"], timeout=10)
    return result.ok and bool(result.stdout.strip())
