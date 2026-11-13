"""``fs.*`` ops.

The admin is root-equivalent, so listing is allowed everywhere; mutating ops (Phase 1)
enforce the protected-path rules of §9.9.
"""

from __future__ import annotations

import functools

from easydeploy_agent.executor import FileStat
from easydeploy_agent.protocol.fs import FsEntry, FsListParams, FsListResult
from easydeploy_agent.registry import OpContext, op


@functools.lru_cache(maxsize=256)
def _user_name(uid: int) -> str:
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


@functools.lru_cache(maxsize=256)
def _group_name(gid: int) -> str:
    try:
        import grp

        return grp.getgrgid(gid).gr_name
    except (ImportError, KeyError):
        return str(gid)


def to_entry(st: FileStat) -> FsEntry:
    return FsEntry(
        name=st.name,
        path=st.path,
        kind=st.kind,
        size=st.size,
        mode=f"{st.mode:04o}",
        owner=_user_name(st.uid),
        group=_group_name(st.gid),
        mtime=st.mtime,
        link_target=st.link_target,
    )


@op("fs.list", params=FsListParams, result=FsListResult, timeout=30)
def fs_list(params: FsListParams, ctx: OpContext) -> FsListResult:
    """List a directory (directories first, then by name)."""
    stats = ctx.executor.scandir(params.path)
    if not params.show_hidden:
        stats = [s for s in stats if not s.name.startswith(".")]
    stats.sort(key=lambda s: (s.kind != "dir", s.name.lower()))
    truncated = len(stats) > params.limit
    return FsListResult(
        path=params.path,
        entries=[to_entry(s) for s in stats[: params.limit]],
        truncated=truncated,
    )
