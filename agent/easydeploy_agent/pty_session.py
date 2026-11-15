"""Interactive terminals for ``WS /v1/pty`` (§9.10).

``PtySession`` runs a real login shell (or ``docker exec``) on a pseudo-terminal; it exists only
with the real executor on POSIX. ``EchoSession`` is used in development/tests (DryRun/Sandbox)
and simply echoes input, so the UI can be built on any machine.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import struct
from typing import Literal

from pydantic import Field

from easydeploy_agent.errors import OpError
from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.validators.names import DockerName, LinuxUser

SHELLS = ("/bin/bash", "/bin/sh", "/bin/ash", "/bin/zsh")
TERM_ENV = {
    "TERM": "xterm-256color",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}


class PtyStart(StrictModel):
    type: Literal["start"] = "start"
    mode: Literal["host", "container"] = "host"
    user: LinuxUser = "root"
    container: DockerName | None = None
    shell_path: Literal["/bin/bash", "/bin/sh", "/bin/ash", "/bin/zsh"] = "/bin/bash"
    cols: int = Field(default=120, ge=10, le=500)
    rows: int = Field(default=32, ge=5, le=300)


def build_argv(start: PtyStart) -> list[str]:
    if start.mode == "container":
        if not start.container:
            raise OpError("pty.invalid", "A container name is required")
        return [
            "docker",
            "exec",
            "-it",
            "-e",
            "TERM=xterm-256color",
            start.container,
            start.shell_path,
        ]
    if start.user == "root":
        return [start.shell_path, "-l"]
    return ["runuser", "-l", start.user]


class EchoSession:
    """Development terminal: echoes input back (no process is started)."""

    def __init__(self, start: PtyStart) -> None:
        self.start_params = start
        self._out: asyncio.Queue[bytes | None] = asyncio.Queue()
        banner = f"EasyDeploy dry-run terminal ({start.mode}). Input is echoed.\r\n$ "
        self._out.put_nowait(banner.encode())

    async def read(self) -> bytes | None:
        return await self._out.get()

    def write(self, data: bytes) -> None:
        text = data.decode("utf-8", "replace").replace("\r", "\r\n$ ")
        self._out.put_nowait(text.encode())

    def resize(self, cols: int, rows: int) -> None:
        return None

    def close(self) -> int:
        self._out.put_nowait(None)
        return 0


class PtySession:
    """A process on a pseudo-terminal; output is read through the event loop."""

    def __init__(self, start: PtyStart) -> None:
        import pty  # POSIX only

        argv = build_argv(start)
        env = {**TERM_ENV, "HOME": "/root" if start.user == "root" else f"/home/{start.user}"}
        pid, fd = pty.fork()
        if pid == 0:  # child: become the shell immediately
            try:
                os.chdir(env["HOME"])
            except OSError:
                os.chdir("/")
            os.execvpe(argv[0], argv, env)  # noqa: S606  # nosec B606 - argv list, no shell parsing
        self.pid, self.fd = pid, fd
        self._out: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.resize(start.cols, start.rows)
        loop = asyncio.get_running_loop()
        loop.add_reader(fd, self._on_readable)
        self._loop = loop
        self._closed = False

    def _on_readable(self) -> None:
        try:
            data = os.read(self.fd, 65536)
        except OSError:  # EIO: the process exited
            data = b""
        if not data:
            self._loop.remove_reader(self.fd)
            self._out.put_nowait(None)
            return
        self._out.put_nowait(data)

    async def read(self) -> bytes | None:
        return await self._out.get()

    def write(self, data: bytes) -> None:
        if not self._closed:
            os.write(self.fd, data)

    def resize(self, cols: int, rows: int) -> None:
        import fcntl
        import termios

        with contextlib.suppress(OSError):
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def close(self) -> int:
        """Hang up the process and reap it; returns its exit status."""
        if self._closed:
            return 0
        self._closed = True
        with contextlib.suppress(OSError, ValueError):
            self._loop.remove_reader(self.fd)
        with contextlib.suppress(ProcessLookupError):
            os.kill(self.pid, signal.SIGHUP)
        status = 0
        with contextlib.suppress(ChildProcessError):
            _pid, raw = os.waitpid(self.pid, 0)
            status = os.waitstatus_to_exitcode(raw)
        with contextlib.suppress(OSError):
            os.close(self.fd)
        return status
