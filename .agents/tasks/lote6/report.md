# Relatório do lote 6: controle total, loop agêntico e popups animados

Ponto de retorno: tag `antes-lote6` (`dacbf1e`). Tudo foi feito na branch `main`, só local (nenhum `push`). Nenhuma dependência nova de pip ou npm.

**Antes de testar:** em `frontend/`, rode `npm run build` e depois feche e abra o app de novo. Sem isso, a interface antiga continua aparecendo.

## Commits

| Fase | Commit | Conteúdo |
|---|---|---|
| 1 | `a49a907` | Catálogo completo de ferramentas, operações em lote, `open_screen` |
| 2 | `22f7425` | Loop agêntico com verificação, retomada após aprovação, contador de etapas |
| 3 | `e28ae89` | Infraestrutura de popups animados (fila, primitivas, `show_popup`, `/api/popups`, chat e voz) |
| 4 | `d2a7b17` | Popups de hábitos, agenda, água e anotação ao vivo com ditado |
| 5 | `24d0577` | Busca de lugares (OpenStreetMap, Google opcional), janela e popup Lugares, popup de tarefas, `/pendencias` |
| 6 | `ff46cbc` | Simulação de `/api/approvals` corrigida nos smoke tests `runs` e `workspace`; `docs/CONTEXTO_PARA_CHATGPT.md` atualizado |
| 6 | commit seguinte a `ff46cbc` | Este relatório e o `progresso.md` |

## O que foi feito, por funcionalidade

### 1. Mais comandos e controle total para o agente (Fase 1)
- Toda ferramenta geral agora tem entrada no catálogo do Action Kernel, com risco por operação, alvo e efeito. A lista completa (ferramenta, operações, risco, parâmetros) está em `.agents/tasks/lote6/inventario.md`, regenerada nesta fase.
- Operações em lote: vários hábitos, tarefas, lançamentos e lembretes numa chamada só (`create_many`, `check_many`, `add_many`). Cada lote valida tudo antes de gravar.
- Operações novas: editar e renomear hábito, editar tarefa e lançamento, filtros de listagem (período, tipo, categoria, só hoje, concluídas), lembretes de um dia específico, cancelar timer pelo nome.
- Hábitos e tarefas podem ser encontrados pelo nome (sem acento e sem maiúscula). Apagar exige o nome exato.
- `lifeos_tool.set_water`: "bebi 3 L hoje" define o total do dia; "bebi mais um copo" continua somando.
- Ferramentas do cofre (`vault_search`, `vault_daily_log`, `vault_save_note`, `vault_update_profile`) ficaram visíveis para o agente, com validação de pasta e tamanho.
- `open_screen`: o agente abre telas do app ("abre o painel" abre o Painel pessoal).

### 2. Loop agêntico (Fase 2)
- O agente pode fazer várias chamadas a si mesmo dentro de um pedido: planeja até 5 ações, executa, confere o resultado e planeja de novo, até terminar ou bater no limite.
- A decisão de usar o loop é por regra, sem gastar chamada ao modelo: pedido com duas ações ou mais, com "depois"/"em seguida"/"também", ou com "confere se". Pedido simples segue o caminho normal.
- Verificação automática: depois de criar hábito, tarefa, lançamento, água, lembrete ou nota, o agente relê o dado pelo mesmo Kernel e confirma que gravou.
- Retomada após aprovação (C8): se uma etapa precisa de aprovação, o chat avisa "Aguardando aprovação na Central; depois eu continuo sozinho." Ao aprovar, o agente continua a sequência e a resposta final aparece no chat.
- Contador (AQ5): o balão mostra "Etapa 3 de 8 · 3/10 chamadas ao modelo · planejando". A Central mostra o mesmo progresso e a resposta do agente.
- Configurações > "Agente e popups": modo do loop (automático, sempre, desligado), máximo de etapas (1-20, padrão 8), máximo de chamadas ao modelo (1-30, padrão 10), verificação automática.

### 3. Popups animados (Fases 3 e 4)
- Camada de popups no canto da tela, sem bloquear cliques. Fila de até 3 visíveis (configurável de 1 a 5), "+N na fila", Fixar/Soltar, Fechar, Esc fecha o popup focado. Fecha sozinho após 8 s (configurável; 0 = só fecha à mão). Com "reduzir movimento" do Windows ligado, os popups aparecem sem animação.
- Popups automáticos depois de cada ação do agente (pelo chat e pela ligação por voz):
  - **Hábitos:** a lista mostra cada hábito novo entrando um a um, com selo de feito e contagem "feitos hoje".
  - **Agenda:** linha do tempo do dia com o compromisso novo destacado.
  - **Água:** medidor de líquido subindo do valor anterior até o atual, comparado com a meta ("3.000 de 3.000 ml", "meta batida").
  - **Tarefas** (Fase 5): tarefas entrando em sequência, concluída riscada com animação.
- **Anotação ao vivo:** popup fixo que escreve o que você fala com efeito de digitação. Formatos Texto, Lista e Checklist (trocar reformata). Salva no cofre em `05-Notas` ao parar o ditado, ao fechar e no botão Salvar. Até o servidor confirmar, o rascunho fica guardado no navegador. Durante uma ligação por voz, enquanto a nota grava, suas falas vão para a nota e não para o agente, até você dizer "fim da nota", "terminar anotação" ou "parar anotação".
- Todos os números dos popups vêm do banco, nunca do texto do modelo.
- Configurações > "Agente e popups": "Mostrar popups", "Popups automáticos", "Fechar sozinho após (s)", "Máximo na tela".

### 4. Extras (Fase 5)
- **Busca de lugares:** usa o OpenStreetMap (grátis, sem chave). Se você cadastrar uma chave do Google Places em Configurações > Provedores ("Google Places API Key (opcional)"), usa o Google e cai no OpenStreetMap se o Google falhar.
- **Janela Lugares:** campos "O que procurar" e "Perto de", lista de resultados, mapa do OpenStreetMap centrado no resultado escolhido, botão "Abrir no mapa". A busca só acontece quando você aperta Enter ou "Buscar".
- **Popup Lugares** depois que o agente busca, com "Ver no mapa".
- Toda busca a terceiros aparece na Central.

## Como testar no app

Lembre de rodar `npm run build` em `frontend/` e reiniciar o app antes.

### Comandos sem IA (digite no chat)
- `/habitos`: popup com os hábitos de hoje.
- `/hidratacao`: popup da água de hoje (não soma nada).
- `/agua`: soma 250 ml e mostra o medidor subindo.
- `/compromissos`: popup da agenda de hoje.
- `/pendencias`: popup das tarefas pendentes.
- `/nota Compras`: abre a anotação "Compras". Clique em Gravar e fale; ou escreva à mão, escolha Checklist e clique em Salvar. Confira o arquivo em `data/vault/05-Notas/`.
- `/lugares padaria`: abre a janela Lugares já buscando "padaria". Troque o texto e aperte Enter para buscar de novo.
- Ctrl+K e "Fechar popups": fecha todos os popups.

### Pelo chat (com IA)
1. Frase de exemplo completa (testa loop + popups):
   "Abre o painel, adiciona os hábitos Ler, Correr e Meditar, depois agenda dentista amanhã às 15h e registra que bebi 3 litros de água hoje"
   Esperado: o Painel pessoal abre; o balão mostra "Etapa X de 8"; aparecem três popups (hábitos entrando um a um, agenda de amanhã com o dentista destacado, água subindo até 3.000 ml); a resposta final resume o que foi feito. Na Central (Execuções), um pedido com as ações e as leituras de verificação.
2. Água sozinha: "bebi 3 litros de água hoje" (define o total) e depois "bebi mais 500 ml" (soma).
3. Tarefas: "cria as tarefas comprar pão e pagar a conta de luz, depois marca comprar pão como feita".
4. Anotação ao vivo: "abre uma anotação em lista chamada Ideias e vai transcrevendo o que eu falar". O popup abre já gravando.
5. Lugares: "procura padarias perto da Avenida Paulista". Esperado: popup com a lista e "Ver no mapa".
6. Verificação: "cria o hábito Alongar e confere se ele foi criado".
7. Retomada após aprovação (com o Modo liberado **desligado**): "apaga o hábito Meditar e depois cria o hábito Yoga". O chat avisa que espera aprovação; aprove na Central; o agente continua e cria Yoga sozinho.
8. Limites: em Configurações > "Agente e popups", coloque máximo de 2 etapas e repita a frase 1. O agente para no limite e responde "Fiz X de Y etapa(s)… Parei no limite…".

### Pela voz
- Abra a ligação (botão "Abrir conversa por voz" ao lado do campo de mensagem, `/voz` ou Ctrl+K "Abrir conversa por voz") e fale a frase de exemplo 1. Os popups aparecem igual ao chat e a linha de status mostra o progresso das etapas.
- Na ligação, diga "abre uma anotação chamada Compras e anota o que eu falar". Fale alguns itens; a linha de status mostra "Anotando…". Diga "fim da nota" para salvar e voltar a falar com o agente.

## Resultados dos testes (Fase 6)

- **pytest:** 425 passaram, 0 falhas, em 26 arquivos direcionados: os 9 arquivos novos do lote (`test_tool_ops_lote6`, `test_open_screen`, `test_loop_policy`, `test_agent_loop`, `test_agent_loop_settings`, `test_popups_infra`, `test_popups_mirror`, `test_popup_templates`, `test_places`), mais `test_god_mode_components`, `test_backend_cloud_sync`, `test_runtime_settings_sync` e o conjunto de regressão R (14 arquivos). Todos isolam os dados em pasta temporária.
- **tsc:** sem erros.
- **`npm run build`:** ok. O único aviso de pedaço acima de 800 kB é o `elk` do mermaid, que já existia.
- **Smoke tests** (navegador com APIs simuladas):
  - `agent-loop`, `chat-cancel`, `popups`: passaram na primeira rodada.
  - `runs`: falhava porque a simulação não respondia `/api/approvals` do jeito que o selo do Modo liberado espera (problema anterior ao lote 6). Simulação corrigida em `ff46cbc`; passou.
  - `workspace`: mesma correção; agora passa as 6 primeiras partes (carga inicial, chat e aprovações, linha do tempo, desconexão, perfil, Métricas) e para no passo "Ditado pela paleta liga o microfone do compositor". Rodei o mesmo teste contra o frontend da tag `antes-lote6` e ele falha exatamente no mesmo passo, então não é regressão do lote 6. Provável causa: o gravador de áudio do navegador sem tela não inicia com o microfone simulado. Não corrigido; as partes depois desse passo (menu "/", etc.) não foram conferidas por esse teste.
- `mobile_app/` não mudou.
- Não rodados, por regra: a suíte completa e `tests/test_habits_tasks_finance.py`.

## O que falhou ou ficou de fora

- Nada foi testado com o app real, com provedores reais de IA, nem com o Nominatim/Google reais. O mapa do OpenStreetMap dentro da janela do app desktop (pywebview) também não foi conferido.
- Smoke `workspace`: passo do ditado pela paleta continua falhando (já falhava antes do lote).
- Reiniciar o backend no meio de uma sequência aguardando aprovação perde a retomada: o pedido vira "interrompido" na Central.
- A ligação por voz não fala a resposta de uma sequência retomada depois da aprovação; ela só aparece escrita no chat.
- O botão do modo "Execução por etapas" (`/api/react`) não mostra o contador em tempo real; o progresso aparece na Central.
- O popup de anotação não recebe o texto provisório da captura pelo microfone do PC (só frases inteiras). No navegador há texto provisório.
- Popups não aparecem no app do celular.
- Ação aprovada pela Central fora de uma sequência não gera popup.
- A rota antiga `/api/vault/notes` do painel ainda aceita qualquer pasta (a ferramenta do agente já restringe).
- Sem tela para o e-mail de contato do Nominatim (só por configuração ou variável `NOMINATIM_EMAIL`).
- Sincronização: as configurações novas (`agent_loop`, `popups`, chave `google_places`) passam pelo mesmo gravador das outras e sincronizam. As notas em `05-Notas` ficam no cofre, que já sincroniza. O rascunho local de uma nota ainda não salva fica só no navegador.
- Fora do lote desde o plano: rotinas com gatilhos, palmas, orientar pedido em andamento, aprovar dentro do chat, timer em popup.

## Como reverter

- **Voltar tudo para antes do lote 6:**
  `& "E:\PortableGit-2.54.0-64\cmd\git.exe" reset --hard antes-lote6`
  Atenção: isso descarta todos os commits depois da tag e também qualquer alteração não commitada nos arquivos versionados. Não tem volta fácil. Depois rode `npm run build` em `frontend/` e reinicie o app.
- **Desfazer só uma fase** (mantém o histórico e cria um commit de reversão):
  `& "E:\PortableGit-2.54.0-64\cmd\git.exe" revert <commit>`
  Use os hashes da tabela acima. As fases dependem umas das outras: reverta da mais nova para a mais antiga (Fase 6, 5, 4, 3, 2, 1). Reverter uma fase antiga sem as seguintes provavelmente dá conflito.
- Depois de qualquer reversão: `npm run build` em `frontend/` e reiniciar o app.
