# Implementation Plan: estudos, fases 1 e 2

Repo: `c:\Users\maria\Desktop\Jarvis`, branch `main` (base `7cab802`, clean). Work in place, no worktree. Small commits, no push.
Source review: `c:\Users\maria\.gemini\antigravity\brain\f3c96c07-b79b-4bfa-b620-73a69d9f3812\review-study-system.md`.
Scope: 1.1-1.8, 2.1-2.7, 6.5, 6.8, item 9. Phases 3-6 are out of scope.

FEAT artifacts (same content, split for the coder steps): `.agents/tasks/estudos-fases-1-2/task-estudos-fases-1-2/`.

## Ground rules for every step

- `.agents/tasks/` is tracked by git. Stage files by name and never stage anything under `.agents/tasks/estudos-fases-1-2/`.
- Do not touch `app/services/memory_*`, habit or lifestyle code, or `mobile_app/`. Never run `npm run build:mobile`.
- Tests use temporary dirs only. Never read or write `c:\Users\maria\Desktop\Jarvis\data`.
- UI text in Brazilian Portuguese. Write files as UTF-8 with the edit tools, not PowerShell `Set-Content` (it produces mojibake, and `frontend/tests/broken-text.cjs` fails on it).
- Python tests: `python -B -m pytest -q -p no:cacheprovider --tb=short <files>`.
- Frontend checks, run in `frontend/`: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` and `npm run build`.

## Verification of the review's claims (current code at 7cab802)

| Item | Status | Evidence |
|---|---|---|
| 1.1 language mode not wired | Confirmed, and wider than reported | `orchestrator.py:458` only branches on `mode == "tutor"`, so `language` falls into the general prompt. The registry also checks `mode != "tutor"` at lines 393, 400 and 437. Fixing only the prompt would still give language mode the MCP tools, the Groq core list and the video routing. The racing exclusion at `orchestrator.py:1184` does not list `language`. `resolve_active_mode` passes explicit modes through unchanged. `loop_policy._LOOP_MODES` already excludes `language`. |
| 1.2 language tools inside TUTOR_TOOL_NAMES | Confirmed | `registry.py:169-173`. No catalog entries exist for the language or tutor tools. They run on the `BaseTool.metadata` fallback: low risk, capability = tool name. |
| 1.3 wrong field names | Confirmed | `LanguagePage.tsx` reads `stats.vocabulary_count` (on home and progress), `stats.pronunciation_attempts` and `stats.conversations`. The backend writes `total_vocab`, `pronunciation_sessions` and `conversation_sessions` (`language_store.py` DEFAULT stats). |
| 1.4 retrievability always 1.0 | Confirmed, plus one more bug | `fsrs.py` returns `retrievability(stability, 0)`. Elapsed time is measured from the old `due` date, not from `last_review`, so the pre-review R is also wrong. |
| 1.5 no grade validation / no cap | Confirmed, but the fix differs | Any grade outside 0-2 falls into the EASY branch. The API also does `int(payload.get("grade", 2))`: a missing grade becomes "Good" and a non-numeric one raises a 500. The cap belongs on the interval (FSRS `maximum_interval=365`), not on stability. |
| 1.6 `utterance.lang = 'en-US'` | Confirmed | `LanguagePage.tsx` `speakPhrase`. `useLanguage.startPronunciation` passes raw codes such as `es` (not BCP-47). Placeholders and the empty-state copy also hardcode English ("Palavra em inglês", "Type in English…", "Converse em inglês"). |
| 1.7 vocabIndex not reset | Confirmed, and the bug is worse than reported | After a review the card leaves the due list on refresh, and the index is also incremented. The result is that every other card is skipped and the queue ends early. `useStudy.reviewCard` has the same bug. |
| 1.8 Promise.all | Confirmed | `useLanguage.refreshLanguage`. |
| 2.x features | Missing, as described | No undo, no review log, no learning steps, no stats API. Shadowing UI posts to the pronunciation endpoint, and `log_shadowing_session` discards text, score and speed. No conversation endpoint. No vocabulary delete. |
| Gamification "invisible" | Partly wrong | The LanguagePage home already shows streak and daily XP. Tutor XP is invisible because `TutorStore.add_xp` is never called. |
| XP inconsistent | Confirmed | Tutor keeps XP in top-level keys with goal 100. Language keeps it in `stats` with goal 50. Tutor reviews award 0 XP. The displayed streak is never broken until the next study day, and `daily_xp` shows yesterday's value until XP is earned today. |
| `srs.py` "not imported anywhere" | Wrong claim | `app/storage/tutor/__init__.py` imports it and re-exports SM-2 `apply_review`. Nothing imports the package-level name, so it is effectively dead but loaded. |
| `language_store` double save | Confirmed (harmless) | `review_vocabulary` calls `add_xp` (which saves) and then `_save`. This goes away once XP moves to the service. |
| `tutor_store` ID collision | Partly wrong | `fc-{len+1}` is safe because flashcards are never deleted or truncated. `fy-` (capped at 50) and `as-` (capped at 30) do collide after the cap. This is out of scope: record it, do not fix it. |
| 6.8 listener leak | Confirmed | The `dragover` arrow function is never removed. The handlers are recreated every render and listed as effect deps, so the effect re-subscribes on every render and one `dragover` listener is added per render. |
| 9 Pomodoro | Confirmed, plus more | The SVG CSS is dead, and `.pomodoro-container` does not match the `pomodoro-timer` class. The conic-gradient draws a pie because the inner part has no mask. Pause sets `idle` and Start resets to the full time. `onComplete` and `setState` run inside a `setSecondsLeft` updater, so they fire twice under the `StrictMode` in `main.tsx`; once XP is wired, that would double-award it. |
| 6.5 shortcuts | Missing | Neither review panel handles keys. |

## Decisions

1. **Scheduler: use py-fsrs (`fsrs` 6.3.2, MIT, Python >=3.10, single dependency `typing-extensions`; PyPI upload 2026-08-09) behind the existing module `app/storage/tutor/fsrs.py`.** Fixing the hand-rolled code would mean re-implementing FSRS-6 (21 weights, Learning/Review/Relearning, steps, power forgetting curve) and owning its correctness. The maintained package already provides all of that, plus retrievability, `maximum_interval` and JSON serialization. Add `"fsrs>=6.3,<7"` to `pyproject.toml` and install with `python -m pip install "fsrs>=6.3,<7"`. Keep the public functions `apply_review`, `is_due`, `retrievability`, `GRADE_*` and `ReviewResult` so both stores keep a single scheduler. Scheduler config: `desired_retention=0.9`, `learning_steps=(1 min, 10 min)` (the Anki/py-fsrs default; the review's "1m→10m→1h" was only an example, and a 1 h step usually falls outside the session), `relearning_steps=(10 min,)`, `maximum_interval=365`, `enable_fuzzing=False` (deterministic, testable). py-fsrs uses UTC only. Store `due` and `last_review` as ISO UTC datetimes.
2. **Compatibility and migration are lazy and never drop data.** `normalize_card(card)` adds `state`/`step` without deleting legacy keys (`ease`, `interval` stay).
   - A card with `reps == 0`, `lapses == 0` and no `last_review` becomes `state="new"` (fsrs Learning step 0, with stability and difficulty ignored).
   - Any other legacy card becomes `state="review"`, with:
     - `stability` = clamp(old stability or interval, 0.1, 365);
     - `difficulty` = clamp(old difficulty, 1, 10) (same 1-10 scale);
     - `last_review` = the old date, or else `due - max(1, interval)` days;
     - `due` = the old date at local midnight converted to UTC, so existing schedules keep their day.
   - The migrated values are persisted only when the card is next reviewed. Reads return normalized copies.
   - `is_due` accepts both formats. Date-only strings use the old local-date comparison. Review-state cards are due when their due *local date* is today or earlier (Anki day semantics). Learning and relearning cards are due when `due <= now`. New cards are always due.
3. **Grades.** The public scale stays 0-3 (UI buttons and tools) and maps to fsrs `Rating` 1-4. `validate_grade` accepts only an int (not bool) in {0,1,2,3}, otherwise `ValueError`. The APIs return `400 {"ok": false, "error": "invalid_grade"}`, including when the grade is missing (no silent default).
4. **Retrievability.** `ReviewResult.retrievability` is R *before* the review, from the scheduler's power curve with elapsed = now - `last_review`. It is `None` for new cards. It is written to the card and to the review log.
5. **Review log.** Each store keeps an append-only JSONL file `<storage_dir>/review_log.jsonl` (class `ReviewLog` in `app/storage/tutor/review_log.py`, with a lock).
   - Each review entry holds: `id`, `type:"review"`, `deck`, `card_id`, `grade`, `rating`, `reviewed_at` (UTC), `local_date`, `state_before`, `state_after`, `retrievability_before`, `interval_days`, `xp`, a `before` snapshot (the exact raw scheduling keys from before normalization, plus the list of keys that were absent) and an `after` snapshot.
   - Undo appends `{type:"undo", target:<review id>}`. Entries are never edited. Stats ignore undone reviews.
6. **Undo (2.5).** `undo_last_review()` takes the latest non-undone review of that deck and checks two things:
   - the card still exists, otherwise 409 `card_not_found`;
   - its scheduling keys equal the `after` snapshot, otherwise 409 `stale`.
   If both hold, it restores the `before` snapshot exactly (sets the present keys, deletes the absent ones), revokes that review's XP on its original day and appends the undo entry. Undo can be repeated, newest first. With nothing to undo it returns 404 `nothing_to_undo`.
7. **Unified XP/streak (2.3, 2.7).** New `app/storage/study_xp.py`.
   - The `StudyXP(dir)` file is `<dir>/xp.json`, with keys `daily{date: xp}`, `daily_goal`, `counters{pomodoros}`, `legacy_streak{count,last_date}` and `imported_sources`.
   - `get_study_xp(path)` caches one instance per resolved path, so tutor and language share one object. It is thread-locked. It never writes on construction or read, only on mutation.
   - Path rule: a store built with `storage_dir=None` uses `data/study`; a store built with a custom dir uses `<storage_dir>/study`, unless an `xp=` instance is injected. The orchestrator passes `tutor_store.xp` to the default `LanguageStore`.
   - Streak and best streak are computed on read from consecutive active days, plus the seeded legacy streak days. A missed day therefore shows 0 immediately, and undo stays consistent. `daily_xp` is `daily[today]`.
   - Legacy import is idempotent per source (`tutor`, `language`): totals are summed, `daily[last_study_date] += daily_xp`, the streak with the most recent date wins, and the goal is the max of the legacy goals (default 100).
   - XP amounts: review (both decks) 10, pronunciation 15, conversation 25, shadowing 20, Pomodoro focus block 20. The Pomodoro endpoint accepts minutes in 5..90.
   - Levels: threshold(n) = 50·n·(n-1). Names in order: Iniciante, Aprendiz, Estudante, Dedicado, Focado, Avançado, Expert, Mestre, Sábio, Lenda; after level 10 the name is "Lenda N".
   - Badges are derived, not stored: Primeira revisão, 100 revisões, Sequência de 7 dias, Sequência de 30 dias, 1.000 XP, 10 Pomodoros, 50 palavras.
   - The store methods `add_xp` and `get_streak_info` stay as thin delegates. Legacy keys in the progress files are left untouched.
8. **Study API.** New `app/ui/panel/api/study.py`, registered in both handler tuples in `server.py`. It returns `None` for paths it does not own: `/api/study/categories|trash` are handled earlier in `server.py` and must keep working.
   - `GET /api/study/dashboard`: due counts, `next_due_at`, XP, level, badges.
   - `GET /api/study/stats`: a 371-day heatmap of reviews and XP; daily reviews for the last 30 days per deck; retention = share of review-state reviews in the last 30 days not graded Again (`null` if there are none); state distribution per deck and total; totals.
   - `POST /api/study/pomodoro`.
   - Deck endpoints follow the existing `POST …/{id}/delete` convention (`api/checklists.py`): `POST /api/tutor/flashcards/undo`, `POST /api/language/vocabulary/undo`, `POST /api/language/vocabulary/{id}/delete`, `POST /api/language/shadowing`, `POST /api/language/conversation`.
   - Due lists return learning/relearning cards first (ordered by due), then review, then new, plus `next_due_at` (the earliest future learning due time today).
9. **Language mode (1.1, 1.2).**
   - `orchestrator.py` gets an `elif mode == "language"` branch that calls `build_language_system(...)` with the target and native language, CEFR level, weak phonemes and `get_summary_for_llm()`. Like tutor, it gets no memory, persona or situational block.
   - `LANGUAGE_TOOL_NAMES` = the four `language_*` tools, removed from `TUTOR_TOOL_NAMES`.
   - The registry uses `STUDY_MODES = {"tutor", "language"}` wherever it now checks `mode != "tutor"`. `language` is added to the racing exclusion.
   - Prompt rule 9 ("use the whiteboard") is reworded to markdown tables or lists, because the language conversation UI has no whiteboard and no whiteboard tools.
   - `TOOL_CATALOG` gets entries for the four language tools and for `tutor_save_progress`, `tutor_add_flashcard`, `tutor_save_feynman` and `enem_save_question` (`("study", …)`, low risk, effect, reversibility and scope in Portuguese). `inventory.py` gets a `language` column.
10. **Frontend.**
    - Dashboard "Hoje" (2.1) replaces the content of the existing `plan` mode in `StudyPage`; `navigation.ts` is unchanged. Progress (2.2) is the existing `progress` mode, drawn in plain SVG/CSS because `package.json` has no chart library.
    - One `PomodoroTimer` stays mounted in `StudyPage` (it is removed from the LanguagePage home) so switching modes does not kill a running timer.
    - The vocabulary delete uses the app's `components/ConfirmDialog.tsx` (`danger`). Its own comment says it replaces `window.confirm`.
    - Review queues always show the first due card: the index is reset to 0 on refresh. After an undo the restored card is selected.
    - Shortcuts: Space/Enter flips; 1-4 grade, only after the answer is shown; `z` or Ctrl+Z undoes. They are ignored in inputs, textareas, selects and contenteditable elements.
11. **`srs.py`.** Delete it and repoint `app/storage/tutor/__init__.py` to the fsrs module. This avoids a silent SM-2 import path.

## Ordered items

- [ ] 1. Language mode routing and tool isolation (1.1, 1.2). (FEAT-001)
      In `app/agent/orchestrator.py`, import `build_language_system`, add the language branch and add `language` to the racing exclusion. In `app/agent/tools/registry.py`, add `LANGUAGE_TOOL_NAMES` and `STUDY_MODES` and update the mode checks. Reword prompt rule 9 in `app/agent/modes/language.py`. Add the catalog entries in `app/agent/tools/catalog.py`. Add the language column in `app/agent/tools/inventory.py`.
      Tests:
      - new `tests/test_language_mode.py`: the system prompt contains the language tutor text, level and target language and no "Situação agora"; `get_tool_declarations` and `allowed_tool_names(mode="language")` equal the registered language tools for gemini and groq; tutor has no `language_*` tools; no MCP tools in language mode.
      - `tests/test_turn_tool_allowlist.py`: add a language case.
      - `tests/test_tool_catalog.py`: every study-mode tool is in the catalog and not critical.
      Files: app/agent/orchestrator.py, app/agent/tools/registry.py, app/agent/modes/language.py, app/agent/tools/catalog.py, app/agent/tools/inventory.py, tests/test_language_mode.py, tests/test_turn_tool_allowlist.py, tests/test_tool_catalog.py
      Verify: `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_language_mode.py tests/test_turn_tool_allowlist.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_tools_smoke.py tests/test_orchestrator_enem.py tests/test_situational_context.py` passes.
      Commit: `feat(agent): conecta modo language ao prompt CEFR e isola ferramentas de idiomas`.

- [ ] 2. py-fsrs scheduler, migration, review log and undo (1.4, 1.5, 2.4, 2.5 backend). (FEAT-002; depends on nothing)
      - Install `fsrs` and add it to `pyproject.toml`. Rewrite `app/storage/tutor/fsrs.py` as an adapter: `validate_grade`, `normalize_card` (migration), `apply_review(card, grade, now=None, today=None)` returning `ReviewResult` with interval, ease, reps, lapses, due, difficulty, stability, retrievability, state, step and last_review, plus `is_due(card, now=None, today=None)`, `retrievability(stability, days)` and `sort_due`.
      - Add `app/storage/tutor/review_log.py`. Delete `srs.py` and repoint `__init__.py`.
      - In `tutor_store.py` and `language_store.py`: use `normalize_card`, snapshot before review, append the log entry, and add `undo_last_review()`.
      - In both APIs: return 400 on an invalid grade, add the undo endpoints, and add `next_due_at` to the due lists.
      - Rewrite `tests/test_fsrs.py`. It currently encodes the hand-tuned behaviour, for example "Again on a new card → due tomorrow, lapses=1", which real FSRS does not do. Cover: grade validation (5, -1, True, "2", None rejected); learning steps (new+Good → learning, due in about 10 min; Good again → review, ≥1 day; Again → step 0, about 1 min); lapse → relearning, lapses+1; interval ≤ 365 after 30 Easy reviews; retrievability pre-review in (0,1) for a reviewed card and None for new; migration of legacy SM-2 and old FSRS-lite cards keeps the due day and keeps the legacy keys; `is_due` for both formats.
      - New `tests/test_review_undo.py`: exact restore including absent keys, XP revoked, repeated undo, 404, 409 stale and 409 deleted, log entries never rewritten.
      - Update `tests/test_tutor_store.py::test_add_and_review_flashcard` and `tests/test_language_store.py::test_reviewed_card_not_immediately_due` for learning steps (Easy graduates; Good stays in learning, due today). Extend `tests/test_panel_tutor_api.py` with invalid-grade 400 and undo, and inject a tmp `LanguageStore` into its fixture.
      Files: pyproject.toml, app/storage/tutor/fsrs.py, app/storage/tutor/review_log.py, app/storage/tutor/__init__.py, app/storage/tutor/srs.py (delete), app/storage/tutor_store.py, app/storage/language_store.py, app/ui/panel/api/tutor.py, app/ui/panel/api/language.py, tests/test_fsrs.py, tests/test_review_undo.py, tests/test_tutor_store.py, tests/test_language_store.py, tests/test_panel_tutor_api.py
      Verify: `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_fsrs.py tests/test_review_undo.py tests/test_tutor_store.py tests/test_language_store.py tests/test_panel_tutor_api.py` passes.
      Commits: `feat(estudos): agenda FSRS real (py-fsrs) com learning steps e migração de cards` and then `feat(estudos): log imutável de revisões e desfazer última revisão`.

- [ ] 3. Unified XP/streak service, stats/dashboard API, Pomodoro XP and wiring endpoints (2.1-2.3, 2.6, 2.7 backend). (FEAT-003; depends on 2)
      - Add `app/storage/study_xp.py` (StudyXP, `get_study_xp`, levels, badges, legacy import) and `app/storage/study_stats.py` (`build_dashboard(tutor, language)` and `build_stats(tutor, language)` from the stores and review logs).
      - Make both stores take `xp=`, award XP through it (tutor review +10) and drop the in-store streak math, keeping thin delegates.
      - In `language_store`: add `delete_vocabulary`; store shadowing entries in `shadowing_history` (last 100, with text, score, speed and date); validate the conversation fields. The language dashboard and LLM summary read XP from the service.
      - Orchestrator: pass `xp=self.tutor_store.xp` to the default `LanguageStore`.
      - Add `app/ui/panel/api/study.py` and register it in `server.py`. Add the language delete, shadowing and conversation routes.
      - Tests:
        - `tests/test_study_xp.py`: add/revoke; daily reset on read; streak continues, breaks and shows 0 after a missed day; best streak; legacy import idempotent and summed; goal; level boundaries; badges.
        - `tests/test_study_api.py`, an HTTP fixture copied from `tests/test_panel_tutor_api.py` with tmp tutor, language and xp stores: dashboard and stats shapes with non-zero values after reviews; retention `null` and then a value; states; pomodoro 200 and 400 for 2 or 200 minutes or a non-int; vocabulary delete 200 and 404; shadowing and conversation saved with XP; `/api/study/categories` still served.
        - Update `tests/test_language_store.py::test_dashboard_defaults` (goal 100).
      Files: app/storage/study_xp.py, app/storage/study_stats.py, app/storage/tutor_store.py, app/storage/language_store.py, app/agent/orchestrator.py, app/ui/panel/api/study.py, app/ui/panel/api/language.py, app/ui/panel/server.py, tests/test_study_xp.py, tests/test_study_api.py, tests/test_language_store.py
      Verify: `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_study_xp.py tests/test_study_api.py tests/test_language_store.py tests/test_tutor_store.py tests/test_review_undo.py tests/test_fsrs.py tests/test_panel_tutor_api.py tests/test_language_mode.py` passes.
      Commit: `feat(estudos): XP/sequência unificados, API de painel e estatísticas, endpoints de idiomas`.

- [ ] 4. Frontend fixes, review shortcuts, undo UI and language wiring (1.3, 1.6-1.8, 6.5, 6.8, item 9, 2.5 UI, 2.6 UI). (FEAT-004; depends on 2 and 3)
      - Add `frontend/src/utils/speechLang.ts` (BCP-47 map and Portuguese language names). Add `frontend/src/hooks/useReviewShortcuts.ts`.
      - `useLanguage.ts`:
        - `allSettled`, index reset, `undoVocabReview`, vocabulary list, `deleteVocabulary`, `endConversation`;
        - shadowing posts to `/api/language/shadowing`.
      - `useStudy.ts`: index reset and `undoReview`.
      - `LanguagePage.tsx`:
        - field names, dynamic `utterance.lang` and copy;
        - shortcuts, undo button, "MINHAS PALAVRAS" list with delete through `ConfirmDialog`;
        - "Encerrar conversa" button; Pomodoro removed from home.
      - `StudyPage.tsx`: leak fix (named handlers inside the effect, callbacks through a ref, deps `[activeMode]`), shortcuts and undo in review, a single always-mounted Pomodoro dock.
      - `PomodoroTimer.tsx`: SVG ring; pause and resume keep phase and time (deadline-based); Reiniciar; `onComplete` fired once from an effect; `+5 min` extends the total.
      - CSS in `styles.css`: `.pomodoro-container` becomes `.pomodoro-timer`, plus time, label, count and dock styles. Types in `types.ts`.
      Files: frontend/src/utils/speechLang.ts, frontend/src/hooks/useReviewShortcuts.ts, frontend/src/hooks/useLanguage.ts, frontend/src/hooks/useStudy.ts, frontend/src/pages/LanguagePage.tsx, frontend/src/pages/StudyPage.tsx, frontend/src/components/study/PomodoroTimer.tsx, frontend/src/styles.css, frontend/src/types.ts
      Verify: `tsc --noEmit` and `npm run build` pass, and `git status mobile_app` is clean.
      Commit: `fix(estudos): corrige campos, voz, fila de revisão, listeners e Pomodoro; atalhos e desfazer`.

- [ ] 5. Study dashboard "Hoje", progress visuals, visible gamification, Pomodoro XP and the Playwright smoke test (2.1, 2.2, 2.3, 2.7 UI). (FEAT-005; depends on 3 and 4)
      - Add `frontend/src/hooks/useStudyStats.ts` (allSettled fetch of dashboard and stats, `refresh`, `awardPomodoro`).
      - Add `components/study/StudyDashboard.tsx`:
        - due flashcards and vocabulary, next learning card countdown, streak with pop animation, daily XP bar and "Meta do dia batida!", level bar;
        - quick buttons: the existing six plus "Revisar vocabulário", which opens LanguagePage on the vocab tab through a new `initialTab` prop.
      - Add `components/study/StudyProgress.tsx`: SVG heatmap of 53×7 cells with tooltips by date; 30-day stacked bars for tutor and language; retention %; stacked state bar with legend Novos/Aprendendo/Revisão/Reaprendendo; badge grid.
      - StudyPage wiring: refresh stats after reviews, undo, language actions and Pomodoro. Pomodoro `work` completion calls `POST /api/study/pomodoro` and shows the notice "Pomodoro concluído! +20 XP". Add CSS.
      - New `frontend/tests/study.smoke.cjs`, following the pattern of `frontend/tests/today.smoke.cjs` and `frontend/tests/workspace.smoke.cjs`: `PLAYWRIGHT_MODULE`, a stateful mocked `/api/**`, localStorage `jarvis-active-screen='Estudos'`, `page.clock` to fast-forward the Pomodoro, `broken-text.cjs`. It saves screenshots of: dashboard, progress view, review with a keyboard grade, after undo, and the language Progress tab with non-zero values.
      Files: frontend/src/hooks/useStudyStats.ts, frontend/src/components/study/StudyDashboard.tsx, frontend/src/components/study/StudyProgress.tsx, frontend/src/pages/StudyPage.tsx, frontend/src/pages/LanguagePage.tsx, frontend/src/types.ts, frontend/src/styles.css, frontend/tests/study.smoke.cjs
      Verify:
      1. `tsc` and `npm run build` pass.
      2. Start `npm run dev -- --host 127.0.0.1 --port 5174` in the background.
      3. Run `$env:PLAYWRIGHT_MODULE='C:\Users\maria\AppData\Local\Programs\Python\Python311\Lib\site-packages\playwright\driver\package'; $env:PANEL_TEST_URL='http://127.0.0.1:5174'; $env:PANEL_TEST_OUTPUT='c:\Users\maria\Desktop\Jarvis\.agents\tasks\estudos-fases-1-2\screenshots'; node tests/study.smoke.cjs`. It exits 0 and the screenshots exist.
      4. Stop Vite.
      Commit: `feat(estudos): painel Hoje, progresso visual, gamificação e XP do Pomodoro`.

- [ ] 6. Integration verification, graphify and the report (final step).
      - Run the full targeted Python list, `tsc`, `npm run build` and the smoke test. Then run `graphify update .`.
      - Write `docs/estudos-fases-1-2-2026-11-11.md` in Portuguese. It covers: what changed; decisions, including the FSRS choice (license, version, migration); the wrong review claims from the table above; verification evidence (commands, counts, screenshot paths); what was not verified (real backend with personal data, real speech APIs, real LLM provider in language mode); and a copy of the Phase 1/2 checklist plus 6.5, 6.8 and 9 with the completed items ticked.
      Commit: `docs(estudos): relatório das fases 1 e 2`.

## Gaps and assumptions

- Pronunciation phrases stay English-only (Phase 3.4). The new speech language mapping makes TTS and STT follow the target language, but the phrase list does not change.
- Conversation logging is triggered by the user ("Encerrar conversa"). `corrections` and `new_vocab` are sent as 0 and [] because only the model knows them; no new tool is added.
- A review undone after the vocabulary card was deleted returns 409. Deleted cards' review entries still count in stats.
- `refreshStudy` in `useStudy.ts` still uses `Promise.all`. It is out of the stated scope (1.8 names only `refreshLanguage`); record it in the report.
