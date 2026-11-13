# ADR-0019: Single admin now, RBAC-ready model

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D19

## Context

Multi-user support is valuable but expands the MVP.

## Decision

MVP has a single admin. The custom `User` model has a `role` field (`admin` only for now) and the permission layer is structured so admin/operator/viewer roles can be added later.

## Consequences

No data migration is needed when RBAC arrives; only new permission classes.
