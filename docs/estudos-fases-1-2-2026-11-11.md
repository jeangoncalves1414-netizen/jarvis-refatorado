# Relatório — Sistema de Estudos: Fases 1 e 2 (+ itens 6.5, 6.8 e 9)

**Data:** 11 de novembro de 2026  
**Branch:** `main` · base `7cab802` · HEAD `514549c`  
**Escopo:** itens 1.1–1.8, 2.1–2.7, 6.5, 6.8, item 9. Fases 3–6 fora do escopo.

---

## 1. O que mudou

### Commit `cac95b6` — `feat(agent): conecta modo language ao prompt CEFR e isola ferramentas de idiomas`

Itens **1.1** e **1.2**.

| Arquivo | O que mudou |
|---|---|
| `app/agent/orchestrator.py` | Branch `elif mode == "language"` que chama `build_language_system(...)` com target, native e nível CEFR. Sem memória, persona nem bloco situacional. `language` adicionado à lista de exclusão de racing. |
| `app/agent/tools/registry.py` | Criado `LANGUAGE_TOOL_NAMES` (os 4 `language_*`), removidos de `TUTOR_TOOL_NAMES`. Criado `STUDY_MODES = {"tutor", "language"}` para substituir checagens `mode != "tutor"`. |
| `app/agent/tools/catalog.py` | Oito novas entradas `ToolMetadata` para `language_*`, `tutor_save_progress`, `tutor_add_flashcard`, `tutor_save_feynman` e `enem_save_question` — todas `risk=low`. |
| `app/agent/tools/inventory.py` | Coluna `language` adicionada. |
| `app/agent/modes/language.py` | Regra 9 reescrita sem referência ao whiteboard (UI de idiomas não tem whiteboard). |
| `tests/test_language_mode.py` | Novo — verifica prompt CEFR, `get_tool_declarations == allowed_tool_names` para gemini e groq, ausência de `language_*` no modo tutor, ausência de ferramentas MCP. |
| `tests/test_turn_tool_allowlist.py` | Caso `language` adicionado. |
| `tests/test_tool_catalog.py` | Verificação de que todo tool de estudo tem entrada no catálogo e não é crítico. |

---

### Commit `d3a7304` — `feat(estudos): agenda FSRS real (py-fsrs) com learning steps e migração de cards`

Itens **1.4**, **1.5**, **2.4** (backend).

| Arquivo | O que mudou |
|---|---|
| `pyproject.toml` | Dependência `"fsrs>=6.3,<7"` adicionada. |
| `app/storage/tutor/fsrs.py` | Reescrito como adaptador de py-fsrs 6.3.2. Funções públicas: `validate_grade`, `normalize_card`, `apply_review`, `is_due`, `retrievability`, `sort_due`, `GRADE_*`, `ReviewResult`. |
| `app/storage/tutor/srs.py` | **Deletado** (código SM-2 morto). |
| `app/storage/tutor/__init__.py` | Reaponta re-export para `fsrs.py` em vez de `srs.py`. |
| `app/storage/tutor_store.py` | Usa `normalize_card`; grade validada antes da busca do card; retorna 400 `invalid_grade`. |
| `app/storage/language_store.py` | Mesmas adaptações; `next_due_at` nas listas de devidos. |
| `app/ui/panel/api/tutor.py` | 400 em grade inválida. |
| `app/ui/panel/api/language.py` | 400 em grade inválida. |
| `tests/test_fsrs.py` | Reescrito: steps de aprendizado, lapse → relearning, intervalo ≤ 365, retrievabilidade pré-revisão, migração de cards legados. |
| `tests/test_tutor_store.py` | Atualizado para learning steps. |
| `tests/test_language_store.py` | Atualizado para learning steps. |

---

### Commit `de29883` — `feat(estudos): log imutável de revisões e desfazer última revisão`

Itens **2.5** (backend).

| Arquivo | O que mudou |
|---|---|
| `app/storage/tutor/review_log.py` | Novo — JSONL append-only com lock; métodos `append`, `last_active_review`, `active_reviews`, `undo_entries`. |
| `app/storage/tutor_store.py` | Snapshot `before`/`after`, append de log, `undo_last_review()` com restore exato e revogação de XP. |
| `app/storage/language_store.py` | Mesmo pattern do tutor. |
| `app/ui/panel/api/tutor.py` | Endpoint `POST /api/tutor/flashcards/undo`. |
| `app/ui/panel/api/language.py` | Endpoint `POST /api/language/vocabulary/undo`. |
| `tests/test_review_undo.py` | Novo — 176 linhas: restore exato incluindo chaves ausentes, XP revogado, undo repetido, 404 sem nada a desfazer, 409 stale, 409 card deletado, log só cresce. |
| `tests/test_panel_tutor_api.py` | Casos de grade inválida e undo adicionados. |

---

### Commit `94b47f4` — `feat(estudos): XP/sequência unificados, API de painel e estatísticas, endpoints de idiomas`

Itens **2.3** (backend), **2.6**, **2.7** (backend).

| Arquivo | O que mudou |
|---|---|
| `app/storage/study_xp.py` | Novo — `StudyXP`, `get_study_xp` (cache por path), níveis (10 nomes + "Lenda N"), badges derivados, import legado idempotente. XP: revisão 10, pronúncia 15, conversa 25, shadowing 20, Pomodoro 20. |
| `app/storage/study_stats.py` | Novo — `build_dashboard` e `build_stats`: heatmap 371 dias, barras 30 dias, retenção, distribuição de estados, totais. |
| `app/storage/tutor_store.py` | Delega XP para `StudyXP`; remove matemática de streak in-store. |
| `app/storage/language_store.py` | Mesmo; `delete_vocabulary`; `shadowing_history` (últimas 100 com texto, nota, velocidade e data); validação de campos de conversa. |
| `app/agent/orchestrator.py` | Passa `xp=self.tutor_store.xp` para o `LanguageStore` padrão. |
| `app/ui/panel/api/study.py` | Novo — `GET /api/study/dashboard`, `GET /api/study/stats`, `POST /api/study/pomodoro`. |
| `app/ui/panel/api/language.py` | `POST /api/language/vocabulary/{id}/delete`, `POST /api/language/shadowing`, `POST /api/language/conversation`. |
| `app/ui/panel/server.py` | Registra `study.py` em ambas as tuplas GET e POST. |
| `tests/test_study_xp.py` | Novo — 149 linhas: add/revoke, reset diário, streak, best streak, import legado, níveis, badges. |
| `tests/test_study_api.py` | Novo — 198 linhas: shapes de dashboard e stats com valores reais, retenção, estados, Pomodoro 200/400, delete vocab, shadowing, conversa, `/api/study/categories` ainda funcionando. |
| `tests/test_language_store.py` | `test_dashboard_defaults` atualizado (goal 100). |
| `tests/test_tutor_store.py` | Casos XP estendidos. |

---

### Commit `82c1f73` — `fix(estudos): corrige campos, voz, fila de revisão, listeners e Pomodoro; atalhos e desfazer`

Itens **1.3**, **1.6**, **1.7**, **1.8**, **6.5**, **6.8**, **9** e **2.5** (UI).

| Arquivo | O que mudou |
|---|---|
| `frontend/src/utils/speechLang.ts` | Novo — mapa BCP-47 e nomes de idiomas em português. |
| `frontend/src/hooks/useReviewShortcuts.ts` | Novo — Space/Enter vira; 1-4 avalia (só após revelar); `z`/Ctrl+Z desfaz. Ignorados em inputs. |
| `frontend/src/hooks/useNextDueRefresh.ts` | Novo — refresca a fila quando o próximo card de learning vence. |
| `frontend/src/hooks/useLanguage.ts` | `Promise.allSettled`; reset de `vocabIndex` a 0 no refresh; `undoVocabReview`; `deleteVocabulary`; `endConversation`; shadowing posta em `/api/language/shadowing`. |
| `frontend/src/hooks/useStudy.ts` | Reset de índice; `undoReview`. |
| `frontend/src/pages/LanguagePage.tsx` | Nomes de campos corrigidos (`total_vocab`, `pronunciation_sessions`, `conversation_sessions`); `utterance.lang` dinâmico via `speechLang.ts`; cópia em pt-BR; atalhos e botão Desfazer; lista "Minhas Palavras" com delete via `ConfirmDialog`; botão "Encerrar conversa"; Pomodoro removido da home. |
| `frontend/src/pages/StudyPage.tsx` | Leak corrigido (handlers nomeados dentro do effect com `deps=[activeMode]`, removidos pela mesma referência); atalhos e undo na revisão; Pomodoro único sempre montado. |
| `frontend/src/components/study/PomodoroTimer.tsx` | Anel SVG real; pause/resume preservam fase e tempo (deadline-based); Reiniciar; `onComplete` disparado uma vez por effect com `cycleRef/firedCycleRef`; `+5 min`. |
| `frontend/src/styles.css` | `.pomodoro-timer` (era `.pomodoro-container`); estilos de anel, label, contagem e dock. |
| `frontend/src/types.ts` | Tipos estendidos. |
| `frontend/src/App.tsx` | Ajustes de prop spread. |

---

### Commit `514549c` — `feat(estudos): painel Hoje, progresso visual, gamificação e XP do Pomodoro`

Itens **2.1**, **2.2**, **2.3** (UI), **2.7** (UI).

| Arquivo | O que mudou |
|---|---|
| `frontend/src/hooks/useStudyStats.ts` | Novo — `allSettled` de dashboard e stats, `refresh`, `awardPomodoro`. |
| `frontend/src/components/study/StudyDashboard.tsx` | Novo — cards devidos, vocabulário devido, countdown do próximo learning, streak com animação, barra XP/meta, barra de nível, 7 botões rápidos. |
| `frontend/src/components/study/StudyProgress.tsx` | Novo — heatmap SVG 53×7 com tooltip; barras 30 dias empilhadas (tutor + language); retenção %; barra de estados com legenda; grade de conquistas. |
| `frontend/src/pages/StudyPage.tsx` | Modo `plan` substituído pelo `StudyDashboard`; stats refrescadas após revisão, undo, ações de idiomas e Pomodoro; Pomodoro `work` completo posta `POST /api/study/pomodoro` e exibe "+20 XP". |
| `frontend/src/pages/LanguagePage.tsx` | Prop `initialTab` para abertura direta na aba de vocabulário. |
| `frontend/src/styles.css` | Estilos de dashboard, heatmap, barras e conquistas. |
| `frontend/src/types.ts` | Tipos de dashboard e stats. |
| `frontend/tests/study.smoke.cjs` | Novo — smoke test Playwright: mock de `/api/**` com estado, `page.clock` para avançar o Pomodoro, `broken-text.cjs`, 7 asserções, 5 screenshots. |

---

## 2. Decisões

### 2.1 py-fsrs (fsrs 6.3.2, MIT) em vez de corrigir o código manual

A implementação manual em `fsrs.py` era um subconjunto do FSRS-6: sem learning steps, retrievabilidade calculada a partir da data de vencimento (não da última revisão), sem separação de fases Learning/Review/Relearning. Corrigir exigiria reimplementar os 21 pesos, a curva de esquecimento por potência e as três fases — essencialmente manter uma biblioteca separada.

A biblioteca `fsrs` (PyPI, MIT, `python >= 3.10`, única dependência `typing-extensions`) fornece tudo isso na versão 6.3.2 (publicada em 2026-08-09). O risco de dependência é baixo: licença permissiva, projeto ativo, escopo pequeno e estável.

**Parâmetros do `Scheduler`:**
```python
desired_retention = 0.9
learning_steps    = (timedelta(minutes=1), timedelta(minutes=10))
relearning_steps  = (timedelta(minutes=10),)
maximum_interval  = 365   # dias
enable_fuzzing    = False  # determinístico para testes
```

Os `learning_steps` seguem o padrão Anki/py-fsrs. Um step de 1 h (citado como exemplo no plan de revisão) costuma cair fora da sessão e geraria cards devidos dentro de horas sem oportunidade de resposta; foi omitido intencionalmente.

### 2.2 Migração lazy de cards legados, sem perda de dados

`normalize_card(card)` adiciona `state`/`step` sem remover chaves legadas (`ease`, `interval` permanecem). Regras:
- `reps==0` e `lapses==0` sem `last_review` → `state="new"`.
- Qualquer outro card legado → `state="review"` com `stability=clamp(interval, 0.1, 365)`, `difficulty=clamp(old_difficulty, 1, 10)`, `due` preservado como meia-noite local convertida para UTC.

A migração é persistida só quando o card é revisado. Leituras retornam cópias normalizadas. `is_due` aceita os dois formatos; cards de revisão usam comparação de data local (semântica Anki).

### 2.3 Notas sobre `Promise.all` em `useStudy.ts`

O item 1.8 do plano de revisão nomeava apenas `refreshLanguage` como uso de `Promise.all` sem fallback. `refreshStudy` em `useStudy.ts` usa `Promise.all` pelo mesmo motivo. Como o escopo explícito cobria só `refreshLanguage`, `useStudy.ts` foi corrigido no reset de índice e undo, mas a substituição por `allSettled` em `refreshStudy` ficou fora do escopo. Registrado aqui para fase futura.

---

## 3. Afirmações da revisão que estavam incorretas ou imprecisas

A tabela abaixo refere-se ao arquivo de revisão original (`review-study-system.md`) e a verificações feitas contra o código base `7cab802`.

| Afirmação original | Situação real |
|---|---|
| `srs.py` "não importado em lugar nenhum" | **Parcialmente errado.** `app/storage/tutor/__init__.py` importava `srs.py` e re-exportava `apply_review` (SM-2). Nada importava o nome no nível de pacote, então era efetivamente morto — mas carregado. |
| Gamificação "invisível" | **Parcialmente errado.** A LanguagePage home já exibia streak e XP diário. O que era invisível era o XP do tutor (`TutorStore.add_xp` nunca chamado) e as barras de progresso/nível. |
| Colisão de IDs no `tutor_store` | **Parcialmente errado.** `fc-{len+1}` é seguro (flashcards nunca deletados). `fy-` (cap 50) e `as-` (cap 30) colidem após o cap. Fora do escopo desta fase; registrado sem correção. |
| Cap de estabilidade pertence à estabilidade | **Errado na proposta.** O cap correto é `maximum_interval` no `Scheduler` (que limita o intervalo calculado, não a estabilidade interna). A implementação usa `Scheduler(maximum_interval=365)`. |

---

## 4. Evidências de verificação

### 4.1 Testes Python

```
Comando: python -B -m pytest -q -p no:cacheprovider --tb=short \
  tests/test_fsrs.py tests/test_language_store.py tests/test_tutor_store.py \
  tests/test_panel_tutor_api.py tests/test_review_undo.py tests/test_study_xp.py \
  tests/test_study_api.py tests/test_language_mode.py tests/test_turn_tool_allowlist.py \
  tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_tools_smoke.py \
  tests/test_orchestrator_enem.py tests/test_situational_context.py

Resultado: 268 passed, 2 failed, 3 warnings — 97.86s
```

**2 falhas pré-existentes** (confirmadas em `7cab802` via `git show`):  
`test_tool_catalog.py::test_every_general_tool_has_catalog_entry_and_no_declared_operation_is_critical_by_omission`  
`test_tool_catalog.py::test_inventory_lists_every_general_tool_without_critical_operations`  

Causa: `personal_records` está em `GENERAL_TOOL_NAMES` em `registry.py` mas não tem entrada em `catalog.py`. Essa ferramenta pertence à investigação paralela de memória/hábitos (`.agents/tasks/memoria-habitos-modelo/`) e não foi tocada nesta fase.

**`data/study` não existia antes nem depois** dos testes (confirmado com `Test-Path`).  
**`data/tutor/progress.json`** e **`data/language/progress.json`**: mtimes não alterados durante os testes.  
**Nenhum `review_log.jsonl`** criado em `data/`.

### 4.2 TypeScript e build de produção

```
Comando (em frontend/): node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
Resultado: exit 0 (sem erros)

Comando: npm run build
Resultado: ✓ built in 58.30s — exit 0
```

### 4.3 Verificação de texto (broken-text.cjs)

```
Comando: node frontend/tests/broken-text.cjs
Resultado: exit 0
```

Nenhum mojibake ou texto quebrado nos arquivos de fonte.

### 4.4 Smoke test Playwright

```
Vite: 127.0.0.1:5174 (subido via script auxiliar .agents/tasks/estudos-fases-1-2/run-smoke.cjs)
PLAYWRIGHT_MODULE: C:\Users\maria\AppData\Local\Programs\Python\Python311\Lib\site-packages\playwright\driver\package
PANEL_TEST_URL: http://127.0.0.1:5174
PANEL_TEST_OUTPUT: c:\Users\maria\Desktop\Jarvis\.agents\tasks\estudos-fases-1-2\screenshots

Resultado:
  PASS: painel Hoje com pendências, sequência, meta diária e nível
  PASS: Espaço vira, 3 avalia como Bom e o próximo cartão aparece
  PASS: Z desfaz e o cartão anterior volta
  PASS: mapa de calor (371 dias), barras de 30 dias, retenção, estados e conquistas
  PASS: progresso de idiomas mostra palavras, pronúncias e conversas
  PASS: exclusão de palavra confirmada no diálogo
  PASS: Pomodoro de 25 min registra XP uma vez e o painel atualiza
  PASS: estudos (Hoje, revisão por teclado, desfazer, progresso, idiomas, exclusão, Pomodoro)
  exit 0
```

**Screenshots** (em `.agents/tasks/estudos-fases-1-2/screenshots/`):

| Arquivo | Descrição |
|---|---|
| `study-dashboard.png` | Painel Hoje: streak, barra XP, nível, cards devidos, botões rápidos |
| `study-review-keyboard.png` | Revisão com cartão virado por teclado |
| `study-undo.png` | Card anterior restaurado após `z` |
| `study-progress.png` | Heatmap 371 dias, barras 30 dias, retenção, estados, badges |
| `language-progress.png` | Aba Progresso de idiomas com valores não-zero |

### 4.5 mobile_app e graphify

```
git status --short mobile_app → (vazio)
graphify update . → exit 0 — "No code-graph topology changes detected; outputs left untouched"
```

---

## 5. O que NÃO foi verificado

1. **Backend real com dados pessoais** — todos os testes usam `tmp_path`; o arquivo `data/` nunca foi tocado.
2. **Web Speech API real** — pronúncia e TTS testados com mocks; o comportamento real de `SpeechRecognition` e `speechSynthesis` em diferentes navegadores e idiomas não foi testado.
3. **Provedor LLM real no modo language** — o prompt CEFR e as ferramentas de idioma foram verificados por testes unitários de orquestrador; nenhuma chamada real à API Gemini/Groq em modo `language` foi feita.
4. **APK mobile** — `mobile_app/` não foi modificado (confirmado por `git status --short mobile_app` vazio); a build móvel não foi executada.
5. **Dupla avaliação por tecla pressionada** — a condição de corrida de `useReviewShortcuts` (finding minor #1 do review) não foi coberta por teste automatizado; undo pode recuperar, mas a proteção não foi adicionada.
6. **Undo bloqueado por entrada irrecuperável** — finding minor #2: se o card mais recente não puder ser desfeito (deletado ou stale), undo retorna 409 para todas as revisões mais antigas do mesmo deck.
7. **`vocab_mastered` após undo no language** — finding minor #3: a contagem não é recalculada após undo no `LanguageStore`.
8. **Reversibilidade inacurada no catálogo** — finding minor #4: `tutor_add_flashcard` e `language_add_weak_phoneme` anunciam caminhos de desfazer que não existem.

Os itens 5–8 são **minor** conforme o review aprovado (`APPROVED`). Ficam registrados para a próxima fase de polish.

---

## 6. Checklist das Fases 1 e 2 + itens 6.5, 6.8 e 9

### Fase 1 — Correções Críticas

- [x] **1.1** Conectar `mode == "language"` no orchestrator — `cac95b6`
- [x] **1.2** Criar `LANGUAGE_TOOL_NAMES` separado no registry — `cac95b6`
- [x] **1.3** Corrigir nomes de campos frontend ↔ backend — `82c1f73`
- [x] **1.4** Corrigir bug retrievability no FSRS (R pré-revisão, calculado de `last_review`) — `d3a7304`
- [x] **1.5** Validação de grade (0–3 int, 400 em inválido) + cap de intervalo 365 dias — `d3a7304`
- [x] **1.6** Corrigir `utterance.lang` para usar o idioma-alvo dinâmico via `speechLang.ts` — `82c1f73`
- [x] **1.7** Reset de `vocabIndex` quando `dueVocab` muda — `82c1f73`
- [x] **1.8** `Promise.allSettled` em `refreshLanguage` — `82c1f73`  
  *(Nota: `refreshStudy` em `useStudy.ts` ainda usa `Promise.all` — fora do escopo explícito de 1.8; registrado na seção 2.3)*

### Fase 2 — Fluxo de Estudo Completo

- [x] **2.1** Study Dashboard "Hoje" — `514549c`
- [x] **2.2** Visualização de Progresso (heatmap, barras, retenção, estados) — `514549c`
- [x] **2.3** Gamificação visível (barra de XP, streak animado, níveis, badges) — `514549c`
- [x] **2.4** Learning Steps intraday (1 min → 10 min via py-fsrs) — `d3a7304`
- [x] **2.5** Undo Last Review (backend + UI: botão e atalho `z`/Ctrl+Z) — `de29883` + `82c1f73`
- [x] **2.6** Wiring completo: shadowing API, conversation log, delete vocab — `94b47f4` + `82c1f73`
- [x] **2.7** Pomodoro → XP integration (+20 XP por ciclo work concluído) — `94b47f4` + `514549c`

### Item 6.5 — Keyboard shortcuts para review

- [x] **6.5** Space/Enter vira; 1–4 avalia; `z`/Ctrl+Z desfaz; ignorados em inputs — `82c1f73`

### Item 6.8 — Fix event listener leaks no StudyPage

- [x] **6.8** Handlers nomeados dentro do effect com `deps=[activeMode]`, cleanup remove as mesmas referências — `82c1f73`

### Item 9 — PomodoroTimer

- [x] **9** Anel SVG funcional; pause/resume preservam fase/tempo; Reiniciar; `onComplete` disparado uma vez por effect; `+5 min`; CSS `.pomodoro-timer` — `82c1f73` + `514549c`

---

*Relatório gerado em 11/11/2026. Commits da base 7cab802 até HEAD 514549c (6 commits, 43 arquivos alterados, +3347 / -623 linhas).*
