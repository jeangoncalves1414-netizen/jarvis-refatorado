# Correções após a auditoria desktop

## Alterações

- **Tarefas:** criação rápida, ferramentas e consulta do painel usam SQLite. Tarefas do JSON antigo são importadas uma vez por ID, com prioridade e conclusão preservadas. O JSON permanece intacto para recuperação; IDs importados ficam registrados para não ressuscitar tarefas excluídas. Concluir é uma operação explícita e idempotente, separada de alternar/reabrir.
- **Resultados do agente:** consultas entregam registros e IDs ao modelo. Uma consulta não satisfaz pedidos de concluir, excluir ou editar. O caminho nativo tenta completar pendências uma vez; se continuar incompleto, informa isso. Respostas de ações pessoais usam recibos reais. Uma chamada inválida posteriormente corrigida não mantém uma mensagem de falha antiga.
- **Repetições:** criações e exclusões repetidas reutilizam o recibo dentro do mesmo pedido. Criações individuais de tarefas, hábitos e lançamentos normalizam valores padrão antes da comparação. Pedidos diferentes continuam independentes; criar após excluir também funciona.
- **Finanças:** edição explicitamente restrita ao valor preserva campos não solicitados. Localização por descrição exata recusa ambiguidades. Excluir ID inexistente não afirma sucesso. Edições geram recibo com saldo anterior/posterior na mesma transação e abrem o popup existente.
- **Checklists:** schema descreve os itens; criar lista vazia quando o pedido inclui itens é recusado antes de gravar. Um identificador inexistente não seleciona outra lista só porque ela é a única disponível.
- **Arquivos/ReAct:** o modo por etapas recebe ferramentas pessoais e de arquivos relevantes, preservando as ferramentas que já possuía. `file_manager.create` cria texto UTF-8 dentro da pasta autorizada, com limite de 1 MB e criação exclusiva: não sobrescreve arquivos. Não foram relaxadas as restrições de `script_runner`.
- **Provedor:** cooldown por 429 informa limite temporário e espera estimada, distinguindo-o de chave ausente. Nenhuma chave, cota ou configuração de segurança foi alterada.
- **Calculadora:** o alias inglês `calculator` resolve para `calc`.
- **Pesquisa:** buscas de documentação refinam resultados sem o assunto solicitado e deixam de receber refinamentos de notícias. Se a ferramenta não trouxer fontes, a resposta final não pode afirmar que encontrou uma URL; a mesma proteção foi aplicada ao modo por etapas.
- **Inicialização desktop:** a nova rodada revelou um crash nativo `0xc0000005`. O faulthandler mostrou `PyAudio.terminate` no construtor de `speech_recognition.Microphone` concorrendo com `PyAudio.__init__` da wake word. A inicialização da wake word agora ocorre depois da API desktop. Ausência de microfone não impede a janela; falha ao iniciar gravação deixa de retornar sucesso fictício. A abertura inicial do stream da wake word usa o caminho de tentativa novamente já existente.

## Validação automatizada

Executada em cópia isolada do projeto, com dados e perfil temporários:

- **213 testes passaram** na bateria final consolidada: correções novas, inicialização sem microfone, fronteira de ações, orquestrador, loop, finanças/tarefas/hábitos, checklists, popups, arquivos, Calculadora e configuração LLM. Resultado JUnit: `scratch/desktop-qa-fixes/final-pytest.xml` (zero falhas).
- **67 testes passaram, com 44 subtests**, na verificação posterior de inicialização desktop, módulos desktop, conversa e voz. Há sobreposição com a bateria principal; esses números não devem ser somados como testes distintos.
- A proteção final de pesquisa foi conferida também em uma bateria direcionada de **93 testes**, todos aprovados, e repetida com o provedor real.
- Smoke da interface financeira passou: recibo, filtros, preservação de rascunho, tratamento de erro e edição. Esse smoke usa respostas simuladas; a edição real abaixo foi verificada separadamente.

## Validação real

Evidências em `scratch/desktop-qa-fixes/`:

- Tarefa criada uma única vez, título `QA-FIX-TAREFA`, prioridade 2 (alta). Conclusão por nome gravada; repetição manteve o mesmo estado e timestamp. Exclusão por nome removeu o registro.
- Checklist criada com Café e Papel. A primeira repetição de exclusão revelou uma segunda chamada indevida; a proteção foi ampliada e submetida aos testes acima.
- A primeira criação financeira revelou duplicação com argumentos equivalentes. Ambas as entradas de teste foram removidas por ID após conferir a descrição. A versão final criou **um** registro `QA-FIX-FINAL`.
- Pelo **chat da interface real**, o lançamento passou de 1,23 para 1,45; categoria `Teste QA` e descrição foram preservadas. O popup foi observado e fotografado, mostrando saldo de -11,23 para -11,45. Nenhum erro JavaScript ocorreu nessa verificação. Evidências: `ui-finance-edit.json` e `finance-edit-popup.png`.
- Exclusão do lançamento final por descrição funcionou; consulta SQL confirmou ausência.
- Modo por etapas criou `scratch/desktop-qa-fixes/prova.txt` e leu o conteúdo `QA-FIX-ARQUIVO-8437` em outro pedido. O conteúdo físico foi conferido.
- Pedido à ferramenta de aplicativos abriu a Calculadora com confirmação de efeito.
- Após o ajuste de inicialização, o processo apresentou a janela nativa **Jarvis** e continuou atendendo às verificações.
- Na repetição final, `QA-FIX-FINAL-LISTA` foi consultada pela API com dois itens (HTTP 200) e depois excluída por nome pelo agente. A consulta posterior retornou 404, sem a falsa falha causada por repetir a exclusão.
- A busca real de pathlib continuou sem fontes retornadas pelo mecanismo de pesquisa. Antes da última proteção, o modelo citava uma URL sem evidência; a repetição final informou **evidência insuficiente**, sem inventar que encontrou a página. Portanto, a honestidade da resposta foi corrigida, mas a obtenção dessa página por busca permanece limitada pelo mecanismo externo.

## Limpeza

Verificação independente em `cleanup-verification.json`: zero tarefas e lançamentos `QA-FIX-*`; ambas as checklists da rodada retornam HTTP 404. As duas duplicatas financeiras identificadas durante o desenvolvimento foram removidas somente após conferir os IDs e a descrição de teste. O lançamento final foi removido pelo próprio agente.

Conversas de diagnóstico, recibos, screenshots e arquivo de prova em `scratch/desktop-qa-fixes/` foram mantidos como evidência. Os scripts de comandos reais terminaram. O desktop foi reaberto com a versão corrigida.

## Limites

Os testes não eliminam os limites externos do provedor. A rodada encontrou 429 e preservou os registros das tentativas incompletas. Não foram validados novamente áudio físico, fala humana pelo microfone, palavra de ativação por voz, integrações externas desconfiguradas ou todas as funcionalidades do aplicativo. A inicialização do áudio foi corrigida; isso não comprova reconhecimento de voz em hardware.

Nenhum commit foi criado. Alterações anteriores do projeto foram preservadas.
