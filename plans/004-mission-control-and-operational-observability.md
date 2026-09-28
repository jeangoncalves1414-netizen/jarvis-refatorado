# Plan 004: Criar o Mission Control e a telemetria operacional

> **Executor instructions**: Build on the immutable actions from Plan 003. Do not turn private diagnostics into a public dump and do not expose audio, prompts, transcripts, credentials or biometrics.
>
> **Drift check**: `git status --short -- app/core/diagnostics.py app/ui/panel frontend/src tests`.

## Status

- **Priority**: P1
- **Effort**: M/L
- **Risk**: MED
- **Depends on**: `plans/002-secure-local-control-plane.md`, `plans/003-action-kernel-and-workflows.md`
- **Category**: direction + dx
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

The assistant already has private diagnostics (`app/core/diagnostics.py`) and many independent states (voice, providers, tasks, bridge, reminders). The user needs one trustworthy place to understand what Jarvis is doing, what needs approval and why something failed. This is the professional “operating room”, not a decorative dashboard.

## Current state

- `app/core/diagnostics.py:13-68` writes bounded JSONL diagnostic metadata and filters sensitive keys.
- `app/ui/panel/server.py` manually serves a large collection of APIs; new dashboard endpoints should be a focused API module, not another large conditional branch.
- `frontend/src/App.tsx` is already large; use dedicated pages/components and existing shell conventions.
- Plan 003 is the source of truth for action status/history; do not infer completion from chat text.

## Scope

**In scope:** diagnostics/event aggregation additions, a focused `mission_control` API module, new frontend page/components, safe status adapters for voice/provider/bridge/proactive/action state, and targeted tests.

**Out of scope:** remote telemetry SaaS, storing user conversation contents, changing action policy, adding new device capabilities, visual redesign of unrelated pages.

## Steps

1. Define a versioned, redacted health snapshot contract with component status (`healthy`, `degraded`, `unavailable`), last transition, safe reason code and correlation ID. Adapters may report voice engine, provider effective route, Action Kernel queue, reminders and bridge device count.
2. Add a bounded operational event feed derived from action journal and safe diagnostics. Preserve existing retention guarantees; no raw exception bodies unless already sanitized.
3. Implement authenticated read APIs: snapshot, recent events, active/pending actions and a detail view by correlation/action ID. Add filters by component/level/time, pagination and no wildcard CORS dependency.
4. Build the Mission Control page: “agora”, approvals, recent completed/failed actions, voice/provider health, reminder/goal summary and connected devices. Make error states actionable (“ver detalhes técnicos”, “tentar novamente”, “abrir configuração”), but never auto-retry high-risk actions.
5. Add a “diagnostic export” that produces a redacted local bundle only after explicit confirmation. It must state what is excluded and omit secrets, media and conversation content.

**Verify after each backend step**: `python -m pytest -q tests/test_diagnostics.py tests/test_mission_control.py` exits 0. **Verify UI**: `Set-Location frontend; npm run build` exits 0.

## Test plan

Create `tests/test_mission_control.py` with temporary diagnostics/action storage. Assert snapshot schema stability, no sensitive fields, transition display, empty/degraded states, pagination and authorization denials. Model safe diagnostics assertions after `tests/test_diagnostics.py`.

## Done criteria

- [ ] Mission Control presents real action records, not guessed chat state.
- [ ] Every health item has a safe status and correlation ID.
- [ ] Export and API output stay redacted.
- [ ] Tests, compileall, frontend build and diff check pass.

## STOP conditions

- A desired status requires recording prompt, transcript, token, raw audio or biometric data.
- An adapter needs to invoke an external provider merely to render the dashboard.
- Plan 003 action store is not available.

## Maintenance notes

Treat this contract as an operator API. New systems provide a small status adapter and safe event vocabulary rather than creating their own hidden logs.
