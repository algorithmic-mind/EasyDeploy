# ADR-0018: structlog JSON logging

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D18

## Context

Diagnosing issues across API, worker and agent requires correlated logs.

## Decision

structlog JSON logs to journald; `request_id` propagated API → worker → agent through `X-Request-ID`; secrets masked by a processor.

## Consequences

Every log line can be correlated with a request or task.
