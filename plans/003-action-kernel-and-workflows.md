# Plan 003: Introduzir o Action Kernel e workflows auditáveis

> **Executor instructions**: Read Plan 002 first and do not bypass its authorization receipt. Preserve unrelated changes. Start with tests and additive data structures; do not replace existing tools in one commit.
>
> **Drift check**: `git status --short -- app/agent app/services app/ui/panel frontend/src tests` and `git diff -- app/agent app/services app/ui/panel frontend/src tests`.

## Status

- **Priority**: P0
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/002-secure-local-control-plane.md`
- **Category**: tech-debt + direction
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

Jarvis currently has many tools but the central executor only blocks repeated calls. `ActionExecutor.execute()` in `app/agent/action_executor.py:22-41` has no durable risk classification, approval state, undo contract or user-visible history. A professional assistant feels safe when it explains what it will do, obtains the right level of permission, and can show what happened afterwards.

## Current state

- `app/agent/tools/base.py` exposes only `name`, `description`, `critical` and `execute`.
- `app/agent/tools/registry.py:1-170` registers many desktop, browser, file, vision, automation and code tools without capability metadata.
- `app/agent/action_executor.py` invokes legacy tools directly; `app/agent/tool_guardrails.py` only protects loop/no-progress behavior.
- `app/agent/tools/planning_workspace.py` is the existing consent-aware model for opening a planning surface. Use its naming and `ToolResult` conventions.
- Plan 002 supplies server-side authorization receipts for privileged execution; consume it rather than recreating confirmation logic.

## Commands you will need

| Purpose | Command | Expected result |
|---|---|---|
| Core tests | `python -m pytest -q tests/test_action_kernel.py tests/test_actions.py tests/test_planning_workspace.py` | exits 0 |
| Regression tests | `python -m pytest -q tests/test_orchestrator.py tests/test_hacker_terminal.py` | exits 0 |
| Build | `Set-Location frontend; npm run build` | exits 0 |

## Scope

**In scope:** new `app/core/actions.py` and `app/storage/action_store.py`; `app/agent/action_executor.py`; `app/agent/tools/base.py`, `registry.py`, `planning_workspace.py`; a focused `app/ui/panel/api/actions.py`; minimal server registration; frontend action-preview/history components; targeted tests.

**Out of scope:** rewriting every existing tool; executing arbitrary user code; biometric authorization; mobile protocol changes; replacing the current chat model/tool-call format.

## Steps

### Step 1: Create typed action and policy contracts

Define immutable action records with ID, source, tool/capability, normalized arguments digest, risk (`observe`, `low`, `high`, `critical`), preview, status, timestamps, receipt reference, result summary and optional undo payload. Add tool metadata for capabilities, default risk and whether the action is reversible. Keep `critical` backward-compatible while migrating tools gradually.

**Verify**: unit tests serialize/deserialize records, reject unknown risk values and prove preview/result summaries redact sensitive fields.

### Step 2: Persist an append-only local action journal

Create a bounded local JSONL/SQLite-style store matching the project’s local-data conventions. It must support query by action ID/status/time, never retain secrets or full script bodies, and mark action transitions only through a valid state machine: `proposed → awaiting_confirmation → authorized → running → succeeded|failed|cancelled|expired`.

**Verify**: tests reject invalid transitions, keep action IDs stable, rotate/prune only old nonessential records, and return a correlation ID for diagnostics.

### Step 3: Route execution through proposal and authorization

Refactor `ActionExecutor` so a tool call first creates a proposal. Observational actions can execute directly and are journaled. Low-risk actions obey explicit per-user preferences. High/critical actions return a structured preview and require the server-side receipt created by Plan 002. Do not let the LLM manufacture an approval ID or elevate risk via arguments.

Add an optional undo handler contract. Start with safe, reversible actions only; when a tool has no real inverse, clearly show “sem desfazer”.

**Verify**: tests cover direct observation, low-risk preference, high-risk pending state, forged/expired receipt, execution failure and one reversible fixture action.

### Step 4: Turn workflows into declared, reviewable recipes

Make workflow definitions a small declarative local format: name, purpose, approved capabilities, ordered steps, variables, confirmation boundary and rollback/stop behavior. Validate them before registration. A workflow cannot invoke a tool outside its declared capability set, skip a required confirmation, or embed arbitrary executable code.

Implement two safe built-in examples only: “Planejamento semanal” (opens/updates the planning workspace) and “Encerrar o dia” (summarizes pending tasks without deleting data). Surface dry-run output before first execution.

**Verify**: tests reject undeclared tool calls, cycles and raw-script steps; dry-run produces no side effects; the two examples create expected action proposals.

### Step 5: Add the action preview and history surface

Create a compact panel component/API that shows proposed action, why, target, risk, confirmation choice, completion/failure and undo when supported. Use clear Portuguese; never say an action was completed before its record says succeeded. Integrate existing planning opt-in behavior with the same language.

**Verify**: frontend build succeeds; API tests verify history redaction, ownership/auth checks from Plan 002, approve/reject and undo visibility.

## Test plan

Create `tests/test_action_kernel.py` as the primary state-machine test. Follow `tests/test_planning_workspace.py` for consent behavior and `tests/test_hacker_terminal.py` only for command-policy regression. Use temporary storage; never invoke real applications, filesystem deletion, clipboard writes or shell execution.

## Done criteria

- [ ] Every newly migrated tool has explicit capability/risk metadata.
- [ ] High/critical actions are proposed, authorized server-side and journaled before execution.
- [ ] Workflows are declarative, validated and support dry-run.
- [ ] Action history is redacted and visible only to the authorized local principal.
- [ ] Targeted backend tests and frontend build pass.

## STOP conditions

- Plan 002 authorization receipts are not present or have no API for Action Kernel consumption.
- A tool cannot expose a safe preview without executing first.
- A requested undo would be misleading or destructive.

## Maintenance notes

New tools must declare metadata at registration time. Future proactivity and devices schedule Action Kernel proposals; they must never call legacy execution directly.
