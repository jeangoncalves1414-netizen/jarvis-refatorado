# Plan 001: Unificar rotas de provedores e exibir o motor efetivo

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 1861eae..HEAD -- .env .env.example app/config.py app/storage/runtime_settings.py app/services/llm.py app/agent/prompts.py app/agent/orchestrator.py app/ui/panel/api/settings.py frontend/src/pages/SettingsPage.tsx frontend/src/App.tsx frontend/src/types.ts tests`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1
- **Effort**: M/L (roughly 2–4 days including tests and manual UI verification)
- **Risk**: MED
- **Depends on**: none
- **Category**: bug + tech-debt
- **Planned at**: commit `1861eae`, 2026-08-05

## Why this matters

The settings screen currently shows several independently selected values, but
the user cannot tell which route actually handles chat. In the current `.env`,
`LLM_PROVIDER` appears twice (`.env:4` and `.env:16`); `python-dotenv` keeps the
first value, so the effective route is Groq even though the later line says
Oxyy. The Oxyy model selector is also only a model catalog; it does not activate
Oxyy chat by itself. Finally, the assistant prompt contains no effective
provider/model metadata, so a model can answer that it is GPT-4 without any
runtime evidence. This plan makes one route explicit per capability and makes
the chat identity truthful.

## Current state

### Repository and verification conventions

- Python backend under `app/`; React/Vite frontend under `frontend/`.
- Backend tests use pytest under `tests/`; frontend verification is
  `npm run build` from `frontend/`.
- The last known clean baseline for the touched work was `python -m compileall -q app`,
  `npm run build`, and the targeted provider/voice tests. A full `pytest -q`
  run previously exceeded one minute and was terminated, so do not use that as
  the only gate.
- Existing API handlers are plain functions returning `(status, dict)`; match
  that style in `app/ui/panel/api/settings.py`.
- Existing React settings are prop-driven; match the patterns in
  `frontend/src/pages/SettingsPage.tsx` and `frontend/src/App.tsx`.

### Evidence of the route ambiguity

- `.env:4` and `.env:16` both define `LLM_PROVIDER`. Do not copy any secret
  values from `.env` into source, plans, logs or tests. Keep exactly one
  non-secret provider declaration after the migration.
- `app/config.py:80-82` loads `LLM_PROVIDER`, `GEMINI_MODEL` and `GROQ_MODEL`
  into separate fields. `app/config.py:97-117` then overlays persistent
  selections from `data/runtime_settings.json` for the provider and Oxyy
  capability models.
- `app/storage/runtime_settings.py:41-59` persists only one `llm_provider`,
  while `:74-113` persists Oxyy models in a separate object. This split is the
  reason the UI can show a selected Oxyy chat model while the active provider is
  still Groq.
- `app/services/llm.py:84-96` resolves the provider and silently changes
  Gemini to Groq when Gemini has no key. There is no equivalent explicit status
  object explaining that fallback to the UI.
- `app/services/llm.py:176-193` dispatches chat by provider; Oxyy uses the
  selected `oxyy_chat_model` at `:223-234`, Groq uses `groq_model`, and Gemini
  uses `llm_model` at `:324`.
- `app/ui/panel/api/settings.py:18-57` exposes three separate settings
  endpoints. `/api/settings/llm` returns only provider booleans through
  `get_llm_settings`; `/api/settings/oxyy` returns capability models but does
  not identify whether Oxyy is active for chat.
- `app/storage/runtime_settings.py:63-71` confirms the LLM response only has
  `llm_provider` and configured flags, not the effective model, fallback chain,
  or reason for a fallback.
- `frontend/src/pages/SettingsPage.tsx:62-72` renders Gemini, Groq and Oxyy as
  provider cards, while `:74-92` separately renders Oxyy model selectors for
  chat, TTS, STT, image, video and embeddings. The labels do not say that the
  Oxyy chat selector is inactive unless Oxyy is the selected LLM provider.
- `frontend/src/App.tsx:95-130` and `:364-367` update TTS, STT, Oxyy models and
  LLM provider through independent calls, so there is no single route update
  that can be displayed consistently.
- `app/agent/orchestrator.py:368-382` builds the system prompt using the active
  provider only to choose the function-calling style. It does not pass the
  effective provider/model into the prompt.
- `app/agent/prompts.py:7-18` and `:69-112` define persona and behavior but do
  not provide a factual “you are running on provider X/model Y” context.

## Target design

Use a capability-oriented route object, with exactly one primary route and an
optional ordered fallback list for each capability:

```text
chat:      { primary: {provider, model}, fallback: [{provider, model}], policy }
tts:       { primary: {provider, model, voice}, fallback: [...] }
stt:       { primary: {provider, model}, fallback: [...] }
image:     { primary: {provider, model}, fallback: [...] }
video:     { primary: {provider, model}, fallback: [...] }
embedding: { primary: {provider, model}, fallback: [...] }
```

The backend must return both `configured` and `effective` information. The
frontend must show “Ativo agora” for the effective route, “fallback” for a
standby route, and “não configurado” when a key is missing. Selecting an Oxyy
model changes the Oxyy route model; it does not silently change the chat
provider. Selecting the chat provider is a separate, prominent single-choice
operation. Fallbacks must be visible and deterministic; no provider may be
silently substituted without appearing in the returned status.

When the user asks “quem é você?” or similar, the system prompt should include
an internal factual context such as “Motor ativo: Oxyy; modelo: gemini-2.5-flash;
rota: principal” generated from the backend resolver. The assistant may state
that fact, but must not claim a model that is not in that context.

## Scope

**In scope (only these files may be modified by the executor):**

- `.env` and `.env.example` (remove duplicate provider declarations and document
  the canonical route configuration; never expose key values)
- `app/config.py`
- `app/storage/runtime_settings.py`
- `app/services/llm.py`
- `app/agent/prompts.py`
- `app/agent/orchestrator.py`
- `app/ui/panel/api/settings.py`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/types.ts`
- `frontend/src/styles.css` (only settings/status styles)
- `tests/test_llm_provider.py` and new provider-route tests under `tests/`

**Out of scope:**

- Rotating or printing any API key; if a committed credential is discovered,
  stop and report its location/type so it can be rotated separately.
- Rewriting the chat transport, tool registry, voice streaming, cinema, study,
  identity or mobile bridge features.
- Implementing new Oxyy video-generation or embeddings consumers. This plan
  only makes their routes truthful and ready for those consumers.
- Changing provider SDK versions or adding a new provider.

## Steps

### Step 1: Normalize configuration precedence and migrate the duplicate `.env`

1. Remove the duplicate `LLM_PROVIDER` declaration from `.env`; preserve the
   user's intended provider only after checking the current runtime selection in
   `data/runtime_settings.json`. Do not delete or rewrite any key line.
2. Keep `.env.example` as a single-source template with one `LLM_PROVIDER`,
   one model variable per native provider, and Oxyy capability model variables.
   Add a short comment that the Oxyy capability model is used only when Oxyy is
   the selected route for that capability.
3. Define and document precedence: persisted runtime route → environment
   default → built-in default. Avoid a second hidden precedence inside a
   provider getter.

**Verify**: a PowerShell check that counts `^LLM_PROVIDER=` in `.env` and
`.env.example` returns `1` for each; `python -c "from app.config import load_settings; s=load_settings(); print(s.llm_provider)"` prints the canonical provider and does not expose keys.

### Step 2: Add one backend route resolver and a truthful status contract

1. Add a small resolver module or a clearly isolated section in
   `app/storage/runtime_settings.py` (choose the existing layer that keeps
   persistence and runtime settings together) with typed route/status data.
2. Resolve each capability to `{configured, primary, effective, fallback,
   reason}`. A missing key may trigger fallback, but the returned `reason` must
   explicitly say why and which provider became effective.
3. Update `LLMService.get_active_provider()` to use the resolver. Preserve the
   existing public method signature for callers, but remove silent behavior from
   the UI by exposing the same resolution result through the API.
4. Add `GET /api/settings/ai` returning all capability routes and
   `PATCH/POST /api/settings/ai` for atomic updates. Keep `/api/settings/llm`,
   `/api/settings/tts`, `/api/settings/stt` and `/api/settings/oxyy` as backward-
   compatible adapters that delegate to the same resolver.
5. Extend `/api/settings/llm` with at least `effective_provider`,
   `effective_model`, `fallback_used`, `fallback_reason` and a redacted route
   summary. Never return key values.

**Verify**: add unit tests for: explicit Oxyy primary; explicit Groq primary;
missing primary key with visible fallback; all providers unavailable; and
persisted route surviving `load_settings()`. The tests must assert provider and
model fields, not only HTTP status.

### Step 3: Make the chat identity factual

1. Add a helper in `app/agent/prompts.py` that accepts the resolved chat route
   and emits a short internal system-context block containing provider, model,
   and whether fallback was used.
2. Pass that block from `app/agent/orchestrator.py` into both normal and
   streaming function-calling prompt construction. Do not expose API keys or
   internal fallback diagnostics unless the user asks who/what is running.
3. Add a rule to the system prompt: when asked about its engine, answer only
   from this runtime context; if no model is known, say that the provider/model
   is not exposed rather than guessing GPT-4, OpenAI or another model.

**Verify**: unit-test the prompt helper for Oxyy, Groq and fallback routes,
including the absence of secret-like strings. Add an orchestrator test that
checks the generated prompt contains the selected provider/model and does not
contain a hard-coded GPT-4 claim.

### Step 4: Replace the confusing settings layout with explicit primary/fallback routes

1. In `frontend/src/types.ts`, add types for capability route status and the
   aggregate AI settings response.
2. In `frontend/src/App.tsx`, load `/api/settings/ai`, use one state object for
   route updates, and refresh it after every provider/model change. Keep legacy
   endpoint calls only as compatibility fallbacks if the aggregate endpoint is
   unavailable.
3. In `frontend/src/pages/SettingsPage.tsx`, replace the current visual model of
   “many selected providers” with:
   - a “Motor de chat” section containing one radio/card group for Gemini,
     Groq and Oxyy;
   - a model select shown directly under the chosen provider (native model for
     Gemini/Groq; Oxyy catalog select only when Oxyy is chosen);
   - separate “Voz”, “Transcrição”, “Imagem”, “Vídeo” and “Embeddings” route
     cards, each with one primary provider and an explicit fallback row;
   - badges for “Ativo agora”, “Fallback”, “Configurado” and “Chave ausente”;
   - a compact diagnostic line such as “Chat efetivo: Oxyy ·
     gemini-2.5-flash” so the user can verify the route without opening the
     accordion.
4. Keep the Oxyy catalog accordion, but relabel it as “Catálogo de modelos
   Oxyy” and state clearly that selecting a catalog model does not activate Oxyy
   until the capability's primary provider is Oxyy.
5. Add a “Testar rota” action that calls a safe backend status/health endpoint
   without sending the user's chat content. Show the returned effective route
   and fallback reason in the existing notice area.

**Verify**: `npm run build` from `frontend` exits 0. Manually verify that selecting
Groq leaves Oxyy's catalog choice visible but inactive, selecting Oxyy marks
Oxyy and its chosen model as active, and a missing key visibly shows fallback
instead of a second active card.

### Step 5: Cover regressions and document the operator workflow

1. Extend `tests/test_llm_provider.py` or create `tests/test_provider_routes.py`
   using its isolated runtime-settings fixture pattern.
2. Add API contract tests for aggregate GET/POST, legacy adapter responses, no
   secret leakage, and stable fallback reasons.
3. Add a short section to `README.md` or `USER_GUIDE.md` explaining the only
   supported workflow: choose one primary provider per capability, then choose
   its model; fallback is optional and visible.

**Verify**: `python -m compileall -q app`; targeted pytest for provider/config
tests passes; `npm run build` passes; `git diff --check` reports no whitespace
errors; `git status --short` shows only the in-scope files.

## Test plan

- Model the new tests after `tests/test_llm_provider.py` and its temporary
  runtime-settings fixture.
- Cover duplicate/precedence migration, provider selection, Oxyy model selection
  without activation, explicit fallback, all-keys-missing, prompt identity and
  API redaction.
- Run `pytest -q tests/test_llm_provider.py tests/test_provider_routes.py` (or
  the final provider test file name chosen by the executor), then
  `python -m compileall -q app`, `npm run build` in `frontend`, and `git diff
  --check`.

## Done criteria

- [ ] `.env` and `.env.example` each contain exactly one `LLM_PROVIDER`.
- [ ] The backend has one aggregate route status contract with explicit primary,
      effective and fallback values for every capability.
- [ ] The settings panel cannot visually imply that Groq, Gemini and Oxyy chat
      are active at the same time.
- [ ] The panel names the effective provider and model without exposing keys.
- [ ] An Oxyy catalog selection does not activate Oxyy by itself.
- [ ] The assistant's self-identification is generated from runtime provider and
      model context; no hard-coded GPT-4 identity remains.
- [ ] Targeted provider tests, compileall, frontend build and diff check pass.
- [ ] No files outside Scope are modified.

## STOP conditions

- The intended `.env` provider cannot be determined from the persisted runtime
  settings and current user-visible selection; stop before deleting either
  declaration and report the ambiguity.
- A key value, token or credential is found in a tracked file; stop and report
  only its file, line and credential type. Do not copy it.
- The current backend has a second provider-selection path not listed in this
  plan; stop and update the route inventory before changing behavior.
- Removing silent fallback would break an existing voice/tool path outside the
  Scope; stop and report the caller rather than adding an implicit third route.
- Any verification command fails twice after a focused fix attempt.

## Maintenance notes

- Any future provider must implement the same capability route/status contract;
  do not add another independent boolean/card set.
- Keep provider/model identity derived from the resolver, not handwritten in a
  persona string. Review fallback reasons whenever a new key rotation policy is
  added.
- The plan intentionally does not implement video generation or embeddings
  consumers; those should consume the already-visible capability routes in a
  later plan.
