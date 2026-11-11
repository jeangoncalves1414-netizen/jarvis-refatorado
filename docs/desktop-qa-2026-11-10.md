# Teste do desktop — 10/11/2026

## Resultado

Teste amplo do código atual e do servidor Jarvis aberto no PC. Não equivale a certificação de todas as integrações e do hardware.

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa, em cópia isolada | 1.313 passaram, 8 falharam, 24 desmarcados; 44 subtestes passaram |
| Reexecução dos módulos envolvidos após diagnóstico e ajustes dos testes | 43 passaram (10 + 29 + 4); todas as 8 falhas iniciais resolvidas nessa reexecução |
| Playwright: conversa e chamada de voz simulada | 30 passaram |
| Roteiros de interface `.smoke.cjs` | Os 8 passaram; dois precisaram de atualização de expectativas |
| Navegação com backend real | 13 telas carregadas, sem erros JavaScript, respostas HTTP de erro ou overflow horizontal observados |
| Build frontend | Passou; alerta de chunks grandes |
| Build Evolute | Passou; alerta de chunks grandes |
| Verificação de whitespace dos arquivos de teste alterados | Passou |

A suíte Python inteira não foi repetida após os ajustes: foram reexecutados os módulos afetados. Os testes desmarcados são os de integração/rede/hardware/mobile excluídos pela configuração padrão.

## Comandos realmente executados pelo agente

Usado o modelo configurado no aplicativo, com arquivos sintéticos em `scratch/desktop-qa/`.

| Fluxo | Resultado observado |
| --- | --- |
| Ler arquivo no modo geral | Passou: retornou um código aleatório existente somente no arquivo |
| Ler arquivo pelo chat da interface | Passou com backend e modelo reais |
| Criar pasta com `file_manager` | Passou; existência da pasta conferida no disco |
| Ler arquivo inexistente | Falhou corretamente, com recibo de arquivo não encontrado, sem criar arquivo |
| Criar arquivo de texto | Falhou: agente escolheu `script_runner`, que bloqueou `open(...)` |
| Ler arquivo em “Execução por etapas” | Falhou: respondeu que não tinha ferramenta para leitura |
| Listar hábitos | `habit_tool` concluiu com sucesso |
| Consultar finanças | `finance_tool` concluiu após término do limite temporário de uso |
| Buscar anotações | `vault_search` concluiu; pesquisa por identificador sintético |
| Abrir janela financeira por comando no chat | Passou; janela apareceu na interface real |

## Problemas funcionais encontrados

1. **Capacidades inconsistentes entre modos.** O modo geral lê arquivos, mas o modo ReAct explícito usa `REACT_TOOLS`, sem `file_manager`. Também não inclui os principais recursos pessoais. O usuário pode selecionar um modo de execução e perder capacidades que estavam disponíveis na conversa comum. Evidência: `read-response.json` versus `read-general-response.json`.
2. **Não há escrita genérica de arquivo no `file_manager`.** Ele oferece listar, ler e criar pasta. Ao pedir criação de texto, o modelo escolheu um script bloqueado. Não foi removida a proteção nem tentado contorná-la. Uma solução futura deve ser uma operação de escrita com escopo e validação próprios.
3. **Limite do provedor aparece como chave ausente.** Após algumas chamadas reais, o aplicativo respondeu “GROQ_API_KEY não encontrada”. A saúde registrou erro 429; após esperar, a mesma configuração voltou a funcionar. `KeyRotator.get_key()` retorna vazio quando todas as chaves estão em cooldown, e o orquestrador interpreta vazio como configuração ausente. O diagnóstico deveria diferenciar esses estados.
4. **Automação nativa não pôde ser validada.** A janela Jarvis foi localizada, mas a captura falhou duas vezes (`FrameArrived timed out` / `window capture timed out`). A interface foi então exercitada por Chromium contra o mesmo servidor local. Isso não comprova bandeja, atalhos globais, arrastar janela, minimizar/restaurar ou comportamento específico do WebView.

Nenhuma dessas restrições funcionais foi alterada nesta rodada; as alterações de código foram nos testes.

## Diagnóstico das oito falhas Python iniciais

| Teste | Causa / tratamento |
| --- | --- |
| Smart Drop Zone | Dependia da pasta Downloads real e poderia mover arquivos pessoais. Agora cria pasta e conteúdo temporários e verifica o arquivo movido. |
| Life OS: água e hábito | Presumia a existência do hábito `agua` e podia escrever no Life OS pessoal. Agora usa isolamento e cria seu próprio hábito. |
| Provedor ativo | Esperava Groq sem configurar chave no ambiente isolado. Agora fornece chave fictícia somente para testar seleção, sem chamada externa. |
| Backup APK | O arquivo não havia sido copiado para o ambiente isolado. O original existe, com 14.728.272 bytes; copiado e teste repetido com sucesso. |
| Memória de preferências | Esperava intenção `general` quando não há chave. A classificação atual é `error`; mantém a verificação de persistência da preferência local. |
| Resultado de ferramenta com falha | Esperava detalhe na resposta principal. O detalhe está no recibo estruturado; agora verifica recibo, falha persistida e resposta sem falsa confirmação. |
| ENEM sem chave | Expectativa antiga de `general`; alinhada à classificação `error`, mantendo verificação da mensagem. |
| Voz/orquestrador sem chave | Mesma expectativa antiga; alinhada à classificação `error`. |

Nos roteiros de interface, o teste do loop passou a aceitar timestamp/atividade no histórico, e o teste do workspace passou a fornecer recibo de ferramenta e revelar os controles por hover antes de clicar. Não foram removidas as verificações de cancelamento, persistência, falhas ou navegação.

## Cobertura de interface

Telas reais: Início, Execuções, Automações, Conhecimento, Integrações, Saúde, Estudos, Life OS, Calendário, Painel pessoal, Métricas, Perfis e Configurações. Conversas foi exercitada separadamente com comandos reais.

Testes simulados cobrem também: menu de comandos, busca/paleta, aprovações, erros e novas tentativas, cancelamento, histórico, retomada sem duplicar, isolamento entre conversas, rascunhos, notas, hábitos, recibos financeiros, filas de popups, movimento reduzido, telas de 360–390 px e várias condições de corrida na chamada de voz.

## Limites e integrações

- Microfone, alto-falante, reconhecimento de fala humana e palavra de ativação não tiveram validação física. Os 30 testes de voz/conversa usam simulações. A página Saúde informa escuta configurada, o que não prova transcrição ou reprodução real.
- A suíte registrou uma tentativa de Edge TTS com erro HTTP 403 ao encerrar. Isso não valida nem reprova o provedor TTS efetivamente escolhido pelo usuário; precisa de teste de áudio dedicado.
- Não foram enviados WhatsApp/Telegram/e-mails, nem acionados dispositivos físicos, desligamento/reinício ou operações financeiras externas.
- Saúde informa Telegram e Kasa sem bibliotecas, Home Assistant não configurado, Composio não configurado/registrado e Spotify não detectado pelo caminho tradicional. MCP tem dois servidores configurados, mas a disponibilidade efetiva de suas ferramentas não foi testada.
- Hábitos, finanças e notas foram consultados no backend real. Operações de escrita dessas áreas foram testadas com fixtures/mocks, preservando os registros pessoais.
- Os testes reais criaram conversas e registros de execução de QA, além da pasta sintética. Eles foram mantidos para inspeção. O aplicativo permaneceu aberto; não foi reiniciado nem foram trocados provedores ou chaves.

## Evidências locais

- `scratch/desktop-qa/backend-initial.xml`: relatório da execução Python inicial.
- `scratch/desktop-qa/backend-initial.log`: saída inicial, com URL do serviço de voz omitida.
- `scratch/desktop-qa/navigation.json`: resultado por tela.
- `scratch/desktop-qa/health-summary.json`: disponibilidade reportada pelo aplicativo.
- `scratch/desktop-qa/live-file-chat.png`: leitura pelo chat real.
- `scratch/desktop-qa/live-finance-window.png`: janela aberta pelo agente.
- `scratch/desktop-qa/*-response.json`: respostas dos comandos reais. Podem conter dados locais consultados; manter localmente.

Prioridade sugerida: corrigir o diagnóstico de cooldown, tornar claras as capacidades de cada modo e implementar escrita segura de arquivos antes de ampliar as promessas do agente. Depois, validar voz e ciclo de vida da janela nativa em uma sessão de captura funcional.
