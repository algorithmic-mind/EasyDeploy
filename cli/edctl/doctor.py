"""``edctl doctor`` (lite): actionable checks of a running installation (§9.18)."""

from __future__ import annotations

import os
import shutil
import sqlite3
import ssl
import stat
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from edctl.config import Paths, read_env
from edctl.system import DEPENDENCIES, UNITS, run, unit_state

MIN_FREE_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""


def _units() -> list[Check]:
    checks = []
    for unit in (*UNITS, *DEPENDENCIES):
        state = unit_state(unit)
        checks.append(
            Check(
                f"service {unit}",
                state == "active",
                state,
                f"systemctl restart {unit} && journalctl -u {unit} -n 50",
            )
        )
    return checks


def _socket(path: str, dir_group: str, dir_mode: int) -> Check:
    """The socket must exist; its directory (group + mode) is the access boundary (§5.2)."""
    import grp

    name = f"socket {path}"
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return Check(name, False, "missing", "edctl restart")
    if not stat.S_ISSOCK(st.st_mode):
        return Check(name, False, "not a socket", "edctl restart")
    dst = os.stat(os.path.dirname(path))
    try:
        group_name = grp.getgrgid(dst.st_gid).gr_name
    except KeyError:
        group_name = str(dst.st_gid)
    actual = stat.S_IMODE(dst.st_mode)
    ok = group_name == dir_group and actual == dir_mode
    return Check(
        name,
        ok,
        f"dir group={group_name} mode={actual:o}",
        "systemd-tmpfiles --create /etc/tmpfiles.d/easydeploy.conf && edctl restart",
    )


def _database(path: str) -> Check:
    name = f"database {os.path.basename(path)}"
    if not os.path.exists(path):
        return Check(name, False, "missing", "re-run the installer or restore a snapshot")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5) as conn:
            row = conn.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        return Check(name, False, str(exc), "edctl backup panel; then restore from a backup")
    return Check(name, bool(row) and row[0] == "ok", str(row[0] if row else "?"))


def _nginx() -> Check:
    result = run(["nginx", "-t"], timeout=30)
    detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
    return Check("nginx config", result.ok, detail[0], "nginx -t  # read the error, fix the file")


def _docker() -> Check:
    result = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    return Check("docker", result.ok, result.stdout.strip(), "systemctl restart docker")


def _disk(p: Paths) -> Check:
    target = p.root if p.root.exists() else p.root.parent
    free = shutil.disk_usage(target).free
    return Check(
        "disk space",
        free >= MIN_FREE_BYTES,
        f"{free / 1024**3:.1f} GiB free",
        "free space (Toolbox → Cleanup or docker system prune)",
    )


def _clock() -> Check:
    result = run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], timeout=10)
    synced = result.stdout.strip() == "yes"
    return Check("clock synchronized", synced, result.stdout.strip(), "timedatectl set-ntp true")


def _health(p: Paths) -> Check:
    env = read_env(p.env_file)
    port = env.get("ED_PANEL_PORT", "")
    if not port.isdigit():
        return Check("panel health", False, "ED_PANEL_PORT missing", "edctl set-port <port>")
    ctx = ssl.create_default_context(cafile=str(p.panel_cert)) if p.panel_cert.exists() else None
    if ctx is not None:
        ctx.check_hostname = False  # self-signed panel cert is issued for the IP / hostname
    url = f"https://127.0.0.1:{port}/api/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=10, context=ctx) as resp:
            body = resp.read(200).decode()
            return Check("panel health", resp.status == 200, body)
    except Exception as exc:
        return Check("panel health", False, type(exc).__name__, "edctl logs api")


def run_checks(p: Paths) -> list[Check]:
    steps: list[Callable[[], list[Check] | Check]] = [
        _units,
        lambda: _socket(str(p.run_dir / "agent" / "agent.sock"), "easydeploy", 0o750),
        lambda: _socket(str(p.run_dir / "api" / "api.sock"), "www-data", 0o2750),
        lambda: _database(str(p.root / "data" / "panel.db")),
        lambda: _database(str(p.root / "data" / "monitor.db")),
        _nginx,
        _docker,
        lambda: _disk(p),
        _clock,
        lambda: _health(p),
    ]
    results: list[Check] = []
    for step in steps:
        out = step()
        results.extend(out if isinstance(out, list) else [out])
    return results
