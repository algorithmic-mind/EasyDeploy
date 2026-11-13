# ADR-0006: Celery + Redis + django-celery-beat

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D6

## Context

Long operations must not block HTTP requests; cron jobs need a persistent scheduler.

## Decision

Celery 5 with a Redis broker; django-celery-beat (database scheduler) for cron jobs. Beat is embedded in the worker (`-B`) on a single node to save memory.

## Consequences

Tasks are idempotent and accept IDs. Windows-native development uses the `solo` pool or eager mode.
