# ADR-0001: Product name and slugs

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D1

## Context

The product needs one stable name used in packages, paths, systemd units, Docker labels and the CLI.

## Decision

Name **EasyDeploy**; slug `easydeploy`; CLI `edctl`; Docker network `easydeploy-net`; Docker label prefix `io.easydeploy.`; release host placeholder `get.easydeploy.example` (to be replaced by the owner's domain before the first public release).

## Consequences

All paths (`/opt/easydeploy`, `/etc/easydeploy`, `/run/easydeploy`), units (`easydeploy-*.service`) and labels derive from the slug. Renaming later requires a migration of on-disk state and Docker labels.
