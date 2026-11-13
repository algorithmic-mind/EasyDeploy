# ADR-0003: Bundled CPython 3.12

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D3

## Context

Ubuntu 22.04 ships Python 3.10, 24.04 ships 3.12, 26.04 ships a newer one; depending on the host interpreter makes behavior differ by release.

## Decision

Ship CPython **3.12** from python-build-standalone inside the release tarball. In `--from-source` dev installs, `uv python install 3.12` (which verifies the download hash) provides the same interpreter.

## Consequences

The host Python version is irrelevant. The release tarball grows by ~30 MB per architecture.
