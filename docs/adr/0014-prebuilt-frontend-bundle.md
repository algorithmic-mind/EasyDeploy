# ADR-0014: Prebuilt frontend bundle

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D14

## Context

Node.js on production servers costs memory and attack surface.

## Decision

The SPA is built in CI and shipped as static files inside the release; Nginx serves it directly.

## Consequences

No Node.js on servers. Frontend changes require a release build.
