# ADR-0004: Django 5.2 LTS + DRF

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D4

## Context

The panel needs a mature web framework with auth, ORM, migrations, i18n and an API layer.

## Decision

Django **5.2 LTS** + Django REST Framework + drf-spectacular (OpenAPI 3) + django-filter.

## Consequences

Long support window. The OpenAPI schema drives the generated TypeScript client.
