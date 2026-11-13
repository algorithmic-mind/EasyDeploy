# ADR-0009: Privileged agent: FastAPI over a Unix socket

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D9

## Context

The web layer must not run as root, but the panel must perform root operations.

## Decision

Separate service `easydeploy-agent` running as root: FastAPI over `/run/easydeploy/agent/agent.sock`, bearer token + socket permissions, Pydantic v2 typed ops, Jinja2 templates, docker SDK + `docker compose` CLI.

## Consequences

Defense in depth: API bugs cannot run arbitrary shell strings. Windows-native development uses TCP on 127.0.0.1 with the DryRun executor because Python on Windows lacks reliable AF_UNIX server support.
