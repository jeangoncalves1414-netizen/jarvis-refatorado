# Rodada 2 — comandos reais e limpeza

Rodada concluída, incluindo os dois comandos pendentes após a interrupção. Nenhuma correção funcional foi aplicada. O Jarvis estava fechado na retomada e foi reaberto para finalizar os testes.

## Método e cobertura

Foram concluídos **38 pedidos reais ao agente pelo endpoint de chat do aplicativo**, com modelo e ferramentas reais, mais **uma correção financeira solicitada pelo chat da interface**. Isso não significa 39 funcionalidades distintas: há repetições, negativas e tentativas bloqueadas pelo provedor. Respostas e recibos estão em `scratch/desktop-qa-round2/commands-summary.json` e nos arquivos individuais.

Resultados de escrita foram confrontados com SQLite, arquivos locais e APIs de consulta. A interface também foi usada para conferir os lançamentos financeiros e reabrir a nota salva. Não houve substituição das ferramentas por mocks nesta rodada.

| Área | Resultado dos pedidos reais |
| --- | --- |
| Hábitos | Criar, alterar horário, concluir e desfazer funcionaram. Pedido repetido de conclusão não executou outra ferramenta. Exclusão por conversa ficou bloqueada pelo limite do provedor; limpeza pela API funcionou. |
| Finanças | Despesa e receita gravadas e visíveis na interface. Corrigir o valor funcionou, mas mudou também a categoria. Exclusão por descrição falhou na resolução do lançamento; exclusão pelo ID exato funcionou. |
| Notas | Salvar, buscar código contido na nota, reabrir na interface e substituir conteúdo funcionaram. |
| Tarefas — pedido natural | Criou no JSON legado, com título incluindo parte da instrução e prioridade normal. Consulta/conclusão usou SQLite, onde aquela tarefa não existia. A resposta afirmou conclusão sem realizá-la. |
| Tarefas — ferramenta explícita | Um pedido criou três registros iguais no SQLite. Exclusão por nome apenas listou os registros e afirmou exclusão. Conclusão pelo ID exato funcionou, comprovada antes da limpeza. |
| Checklist | Primeiro pedido criou lista vazia apesar de solicitar Café e Papel. Pedido seguinte acrescentou os dois itens, com Café concluído. Pedido de exclusão apenas listou a checklist, mas afirmou tê-la excluído. |
| Agenda | Criou evento em 20/11/2026 às 15h, aviso 5 minutos antes; consulta e cancelamento dos avisos funcionaram. Houve chamada inválida corrigida no mesmo turno, mas a resposta misturou falha e sucesso. |
| Rotina | Criou rotina manual, sem gatilhos automáticos, e executou abertura de finanças. Run interno conferido como `succeeded`. Exclusão pelo agente bloqueada pelo provedor; limpeza pela API funcionou. |
| Temporizador | Criar e cancelar QA-R2-TIMER funcionaram. Não foi necessário aguardar o disparo de 30 minutos. |
| Planejamento | Abriu painel e persistiu a etapa solicitada; conteúdo conferido pela API. |
| Pesquisa web | Executou busca e devolveu links, mas não encontrou a página específica de pathlib solicitada. Resultado parcial, não aprovado como atendimento completo. |
| Navegador | Primeira tentativa bloqueada pelo provedor; repetição abriu example.com e retornou `Example Domain`. |
| Calculadora | Primeira tentativa bloqueada pelo provedor; repetição executou `open_windows_app` e retornou falha: não conseguiu abrir `calculator`. Não comprovada abertura. |
| Voz | TTS real gerou 37.197 bytes de áudio; STT real retornou texto. A frase enviada terminava em “amanhã”, palavra ausente no resultado. Não foi isolado se a perda ocorreu na síntese ou na transcrição. |
| Microfone / janela nativa | API enumerou 12 dispositivos e informou disponibilidade. Isso não comprova captura física. Nova tentativa de captura da janela nativa falhou por timeout. |

A tentativa de observar recibo financeiro ao **editar** expirou: o código só configura esse popup automaticamente para adicionar lançamentos. A edição foi comprovada no banco; não foi classificada como falha de gravação pela ausência do popup.

## Falhas prioritárias reproduzidas

1. **Confirmações falsas de ação:** concluir/excluir tarefa e excluir checklist foram anunciados sem executar a alteração correspondente. Os recibos mostram consultas, e os registros permaneceram no armazenamento.
2. **Tarefas divididas em dois armazenamentos:** o caminho determinístico de criação gravou `data/tasks.json`; `task_tool` consultou `data/lifestyle.db`.
3. **Duplicação na criação:** três chamadas de criação produziram três tarefas iguais em um único pedido.
4. **Edição financeira alterou campo não solicitado:** valor passou de 1,23 para 1,45, mas a categoria mudou de `Teste QA` para `QA-R2-DESPESA`.
5. **Pedidos parcialmente executados:** checklist sem itens no primeiro turno; pesquisa não encontrou a página solicitada.
6. **Limite do provedor:** novamente houve erro 429 e mensagens de chave ausente. Não foram trocadas chaves nem removidas proteções para contornar o limite.

Continuam válidos os achados da primeira rodada sobre ferramentas ausentes no ReAct explícito e criação genérica de arquivo bloqueada. Os novos achados precisam ser considerados junto aos três problemas originalmente previstos para correção.

## Limpeza concluída e verificada

Removidos exclusivamente os registros identificados desta rodada:

- Hábito `habit_719768d8` e seus dados associados.
- Tarefas SQLite `task_a7ae8bae`, `task_298eb853`, `task_c9eeecad` e tarefa legada `3ac4b0a060cb`.
- Lançamentos `fin_a9d4dcf7` e `fin_ff4de5c3` — o segundo foi excluído pelo próprio agente usando o ID.
- Checklist `list_0c0859c6` e seus itens.
- Rotina `rt_ae620c41bd33`.
- Evento `cd82b1d860a347dbb7ba5835918cc267`, cujos avisos já estavam cancelados.
- Nota `05-Notas/QA-R2-NOTA.md` e plano QA-R2 da conversa de teste.

As exclusões restantes usaram APIs do app; a tarefa legada usou seu serviço de armazenamento. A nota e o plano foram preservados na pasta de evidências antes da remoção. A primeira execução do script de limpeza parou ao importar o serviço legado; a retomada removeu o restante, e a verificação final foi executada separadamente.

Verificação final: zero hábitos, tarefas e lançamentos SQL desses testes; ausência da tarefa legada, evento, nota e plano; APIs de hábito/checklist/rotina retornaram 404; nenhuma ação pendente da conversa de teste. Evidência: `scratch/desktop-qa-round2/cleanup-verification.json`.

Conversas de diagnóstico, históricos de execução e arquivos em `scratch/desktop-qa-round2/` foram mantidos como evidência. Eles não são registros pessoais ativos. Nenhum processo dos scripts `qa_round2` permaneceu executando ao fechar a rodada. O aplicativo foi deixado aberto.

## Limites da conclusão

Esta rodada de comandos reais e limpeza terminou. **Não é uma declaração de que todas as funcionalidades do produto passaram ou foram testadas.** Não foram validados fala humana pelo microfone, áudio físico, palavra de ativação, bandeja/atalhos globais/ciclo da janela nativa, envio de mensagens a terceiros, dispositivos domésticos, autenticações externas, todas as ferramentas MCP, geração de imagem/vídeo e operações destrutivas do sistema. Integrações desconfiguradas e a captura nativa indisponível permanecem bloqueios explícitos, não aprovações.

Não foram feitas as correções funcionais nesta rodada, conforme a sequência solicitada pelo usuário.
