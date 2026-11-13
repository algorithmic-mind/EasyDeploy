"""Process helpers. Argument lists only — never a shell (§10.2)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from edctl.config import paths, read_env

UNITS = ("easydeploy-agent", "easydeploy-api", "easydeploy-worker")
DEPENDENCIES = ("nginx", "redis-server", "docker")


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    argv: Sequence[str],
    *,
    input_text: str | None = None,
    timeout: float = 60,
    env: dict[str, str] | None = None,
) -> Result:
    try:
        proc = subprocess.run(
            list(argv),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return Result(127, "", f"{argv[0]}: command not found")
    except subprocess.TimeoutExpired:
        return Result(124, "", f"{argv[0]}: timed out after {timeout:.0f}s")
    return Result(proc.returncode, proc.stdout, proc.stderr)


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def unit_state(unit: str) -> str:
    return run(["systemctl", "is-active", unit], timeout=10).stdout.strip() or "unknown"


def systemctl(action: str, target: str) -> Result:
    return run(["systemctl", action, target], timeout=120)


def manage(*args: str, input_text: str | None = None) -> Result:
    """Run a Django management command as the unprivileged ``easydeploy`` user."""
    p = paths()
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "DJANGO_SETTINGS_MODULE": "easydeploy.settings.prod",
        **{k: v for k, v in read_env(p.env_file).items() if k.startswith("ED_")},
    }
    argv = [
        "runuser",
        "-u",
        "easydeploy",
        "--",
        str(p.python),
        str(p.manage_py),
        *args,
    ]
    return run(argv, input_text=input_text, env=env, timeout=120)
