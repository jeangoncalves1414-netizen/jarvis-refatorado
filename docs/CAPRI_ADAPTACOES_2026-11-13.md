# Adaptações do Capri para o Jarvis — 13/11/2026

## Escopo e referência

Prioridade definida por Jean: aproveitar controle do computador, acompanhamento de tarefas, voz e percepção da tela. Companheiro flutuante, animações e presença na área de trabalho ficam para uma decisão posterior.

Referência examinada: [Capri Desktop](https://github.com/lachydotmcg/capri-desktop/tree/26224db16484b51a894f96682d366c4a7a89db26), commit `26224db16484b51a894f96682d366c4a7a89db26`. Foram lidos README, licença e trechos de Hands, Lookout, FollowUps e regras do Brain. O projeto usa [PolyForm Noncommercial 1.0.0](https://github.com/lachydotmcg/capri-desktop/blob/26224db16484b51a894f96682d366c4a7a89db26/LICENSE). Esta etapa criou implementações próprias sobre os serviços existentes do Jarvis; não importou código, personagem, voz ou assets do Capri.

## Implementado nesta etapa

| Capacidade aproveitada | Implementação no Jarvis | Limite |
| --- | --- | --- |
| Consultar uma tarefa enquanto ela executa | Nova ferramenta `run_control`, registrada no modo geral e na seleção de ferramentas: consulta estado, progresso e recibos reais da mesma conversa | Lista limitada de tarefas e recibos recentes; não é um histórico completo |
| Parar uma tarefa específica | `run_control cancel` exige ID e usa o cancelamento existente; impede acesso a outra conversa e cancelamento do próprio comando | Cancelamento cooperativo: uma etapa iniciada pode terminar; efeitos anteriores não são desfeitos |
| Parar pelo chat enquanto aguarda confirmação | Botão de parada também considera `awaiting_confirmation` | Mantém as regras existentes de execução |
| Interromper voz sem anunciar sucesso inexistente | A confirmação usa a resposta da API para distinguir pedido cancelado, solicitação pendente e falha de confirmação; resposta tardia não invade uma nova interação | Interromper áudio, sozinho, não comprova cancelamento de tarefa |
| Descrever a tela com evidência atual | Captura identificada por arquivo e horário UTC; instruções comuns para Groq/Gemini exigem observação, incerteza e tratamento de texto da tela como dados | Uma imagem não demonstra movimento nem conclusão; instruções reduzem, mas não eliminam, erros do modelo |
| Falhar claramente quando não há captura | Ações desconhecidas e captura ausente retornam falha; câmera continua encaminhando ao fluxo de consentimento existente | Não houve implementação de observação contínua nesta etapa |

O Jarvis já tinha execução registrada, cancelamento por API, ferramentas de desktop/browser, captura de tela, memória e fluxo de voz. A adaptação conecta essas capacidades ao agente e melhora a precisão das confirmações, sem instalar um segundo motor de automação.

## Testes conversando com o agente real

Cinco pedidos foram enviados a `/api/chat`, usando o orquestrador, o provedor configurado e ferramentas reais:

1. Consultar uma conversa nova: respondeu que não havia outro pedido registrado.
2. Iniciar espera real de 180 segundos pelo modo ReAct.
3. Perguntar o que estava em andamento: retornou o ID da espera, seu estado e progresso.
4. Pedir cancelamento desse ID: informou a solicitação; a execução original terminou em `cancelled`, conferido pela API.
5. Pedir identificação apenas do aplicativo legível na tela: respondeu “Codex”. A imagem salva foi inspecionada e confirmou esse título.

Evidências locais em `scratch/capri-validation/`: `empty.json`, `wait.json`, `status.json`, `cancel.json`, `cancel-receipt.json` e `vision.json`. O script `scratch/capri-live.py` também verifica o estado final do cancelamento após a resposta da espera. Esses arquivos são ignorados pelo Git por conterem contexto local. A captura não foi incluída neste relatório.

Esses testes verificam os cenários descritos, não todas as ferramentas do aplicativo. A cobertura da rodada anterior está em [VALIDACAO_JARVIS_2026-11-13.md](VALIDACAO_JARVIS_2026-11-13.md).

## Verificações automatizadas

- Backend: **146 testes passaram**, com 44 subtestes, em `test_run_control.py`, `test_agent_loop.py`, `test_conversation_runtime.py`, `test_wait_and_effects.py`, `test_live_call_voice.py` e `test_vision_capture.py`.
- Voz no navegador: **26 testes Playwright passaram**, incluindo cancelamento pendente, confirmado e falha HTTP; interrupção, continuação de fala e descarte de resposta tardia.
- Chat: smoke de cancelamento passou, incluindo espera por confirmação e isolamento entre conversas.
- Build web: passou; permanecem avisos sobre tamanho de chunks e importação estática/dinâmica de `personalRecords`.
- Um teste de voz ultrapassou inicialmente seu prazo de 2 segundos. Passou em duas repetições isoladas; foi ajustado para a espera padrão de 5 segundos e passou a conferir também o texto enviado. A bateria completa posterior passou.

Os testes de voz usam dispositivos e respostas simulados no navegador. Não comprovam qualidade acústica de microfone real, reconhecimento de locutores ou integração com chamadas externas. A análise visual real é separada desses mocks.

## Próximas adaptações com maior utilidade

Estas capacidades são candidatas ainda não implementadas nesta etapa:

1. **Observação visual condicional:** “avise quando este download terminar”, com alvo explícito, duração máxima, intervalo, custo limitado, indicador visível e parada. Preferir estado estruturado do aplicativo quando disponível; imagens devem preservar incerteza.
2. **Controle de computador com verificação por etapa:** aproveitar as ferramentas existentes para observar o resultado após ações, detectar janela incorreta e recuperar falhas sem repetir efeitos. Vincular evidências ao mesmo registro de execução.
3. **Voz em chamadas:** separar microfone do proprietário e áudio capturado do PC. Fala de terceiros e áudio reproduzido não devem aprovar ações. Integração com Discord/Teams exige validação real de dispositivos, eco e roteamento.
4. **Calibração por aplicativo:** guardar controles e contexto apropriados ao aplicativo, com recuperação quando a janela ou interface mudar, em vez de confiar em coordenadas antigas.
5. **Arquivos e acesso remoto:** comparar o fluxo existente de anexos e acesso remoto antes de adicionar componentes; manter bloqueio, origem das solicitações e recibos de execução coerentes.

Companheiro flutuante, animações e presença na área de trabalho permanecem adiados conforme a preferência de Jean. Esta entrega não é uma migração integral do Capri e não acrescenta integração com Discord, transmissão remota ou vigilância contínua da tela.
