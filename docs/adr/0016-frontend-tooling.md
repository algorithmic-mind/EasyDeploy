# ADR-0016: Frontend tooling

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D16

## Context

The frontend needs a consistent build and quality toolchain.

## Decision

Node 24 LTS, pnpm (npm accepted for local work), `sass-embedded`, PostCSS with `postcss-rtlcss`, ESLint, Prettier, Vitest, Playwright.

## Consequences

CI builds the bundle and runs unit tests; Playwright E2E runs against the dev stack with a fake agent.
