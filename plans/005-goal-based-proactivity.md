# Plan 005: Tornar a proatividade orientada a objetivos e consentimento

> **Executor instructions**: This plan changes behavior visible to the user. Make every proactive policy explicit, pausable and reversible. Proactivity may propose work through Action Kernel; it must not secretly execute high-risk work.
>
> **Drift check**: `git status --short -- app/services/proactive.py app/agent app/ui/panel frontend/src tests`.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/003-action-kernel-and-workflows.md`, `plans/004-mission-control-and-operational-observability.md`
- **Category**: direction
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

Current proactivity is a useful collection of reminders, briefings, habit alerts and topic polling. It does not yet have a durable model of a user goal, when an intervention is welcome, what has already been suggested or what may happen automatically. Goals and consent make Jarvis feel attentive without becoming noisy or surprising.

## Current state

- `app/services/proactive.py` persists briefing configuration, reminders, topics and session summaries, then a daemon checks them every 15 seconds.
- `check_monitored_topics_updates()` performs searches in a loop and suppresses failures; `generate_briefing_text()` combines many features directly.
- `app/agent/tools/planning_workspace.py` is the current planning surface and supports explicit auto-open consent.
- Plans 003–004 establish action proposal state and Mission Control visibility.

## Scope

**In scope:** a small goal/goal-policy store, proactive scheduler refactor or adapters, planning workspace integration, focused APIs/UI, Action Kernel integration and tests.

**Out of scope:** autonomous purchases/messages/deletions; background microphone/camera monitoring; cloud account sync; behavioral scoring; face/speaker identification changes.

## Steps

1. Define a goal model: title, desired outcome, horizon, milestones, current next action, evidence/progress, cadence, quiet hours, intervention policy and status. Store it locally and make it profile-scoped.
2. Create explicit consent presets: ask every time, auto-open planning workspace for planning only, notify-only, paused. The plain-language UI must show the exact capability each preset grants; never infer broad autonomy from a sentence.
3. Convert existing reminders, habits and monitored topics into normalized signals. Deduplicate by signal ID/window, enforce rate limits/quiet hours and record why a suggestion was emitted or suppressed.
4. On a relevant signal, create an Action Kernel proposal: e.g. “open the weekly plan”, “draft next study block”, or “show goal review”. No high-risk tool execution may be proposed with pre-approved execution.
5. Add Goal view to Mission Control: active goals, next steps, last intervention, pause/delete controls and a weekly review. Reuse the planning workspace for elaboration, preserving its explicit auto-open preference.
6. Add a small user feedback loop: helpful/not helpful/snooze. Use feedback only to adjust cadence/preferences; show the changed preference and allow reset.

**Verify after steps 1–4**: `python -m pytest -q tests/test_proactive_goals.py tests/test_planning_workspace.py tests/test_action_kernel.py`. **Verify UI**: `Set-Location frontend; npm run build`.

## Test plan

Create `tests/test_proactive_goals.py` with injected clock and temporary stores. Cover goal lifecycle, profile isolation, quiet hours, deduplication, consent modes, snooze, repeated daemon cycles and proposal-not-execution behavior. Extend the existing proactive concurrency tests only if they remain deterministic.

## Done criteria

- [ ] User can create, pause, resume and remove a goal and inspect its next action.
- [ ] Every proactive suggestion has a recorded signal/reason and respects consent/quiet hours.
- [ ] Planning auto-open happens only under the narrow, explicit saved preference.
- [ ] No proactive path directly executes a high/critical action.
- [ ] Backend tests and frontend build pass.

## STOP conditions

- A signal cannot be generated without collecting sensitive ambient data.
- Existing behavior relies on global, non-profile-scoped preferences that cannot be migrated safely.
- A feature request needs user messaging, purchase or device execution beyond the Action Kernel policy.

## Maintenance notes

Future “Jarvis noticed…” features must enter through signals → policy → proposal. This is the foundation for future home/device context without granting invisible autonomy.
