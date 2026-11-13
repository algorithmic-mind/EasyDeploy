# ADR-0011: lego for ACME

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D11

## Context

Certificates need HTTP-01 and DNS-01 with many DNS providers (incl. Cloudflare and ArvanCloud).

## Decision

The **lego** CLI (single Go binary), pinned and checksum-verified, driven by the agent.

## Consequences

No Python ACME stack to maintain. 150+ DNS providers available by mapping env vars.
