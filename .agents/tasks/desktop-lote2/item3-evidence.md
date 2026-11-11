# Item 3: sincronização total com a nuvem (Supabase)

## AVISO PARA A USUÁRIA: troque a chave da Fish Audio
A chave da Fish Audio que apareceu em um export antigo continua exposta. Gere uma chave nova no painel da Fish Audio, cole em Configurações e revogue a antiga. A sincronização não resolve isso: ela copia a chave que estiver salva, inclusive uma comprometida.

## Decisão aplicada
Tudo sincroniza com o Supabase da usuária, incluindo chaves de API completas, configurações, perfil do agente, memórias, notas, tarefas, metas, hábitos e finanças. A proteção é login + RLS da migração `202609200001_evolute_snapshots.sql` (nenhuma tabela nova foi criada; o dado novo vai dentro do mesmo snapshot por revisão atômica, na chave `backend` do cofre). Ficam fora caches, logs e `data/action_journal.sqlite3`.

## O que mudou
- `frontend/src/utils/syncMerge.ts` (novo, funções puras): mescla campo a campo, vazio nunca vence preenchido, campo que só um lado conhece é preservado, no mesmo campo vence o carimbo mais recente (empate: este dispositivo). Também tem máscara de segredos (`maskKeyList`, 4 últimos caracteres) e `redactForLog`.
- `frontend/src/utils/jarvisCloud.ts`:
  - Chaves, provedor e modelos viram campos carimbados (`api_keys.groq`, `llm_provider`, `oxyy_models.chat`...) em `vault.fields`. Dois dispositivos com provedores diferentes mantêm as chaves dos dois. `keys/provider/oxyyModels/providerModels` continuam sendo gravados para o APK antigo (contrato compatível; cofres antigos são lidos via `fieldsFromLegacyVault`).
  - Carimbos reais: cada campo/seção só ganha "agora" quando o conteúdo muda (impressão digital guardada em `jarvis_stamp_state`). Antes tudo era carimbado com `now` na coleta e o local sempre vencia.
  - A coleta não sobrescreve mais chaves locais com os vazios que o backend devolvia.
  - Seções do Life OS usam união por `id`, chave a chave e valor mais recente, em vez de "remoto vence".
  - Envio com até 3 tentativas em conflito de revisão; sem snapshot, usa a revisão real (antes mandava 0).
  - Entrar como PC sempre mescla com a nuvem (antes só enviava se houvesse chave).
  - `console.log` que imprimia o cofre, linhas da nuvem, URL e chaves foi trocado por `log()` com `redactForLog`. Em `evoluteCloud.ts` deixou de registrar o payload de login/renovação (tokens).
- `frontend/src/pages/SettingsPage.tsx`: campos de chave ficam sempre mascarados; o botão do olho mostra só os 4 últimos caracteres de cada chave. O dado salvo continua completo.
- `app/storage/backend_sync.py` (novo): `collect_snapshot`, `merge_snapshots` (pura), `apply_snapshot`, `sync_with_remote`. Cobre `runtime_settings.json` (chaves, provedores, modelos, rotas, perfil do agente), memórias (`memory.json`, `preferences.json`), tarefas (`tasks.json`), metas (`goals.json`), notas Markdown do cofre, e `lifestyle.db` (hábitos, tarefas da rotina, finanças).
- `app/storage/runtime_settings.py`: `_write` carimba por campo (`_field_ts`) só o que mudou; ajudantes de achatar/gravar sem recarimbar.
- `app/ui/panel/api/settings.py`: `GET /api/settings/sync-snapshot` e `POST /api/settings/sync-merge` (mescla, grava, atualiza `Settings` em memória, env e detector de frase de ativação; resposta traz só contagens no `summary`).
- `app/storage/memory_store.py`: recarrega o arquivo antes de ler/gravar, para a restauração não ser sobrescrita pela cópia em memória.

## Decisões conservadoras (sem pausar)
- Remoções não se propagam: a mesclagem é união. Apagar algo num dispositivo não apaga no outro (e um item apagado pode voltar). Evita perda de dados.
- Limpar uma chave de propósito não se propaga (vazio nunca vence preenchido). Para trocar uma chave, grave o novo valor.
- Chave diferente no mesmo provedor: vence a alteração mais recente (não une as listas, para não ressuscitar uma chave trocada, como a da Fish).
- Linhas de hábitos/finanças/tarefas da rotina não têm `updated_at`: finanças e logs usam `timestamp`; tarefas da rotina só viram "concluída"; hábitos mantêm a versão local. Edição de hábito em outro dispositivo não chega até existir uma coluna de atualização.
- Notas: vence a mais recente por `mtime`; a versão local substituída fica em `data/vault/.conflitos/`. Limite de 500 notas de até 512 KB.
- Se o backend local não responder, o envio preserva a seção `backend` que já está na nuvem em vez de sobrescrevê-la com dados parciais.
- Dispositivo sem backend (APK) repassa a seção `backend` sem editá-la; o perfil do agente só é editável no PC.
- Valores inválidos recebidos da nuvem (provedor inexistente, chave de provedor desconhecido, caminho de nota fora do cofre) são ignorados.

## Verificação
- `python -B -m pytest -q -p no:cacheprovider tests/test_backend_cloud_sync.py tests/test_runtime_settings_sync.py tests/test_evolute_sync.py tests/test_settings_api.py tests/test_orchestrator.py tests/test_chat.py`: 27 passed.
- `tests/test_backend_cloud_sync.py` (15 testes, chaves falsas, sem rede, diretórios temporários): chaves de dois dispositivos com provedores diferentes; vazio não sobrescreve preenchido (nos dois sentidos); carimbo mais recente e empate; entradas malformadas ignoradas; carimbo só nos campos alterados; ida e volta do snapshot (chaves, provedor, perfil do agente, tarefas, metas, memórias, preferências, notas, hábitos, rotina e finanças); mesclagem entre dois dispositivos; remoto antigo não sobrescreve edição local; conflito de nota guarda cópia; nota fora do cofre rejeitada; provedor inválido ignorado; endpoints sem chave completa em stdout/logs/resumo; payload inválido devolve 400; cliente não registra URL/linhas/cofre; helpers TypeScript executados com Node (mescla, máscara, `redactForLog`).
- `tsc --noEmit -p tsconfig.json` no frontend: sem erros.
- Não verificado: Supabase real, backend real, APK, navegador.
