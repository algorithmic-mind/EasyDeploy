# ADR-0023: websockets as the API's client for the agent terminal

- Status: Accepted
- Date: 2026-11-15
- Source: MASTER_PROMPT §5.3, §5.4, §9.10

## Context

The terminal (§9.10) runs a PTY inside the root agent and streams it to the browser through
`/ws/terminal/<session>/`. The agent exposes `WS /v1/pty` on its Unix socket, so the API process needs a
WebSocket *client* that can connect over a Unix domain socket (production) and over TCP (development).
httpx, the API's HTTP client for the agent, has no WebSocket support.

## Decision

Use **websockets** (BSD-3-Clause), the asyncio library whose `unix_connect` / `connect` cover both
transports. It is already installed in every deployment as part of `uvicorn[standard]`; the backend now
declares it directly (`websockets>=13`) so the import does not depend on uvicorn's extras.

## Consequences

No new package in the wheelhouse. The bridge lives in `apps.core.agent_client.AgentClient.open_pty`;
tests run it against the real agent app over TCP. Alternatives considered: `aiohttp` (a second HTTP
stack) and `wsproto` (low-level, more code to maintain).
