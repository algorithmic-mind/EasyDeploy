# ADR-0007: SQLite (WAL) for panel data, separate monitor.db

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D7

## Context

The panel must run on 1 GB VPSs; a separate database server costs memory and operations.

## Decision

SQLite in WAL mode (`panel.db`) plus `monitor.db` for metrics, selected by a Django database router. `synchronous=NORMAL`, `busy_timeout=5000`, `transaction_mode=IMMEDIATE`. Code stays database-agnostic.

## Consequences

Metrics writes do not contend with panel writes. PostgreSQL can be swapped in through settings.
