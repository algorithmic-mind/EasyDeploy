# ADR-0010: Native Nginx managed by the agent

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D10

## Context

Sites, apps and the panel itself need a reverse proxy with TLS.

## Decision

Native Nginx from Ubuntu repositories, configured only by the agent with transactional apply (stage → `nginx -t` → swap → reload → health check → rollback).

## Consequences

No container in the request path for the panel. A bad site config never takes down other sites.
