# Step 4: aprovação automática

## Arquivos
- `app/storage/auto_approvals.py` (novo): regras e Modo liberado em `data/auto_approvals.json`.
- `app/agent/action_executor.py`: ao propor uma ação que pediria aprovação, consulta o Modo liberado e as regras. Se cobrir, a ação vai direto para "autorizada" e executa. O motivo fica no histórico da Central: "Aprovada pelo modo liberado (origem: …)" ou "Auto-aprovada pela regra apr_… (origem: …)".
- `app/ui/panel/api/approvals.py` (novo) e `app/ui/panel/server.py`: `GET /api/approvals`, `POST /api/approvals/mode`, `POST /api/approvals/rules` (por `action_id` ou manual), `POST /api/approvals/rules/<id>` (duração ou `revoke`).
- `frontend/src/components/AutoApprovals.tsx` (novo): `AutoApprovalsManager` (toggle + lista de regras), `LiberatedModeBadge`, `AlwaysAllowButton`.
- `AppShell.tsx` (selo vermelho "Modo liberado · desligar" no cabeçalho, some quando desligado), `SettingsPage.tsx` (gerenciador), `ActionHistory.tsx` e `MissionControlPage.tsx` (botão "Permitir e autorizar" com duração).

## Comportamento
- Regra = ferramenta + operação + alvo (operação/alvo vazios valem para qualquer um; "Permitir e autorizar" usa o escopo exato da proposta). Durações: só agora (10 min), hoje (até 23:59), 30 dias, sempre. Cada regra conta usos e pode ser revogada.
- Modo liberado vale para todos os riscos. Desliga ao reiniciar o backend, salvo se "Manter após reiniciar" estiver ligado.
- Propostas já pendentes antes de uma regra nova continuam pendentes até serem aprovadas.

## Não feito / observações
- Regras ficam locais (não entram na sincronização do Supabase).
- "Permitir e autorizar" só funciona enquanto o backend que criou a proposta está no ar (escopo guardado em memória, como o broker).
- Sem testes nem verificação visual, conforme pedido. Só `tsc --noEmit` e `py_compile` passaram.

## Testar
1. Configurações > Aprovações automáticas: ligar/desligar Modo liberado e ver o selo no cabeçalho.
2. Pedir uma ação de risco (ex.: fechar app), clicar "Permitir e autorizar" na Central; repetir e ver a auto-aprovação com a regra no histórico.
3. Editar duração e revogar uma regra.
