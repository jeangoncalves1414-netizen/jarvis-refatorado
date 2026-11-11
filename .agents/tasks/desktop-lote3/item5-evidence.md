# Lote 3, item 5: S1 (lápides de exclusão) + S2 (data de edição dos hábitos)

## O que foi feito
- **S1, lápides** em `app/storage/sync_tombstones.py` (arquivo novo, local `data/sync_tombstones.json`): guarda `tipo -> chave -> instante da exclusão`. Tipos: `tasks` (tarefas de `data/tasks.json`), `notes` (caminho da nota do cofre), `lifestyle.habits`, `lifestyle.habit_logs`, `lifestyle.tasks`, `lifestyle.finance_transactions`. Validação de origem não confiável (tipo conhecido, chave até 300 caracteres, instante finito, nunca no futuro, até 5000 por tipo) e limpeza das lápides com mais de 90 dias (`RETENTION_SECONDS`) em toda leitura/gravação.
- Serviços registram a lápide ao apagar de fato: `FinanceService.delete_transaction`, `HabitService.delete_habit`, `HabitService.uncheck_in`, `TaskService.delete_task` (rotina, SQLite) e `task_store.delete_task`. Falha ao gravar a lápide vira aviso no log e nunca impede a exclusão.
- Notas do cofre não têm exclusão pela API (são apagadas na pasta). `_collect_notes` compara com a lista de notas vistas na coleta anterior; a nota que sumiu do disco vira lápide com o instante dessa coleta anterior (nunca depois da exclusão real).
- `app/storage/backend_sync.py`:
  - O snapshot ganha `tombstones`. `merge_snapshots` une as lápides dos dois lados (vale a mais recente) e tira de tarefas, notas e linhas do SQLite os itens cuja lápide é mais recente ou igual à última edição deles (`updated_at`/`created_at`, `mtime`, `timestamp`, `completed_at`). Item editado ou recriado depois da exclusão vence e continua vivo.
  - Linhas filhas de uma mãe apagada também saem: registros de hábito (`habit_logs`) e subtarefas (`task_subtasks`).
  - `apply_snapshot` grava as lápides unidas, apaga do SQLite local as linhas cobertas (`_delete_lifestyle_rows`) e apaga as notas cobertas, guardando antes uma cópia em `.conflitos/<nome>.apagada.<ms>.md`. O resumo traz só contagens novas: `notes_deleted`, `lifestyle_rows_deleted`, `tombstones`.
- **S2, data de edição dos hábitos** em `app/services/habits.py`: coluna `updated_at` (migração com `ALTER TABLE` para bancos existentes, valor 0 = nunca editado), preenchida na criação e em toda `update_habit`. Na mesclagem, `habits` passa a usar a regra "mais recente vence" com o maior entre `updated_at` e `created_at` (antes a versão local sempre vencia). Empate: local.
- Frontend: nenhuma mudança necessária. `jarvisCloud.ts` repassa o snapshot do backend inteiro (`...cloudBackend`) para `/api/settings/sync-merge` e grava o snapshot devolvido na nuvem, então `tombstones` viaja junto. No modo celular sem backend o snapshot da nuvem é preservado como está.
- Testes: `tests/conftest.py` ganhou fixture automática que aponta o arquivo de lápides para `tmp_path` (nenhum teste grava em `data/`); `tests/test_backend_cloud_sync.py` troca o arquivo de lápides por dispositivo e ganhou 5 testes.

## Decisões conservadoras (sem pausar)
- Lápides expiram em 90 dias. Um dispositivo que ficar mais de 90 dias sem sincronizar pode trazer de volta um item apagado; aceito para o arquivo não crescer sem fim.
- Nota apagada por lápide vindo de outro dispositivo é copiada para `.conflitos` antes de sumir (nada se perde sem cópia).
- O instante da lápide de nota é o da última coleta em que ela existia, não o da detecção, para que uma edição feita em outro dispositivo nesse intervalo vença.
- Metas (`goals`), categorias de finanças, memórias e seções do cofre do frontend (`mergeSection`, localStorage) ficaram fora: não estavam no escopo de S1 (finanças, tarefas, hábitos, notas) e continuam com a união de antes.
- Snapshots antigos (sem `tombstones`, hábitos sem `updated_at`) funcionam: sem lápide nada é apagado; hábito sem `updated_at` usa `created_at`.

## Verificação
- `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_backend_cloud_sync.py tests/test_runtime_settings_sync.py tests/test_evolute_sync.py tests/test_habits_tasks_finance.py`: 34 passed.
  - Novos: apagar finanças, hábito (com registro), tarefa de rotina (com subtarefa), tarefa e nota em A e mesclar com o snapshot velho de B não ressuscita; a exclusão chega a B pela nuvem (com cópia da nota em `.conflitos`); snapshot velho de B de novo não traz nada de volta; edição/recriação depois da lápide vence; edição de hábito em A chega a B e o snapshot velho de B não a desfaz; snapshot antigo sem lápides nem `updated_at` continua funcionando; validação e limpeza de lápides de 90 dias.
- `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`: sem erros.
- `data/sync_tombstones.json` não existe depois dos testes (nada gravado em `data/`).
- Não verificado: Supabase real, dois dispositivos reais, backend real com dados pessoais.
