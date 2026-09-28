# Plan 002: Proteger o plano de controle local e a ponte de dispositivos

> **Executor instructions**: Execute each step in order. Preserve every pre-existing worktree change. Do not use `git reset`, `git clean`, stashes, or a bind to LAN as a shortcut. Stop on any STOP condition.
>
> **Drift check (run first)**: `git status --short -- app/ui/panel/server.py app/services/device_bridge.py app/config.py app/main.py tests` and `git diff -- app/ui/panel/server.py app/services/device_bridge.py app/config.py app/main.py tests`. Compare the live code with the excerpts below before editing.

## Status

- **Priority**: P0
- **Effort**: L
- **Risk**: HIGH — authentication must not lock the desktop user out.
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

The panel currently operates as a trusted local control plane, but it exposes unrestricted browser CORS and endpoints that run Python/PowerShell, commands and device actions. This is unsafe if a malicious page reaches localhost and becomes unacceptable when the configured host is LAN-visible. The future mobile/Raspberry direction needs authenticated devices, revocable credentials and explicit trusted origins before it gains new capabilities.

## Current state

- `app/config.py` defaults to a loopback host, while `app/main.py` accepts `0.0.0.0` and prints a network URL.
- `app/ui/panel/server.py:94-95` emits `Access-Control-Allow-Origin: *`; `:655-657` allows every method and Authorization header.
- `app/ui/panel/server.py:867-890` accepts pair, heartbeat, command and remove bridge actions with no request principal.
- `app/ui/panel/server.py:1147-1180` exposes Hacker Terminal policy, execution and history; `:1362-1404` runs arbitrary Python or PowerShell received from an HTTP body.
- `app/services/device_bridge.py:102-133` only rejects an invalid pairing code when one was supplied; omitting it registers a device. The success response returns the pairing code.
- Existing route tests use an ephemeral `HTTPServer` fixture in `tests/test_settings_api.py`; follow that style. Keep error responses `{ok: false, error: ...}`.

## Commands you will need

| Purpose | Command | Expected result |
|---|---|---|
| Targeted tests | `python -m pytest -q tests/test_control_plane_security.py tests/test_device_bridge.py` | exits 0 |
| Python syntax | `python -m compileall -q app` | exits 0, no output |
| UI build | `Set-Location frontend; npm run build` | exits 0 |
| Whitespace | `git diff --check` | no output |

## Scope

**In scope only:** `app/config.py`, `app/main.py`, `app/ui/panel/server.py`, new small modules under `app/core/` or `app/ui/panel/api/`, `app/services/device_bridge.py`, `app/services/hacker_terminal.py`, `app/agent/tools/script_runner.py`, settings UI files needed to display a local access token, and new targeted tests.

**Out of scope:** exposing the service publicly; storing plaintext passwords; changing LLM provider routes (Plan 001); changing biometric recognition; adding a cloud identity provider; removing Hacker Terminal or Script Runner.

## Steps

### Step 1: Define a local access policy and server mode

Create a small typed policy module that distinguishes `loopback` from `lan`. Default remains loopback. In LAN mode require an explicit opt-in setting and generate a high-entropy local control token on first run; store only a non-secret identifier in diagnostics. Refuse to start in LAN mode without the token configuration and print a safe setup instruction, never the token.

**Verify**: unit tests prove loopback mode starts without a token, LAN mode fails closed when configuration is absent, and configuration validation never returns the token.

### Step 2: Authenticate and constrain every state-changing API

Add one request-authentication helper before route dispatch. Loopback requests may use a same-origin token/cookie strategy appropriate to the desktop UI; LAN requests must require the control token on every API request. Use an allowlist for CORS origins, derived from the active local UI and configured trusted LAN origins; do not emit wildcard CORS. Reject untrusted `Origin`, unauthenticated mutating requests, and cross-origin preflight requests with JSON errors. Preserve static asset delivery.

Treat `/api/script/run`, `/api/hacker/*`, `/api/bridge`, settings writes, memory writes, vision capture and every other POST/PUT/PATCH/DELETE as protected. Avoid route-by-route copies; centralize the policy.

**Verify**: HTTP tests assert a foreign origin cannot read or post, a missing/invalid token receives 401/403 in LAN mode, a valid token can use a safe fixture endpoint, and same-origin loopback UI behavior remains available.

### Step 3: Replace pairing-code bypass with device credentials

Require a pairing code exactly once for a new device. On success issue a randomly generated per-device secret/token, return it only in that pairing response, store only a one-way verifier, and require it for heartbeat, commands and removal. Do not return the global pairing code in status or subsequent responses. Add token rotation and revoke/remove behavior; deny a command unless both source and target are known devices with suitable permissions.

Define a minimal device permission vocabulary (`status`, `notify`, `command`) so a future room device cannot automatically acquire desktop-command power.

**Verify**: tests cover missing, wrong and correct pairing code; token-required heartbeat; revoked token; unknown source; and no pairing or device secret in status/events/logs.

### Step 4: Bind dangerous execution to a server-side authorization receipt

Do not treat a frontend modal, `force: true`, or a `direct_execution` policy as authorization. Create a short-lived, single-use authorization receipt tied to action type, normalized command/script digest, requesting principal and expiry. The server must issue the receipt only after the authenticated user confirms a preview; `/api/script/run` and Hacker Terminal execution must require it. Low-risk command policy may still skip a modal only through a stored, explicit user policy, but it must create an audit record.

Keep execution timeout and current user experience. Do not implement sandboxing as a claim of security; label code execution as local privileged execution.

**Verify**: tests prove direct raw POST execution fails, altered command after approval fails, a receipt cannot be reused or transferred, expiry fails, and approved harmless fixture commands execute once.

### Step 5: Record security-relevant events safely

Use the existing private metadata-only diagnostic pattern in `app/core/diagnostics.py`. Record authentication denials, pairing/revocation and execution receipt outcomes with correlation IDs, but never command bodies, script contents, audio, tokens or pairing codes.

**Verify**: diagnostic tests inspect the written JSONL and confirm sensitive field names/values are absent.

## Test plan

Create `tests/test_control_plane_security.py` using the isolated HTTP fixture pattern in `tests/test_settings_api.py`. Create `tests/test_device_bridge.py` with `tmp_path` state. Include success and denial paths for loopback/LAN mode, origin policy, token verification, pairing, revocation and execution receipts. Keep tests offline and do not execute PowerShell or real shell commands.

## Done criteria

- [ ] No API response emits wildcard CORS.
- [ ] LAN mode fails closed without authentication and trusted origins.
- [ ] A pairing code is mandatory for new devices; device credentials are revocable and never re-exposed.
- [ ] Script and terminal execution require a server-validated single-use receipt.
- [ ] Targeted tests, compileall, frontend build and `git diff --check` pass.
- [ ] No unrelated worktree files were overwritten.

## STOP conditions

- The current UI cannot attach a same-origin authentication mechanism without modifying an out-of-scope login/session system.
- A required client is a non-browser protocol that cannot supply an Authorization header or pairing token.
- Any proposed change prints, commits, logs or returns a credential value.
- The executor needs to expose the service beyond the local network.

## Maintenance notes

All future API routes must pass through this policy. Review new device capabilities and execution paths as permission changes, not ordinary UI features. Hardware work is deliberately deferred until this boundary is proven by tests.
