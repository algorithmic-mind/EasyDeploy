# ADR-0020: UI languages: English and Persian

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D20

## Context

Target users include Persian speakers; RTL must be first-class, not retrofitted.

## Decision

English (default) and Persian (RTL). Every user-facing string is translatable from day one; en and fa catalogs must be complete before a phase is accepted. Optional Jalali calendar.

## Consequences

An i18n completeness test runs in CI for both backend and frontend.
