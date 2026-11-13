# ADR-0015: uv workspace and Python tooling

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D15

## Context

Three Python packages (backend, agent, cli) share dependencies and tooling.

## Decision

A **uv** workspace with members `backend`, `agent`, `cli` and one `uv.lock`; ruff (lint + format, line length 100); mypy strict on agent and cli, standard + django-stubs on backend.

## Consequences

Reproducible installs; the release wheelhouse is exported from the lock file.
