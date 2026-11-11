# Lote 3, item 2: C1, propostas de aprovação com alvo, mudança, reversibilidade e escopo

## O que mudou
- `app/core/action_proposals.py` (novo): `build_proposal_preview(nome, argumentos, metadados)` monta a proposta em quatro campos, nesta ordem: `Alvo:`, `Mudança:`, `Reversibilidade:`, `Escopo:`. Usa só os metadados da ferramenta e argumentos já redigidos. Não chama a ferramenta.
- `app/agent/action_executor.py`: `propose` usa esse texto no lugar de "Executar X. Parâmetros registrados de forma protegida." (e do texto especial da `whiteboard_clear`, agora declarado no catálogo). A mensagem ao chat deixou de terminar com ponto duplo.
- `app/core/actions.py`: `ToolMetadata` ganhou `default_target`, `target_detail`, `effect`, `reversibility`, `operation_reversibility` e `scope`, com `reversibility_for`, `operation_for` e `detail_for`. `effect_for` passa a cair no `effect` da ferramenta. `risk_for`, `target_for` e a política não mudaram. O limite do texto da proposta subiu de 500 para 800 caracteres (`PREVIEW_LIMIT`), para o escopo não ser cortado.
- `app/agent/tools/catalog.py`: todas as 29 ferramentas do catálogo declaram alvo, mudança, reversibilidade e escopo (por operação onde há operações: `system_control`, `open_windows_app`, hábitos, tarefas, finanças, Life OS, `file_manager`, `mobile_adb`, `kasa_control`).
- `app/services/app_manager.py`: `running_processes_for(nome)` devolve `[(executável, quantidade)]` com o mesmo casamento exato de `is_app_running`. Só lê a lista de processos.

## Fechar app
`open_windows_app` com `close` mostra, por exemplo: `Alvo: spotify (encerrar processos: Spotify.exe (2 processos)). Mudança: Encerra todos os processos listados: pede para sair e, se não saírem, força o encerramento. Reversibilidade: Não reversível: o aplicativo precisa ser aberto de novo e dados não salvos nele se perdem. Escopo: Só processos com exatamente o nome do executável indicado; vale o que estiver aberto ao autorizar. Autorizar vale só para esta execução; não cria permissão permanente.`
- Sem processo correspondente: "nenhum processo em execução com esse nome; nada será encerrado".
- Mais de 5 executáveis: lista 5 e informa "e mais N executável(is)".
- Falha ao ler processos: "não foi possível consultar os detalhes do alvo". A proposta continua aguardando aprovação.
- `open` com alvo fora dos apps conhecidos (que já exigia aprovação) agora avisa "fora dos aplicativos conhecidos; será iniciado como foi digitado".

## Textos para cada ferramenta sem declaração
Ferramenta de plugin ou sem metadado no catálogo continua com risco alto e aprovação. A proposta diz "alvo não declarado", lista só os NOMES dos parâmetros (nunca os valores), "Mudança não declarada pela ferramenta; tratada como risco X" e "Não declarada; trate como irreversível". Nada é afirmado sem base.

## Decisões tomadas sozinho (opção conservadora)
- Escopo = alcance da ação + "Autorizar vale só para esta execução; não cria permissão permanente." Concessões por escopo (ferramenta + alvo, duração, limite, revogar) são o item C2 e não foram implementadas.
- Reversibilidade só afirma "Reversível" quando há uma saída real hoje (apagar, desmarcar, fechar, acionar de novo), sem prometer desfazer em 1 clique: `undo_payload` ainda não é preenchido por nenhuma ferramenta. Onde não há saída (exclusões pessoais, WhatsApp, fechar app) diz "Não reversível".
- WhatsApp: a proposta mostra destinatário e os 80 primeiros caracteres da mensagem, com o total de caracteres, porque quem aprova precisa ver o que sai. O texto fica no histórico local (`action_journal`).
- Script, texto digitado no celular (ADB `type_text`): o código e o texto NÃO aparecem (só linguagem/descrição e quantidade de caracteres). Comando de `shell` do ADB e de `hacker_mode` aparecem, truncados em 120 caracteres e redigidos.
- Frontend não mudou: a Central e a página de controle já exibem `preview` inteiro. Texto longo aparece corrido no título do cartão. Se a usuária quiser os quatro campos em linhas separadas, é uma mudança visual de outro item.
- A lista de processos é a de agora; o texto avisa que vale o que estiver aberto ao autorizar.

## Testes
- Novo `tests/test_action_proposals.py` (15 testes): proposta completa para todas as ferramentas do catálogo (sem "não declarado"), fechar app com `psutil.process_iter` simulado (processos listados, nada encerrado), sem processos, falha de consulta, mais de 5 executáveis, abrir alvo desconhecido, ferramenta desconhecida sem valores de parâmetros, operação de sistema não reconhecida sem listar processos, brilho/bloqueio, finanças, WhatsApp, script sem código, ADB, leitura, metadado sem declaração.
- `tests/test_action_kernel.py`: o teste de fechar app passou a simular `psutil.process_iter` (a proposta agora lê processos).
- Alvo: `tests/test_action_proposals.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_app_manager.py`: 113 passaram.
- Suíte completa (sem `test_fish_tts.py`/`test_fish_emotions.py`, não executados): 591 passaram, 24 desmarcados pela configuração, 0 falhas.
- `tsc --noEmit`: sem erros.

## Não verificado
Backend real, processos reais do Windows, aprovação na interface real (smoke de navegador fica para a etapa final).
