# ADR-0013: Frontend: Vue 3 + TypeScript + Bootstrap 5.3

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D13

## Context

The UI must be bilingual with full RTL, themeable, and light enough to ship prebuilt.

## Decision

Vue 3 + TypeScript (strict) + Vite + Pinia + Vue Router + vue-i18n; Bootstrap **5.3.9** compiled from Sass with project variables; Bootstrap Icons bundled; Bootstrap's ES-module JS wrapped in in-house `Ed*` components; RTL via postcss-rtlcss; dark mode via `data-bs-theme`. No jQuery, no third-party Vue–Bootstrap wrapper. Bootstrap 6 (alpha) is not used.

## Consequences

One CSS bundle serves both directions. All Bootstrap JS lifecycle lives in `components/ui/`.
