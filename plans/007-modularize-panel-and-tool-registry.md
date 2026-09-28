# Plan 007: Modularizar o painel e o registro de ferramentas com cobertura de caracterização

> **Executor instructions**: Do not perform a cosmetic rewrite. Move one route/tool family at a time behind characterization tests, preserving endpoints and response shapes. Plan 006 must be complete first.
>
> **Drift check**: `git status --short -- app/ui/panel app/agent/tools app/agent/action_executor.py tests frontend/src/App.tsx`.

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: `plans/006-isolated-verification-release-and-docs.md`
- **Category**: tech-debt
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

The product is growing faster than its boundaries. `app/ui/panel/server.py` is approximately 1,885 lines, `app/services/llm.py` 1,359, `app/agent/orchestrator.py` 925, `frontend/src/App.tsx` 914 and `app/agent/tools/registry.py` 311. Their size is not a bug by itself, but it makes adding Action Kernel, Mission Control and future devices risky because changes touch unrelated behavior.

## Current state

- `app/ui/panel/server.py` is a `BaseHTTPRequestHandler` dispatcher with manually chained API routes and static delivery. Existing focused handler modules such as `app/ui/panel/api/settings.py` return `(status, dict)`.
- `app/agent/tools/registry.py` imports/registers many tools in one file and already groups `GENERAL_TOOL_NAMES` and tutor tools.
- `frontend/src/App.tsx` orchestrates view selection, API loading and page props. Existing `frontend/src/pages/` and `components/` are the extraction pattern.
- Plan 006 supplies a safe regression baseline; use it before every incremental move.

## Scope

**In scope:** route-module extraction from panel server, registry catalog extraction, selected App shell/page-state extraction, characterization tests and architecture documentation updates.

**Out of scope:** changing public URLs/JSON contracts, deleting legacy features, converting framework, changing database format, broad LLM/voice rewrites, reformatting unrelated files.

## Steps

1. Add contract/characterization tests for representative GET/POST/error responses from settings, identity, bridge, action, voice and static routes. Snapshot only stable fields; never snapshot secrets or timestamps.
2. Define a small route dispatcher protocol: path/method match, authenticated principal/context, handler return `(status, payload)`. Move one family at a time into `app/ui/panel/api/`, beginning with read-only settings/status, then bridge and identity, then action/mission-control. Keep server responsible only for HTTP parsing, auth policy, static assets and dispatch.
3. Extract registry declarations into a typed catalog module with registration factories and metadata. Preserve registration order and optional import behavior. Action Kernel metadata must remain the single source of risk/capability data.
4. Extract frontend page state and API clients from `App.tsx` into focused hooks/pages without changing the UI contract. Do one page family per pull request/commit and build after each extraction.
5. Add module boundaries and architecture map to `docs/ARCHITECTURE.md`; state actual size goals as guidance, not a mechanical rule. Review remaining large modules and open separate plans only where tests prove an extraction seam.

**Verify after each extraction**: run the relevant characterization test subset, `python -m compileall -q app`, `Set-Location frontend; npm run build`, and `git diff --check`.

## Test plan

Create `tests/test_panel_route_contracts.py` using temporary HTTP server fixtures. Extend registry tests to assert expected names/metadata and optional dependency behavior. Keep contracts focused on observable behavior rather than private implementation.

## Done criteria

- [ ] Server dispatches route families through focused modules with unchanged public contracts.
- [ ] Tool registry catalog has one metadata source compatible with Action Kernel.
- [ ] `App.tsx` is reduced by extracting real pages/hooks, not duplicated state.
- [ ] Characterization tests, safe suite, compileall and frontend build pass.

## STOP conditions

- A route’s behavior is undocumented and has no testable caller; characterize it before moving it.
- Extraction changes authentication, authorization or action semantics from Plans 002–003.
- A circular import appears after two reasonable boundary adjustments.

## Maintenance notes

Prefer adding a focused module to extending the central server/registry/App. Enforce the route dispatcher and tool catalog boundary in review; the goal is safe evolution, not a one-time line-count target.
