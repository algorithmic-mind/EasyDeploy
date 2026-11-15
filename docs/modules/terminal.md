# Module: terminal

## Purpose
Interactive shells in the browser (§9.10): a login shell on the host (as root or another Linux user) and
`docker exec` into a running container, with multiple tabs, resize, copy/paste, font size and a library of
command snippets. Opening a terminal requires **sudo mode**; sessions close after `terminal.idle_minutes`
without input; every session start and end is audited.

Saved SSH hosts (asyncssh in the API process) are **deferred to Phase 2** (navigation shows them as Phase 2).

## Data path
```
xterm.js ──WS /ws/terminal/<session>/──▶ API (Channels TerminalConsumer)
                                          │ sudo check, frame validation, idle watchdog, audit
                                          └─WS /v1/pty (Unix socket; bearer + HMAC sudo token)──▶ agent
                                                                                                  │ PtyStart validated
                                                                                                  └─ pty.fork → bash -l | runuser -l <user> | docker exec -it <c> <shell>
```
* The agent never receives a command line from the API: only the typed `PtyStart` (`mode`, `user`,
  `container`, `shell_path` from an allowlist, `cols`, `rows`) — argv is built in `pty_session.build_argv`.
* With the DryRun/Sandbox executor (development, tests, non-POSIX) the agent serves an `EchoSession`.
* The API connects with `AgentClient.open_pty` (websockets, ADR-0023); tests use `FakeAgent.open_pty`
  (`FakePty`) and a real agent app over TCP (`apps/core/tests/test_agent_pty.py`).

## WebSocket protocol (same frames on both hops)
Browser → server, JSON text frames:
* `{"type":"start","mode":"host|container","user":"root","container":null,"shell_path":"/bin/bash","cols":120,"rows":32}` (first frame)
* `{"type":"input","data":"ls\r"}` (≤ 64 KiB per frame)
* `{"type":"resize","cols":100,"rows":30}` (clamped to 10–500 × 5–300)

Server → browser: terminal output as **binary** frames; control frames as JSON text:
`{"type":"started"}`, `{"type":"exit","code":0}`, `{"type":"error","code":"…","fields":[…]}`.

Close codes: `4401` not authenticated, `4403` sudo mode required (or cross-origin), `4400` invalid start frame,
`4408` idle timeout, `4502` agent unavailable / refused.

## Endpoints (`/api/v1/terminal/`)
| Method | Path | Notes |
|---|---|---|
| POST | `check` | requires sudo mode (403 `auth.sudo_required` triggers the UI prompt); returns `sudo_until`, `idle_minutes` |
| GET/POST | `snippets` | search `?search=`; `command` ≤ 10 000 chars, not blank |
| GET/PATCH/PUT/DELETE | `snippets/<id>` | |

API keys use scope `terminal:read|write` for snippets; `check` and the WebSocket are session-only.

## Audit
`terminal.session_started` / `terminal.session_ended` (resource = tab session id; details: mode, user,
container, shell, `duration_seconds`), `terminal.snippet_created|updated|deleted`. The agent additionally logs
`pty.open` / `pty.close` in its own audit log.

## Error codes
`terminal.invalid_start`, `terminal.idle_timeout`, `terminal.refused`, `terminal.closed`, `agent.unavailable`.

## Settings
`terminal.idle_minutes` (30; 1–1440).

## Frontend
* `/terminal/local` and `/terminal/container-exec` → `TerminalPage.vue` (tabs, font size, snippets panel with
  Insert = bracketed paste and Run = type + Enter). `?container=<name>` opens the form for that container.
* `/terminal/snippets` → `SnippetsPage.vue` (CRUD).
* `TerminalView.vue` wraps xterm.js + fit addon; Ctrl+Shift+C / Ctrl+Shift+V copy and paste.
* xterm's and Monaco's CSS are excluded from postcss-rtlcss (`postcss.config.js`): inside a `dir="ltr"` island
  on an RTL page both flipped variants would match and break their layout. The terminal container uses
  `overflow: clip` so xterm's off-screen helpers cannot scroll an RTL page.

## Not yet
Saved SSH hosts (Phase 2), session recording/replay, keeping sessions alive across page navigation.
