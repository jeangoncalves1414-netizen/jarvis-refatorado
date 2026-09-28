# Plan 006: Isolar verificações, criar baseline de release e alinhar documentação

> **Executor instructions**: Tests must not alter the real user profile, clipboard, registry, media playback, network state or persistent `data/`. Preserve useful integration tests, but make them opt-in.
>
> **Drift check**: `git status --short -- tests README.md docs frontend package*.json pyproject.toml .github`.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests + dx + docs
- **Planned at**: commit `1861eae`, 2026-09-19

## Why this matters

The repository discovers 201 tests, but `tests/smoke_test.py:23-69` writes logs/preferences/clipboard/session history and triggers media control, while later checks use network and optional services. This makes a normal test run less repeatable and risky during development. Documentation also describes Flask and `/app/` even though the live panel is a Python `ThreadingHTTPServer` serving the React app at `/`.

## Current state

- Python uses pytest; `python -m pytest --collect-only -q` discovers 201 tests.
- The frontend has `npm run build` but no lint/test script in `frontend/package.json`.
- `tests/test_settings_api.py` is a good isolated temporary-server pattern.
- `tests/test_live_server.py` contacts a real app on port 8000; keep it manual/integration-only.
- `README.md:108` and `docs/IMPLEMENTATION_PLAN.md` promise files ≤300 lines; `docs/ARCHITECTURE.md` names Flask; `frontend/README.md:24` names `/app/`.

## Scope

**In scope:** test markers/configuration, tests that need isolation, minimal test helpers, CI workflow, `README.md`, `docs/ARCHITECTURE.md`, `frontend/README.md`, and developer commands.

**Out of scope:** refactoring product code (Plan 007); adding paid CI services; deleting manual integration tests; changing real user data.

## Steps

1. Add explicit pytest markers such as `unit`, `integration`, `live`, `network`, `hardware` and document the default safe command. Configure default test discovery to run only deterministic, isolated tests; keep opt-in commands for live/hardware checks.
2. Refactor smoke tests so they use `tmp_path`, mocks and dependency injection. Split real clipboard/media/browser/network checks into marked integration tests that are skipped unless an environment flag is set.
3. Stabilize or isolate tests that bind a fixed port, depend on installed services, or mutate `data/`. Use existing temporary `HTTPServer` fixture patterns and cleanup assertions.
4. Add a minimal GitHub Actions workflow (Windows or cross-platform appropriate to dependencies) that runs `python -m compileall -q app`, the safe pytest suite, and `npm ci`/`npm run build` in the frontend. Do not publish secrets or start hardware-dependent services.
5. Update README and architecture docs to state the actual server, current URL, supported start commands and separation between safe tests and integration tests. Mark the ≤300-line rule as a target being addressed by Plan 007, not a current fact.

**Verify**: `python -m pytest -q -m "not integration and not live and not network and not hardware"`; `python -m compileall -q app`; `Set-Location frontend; npm ci; npm run build`; and `git diff --check` all exit 0.

## Test plan

Run the safe suite twice in a clean temporary clone/worktree if available and assert no tracked files or user-data files changed. Verify `pytest --collect-only` lists markers appropriately, and use CI syntax validation where supported.

## Done criteria

- [ ] Default documented test command is safe and deterministic.
- [ ] Clipboard/media/network/live-server effects are opt-in integration tests.
- [ ] CI validates backend syntax, safe tests and frontend build.
- [ ] Operator documentation reflects the active server and route.

## STOP conditions

- A test can only pass by relying on a personal API key, user data or attached hardware.
- CI needs credentials or a non-redistributable local model.
- Documentation conflicts with a user-visible deployment contract that cannot be verified.

## Maintenance notes

Any new OS/network/hardware test must be marked before merge. Keep the fast suite a release gate; run integrations separately when the user intentionally tests local capabilities.
