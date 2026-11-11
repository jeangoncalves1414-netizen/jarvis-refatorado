# Análise de fluxo e arquitetura (versão curta)

Feita em 7/11/2026 sobre o HEAD `21d9e12`, só lendo código. Nada foi executado. O desenho completo e o roteiro estão em `plans/017-plano-mestre-do-aplicativo.md`. Esta versão cobre veredito, diagrama, fluxos, autonomia e problemas principais. Eficiência detalhada e recomendações longas ficaram de fora por orçamento (ver seção 8).

## 1. Veredito

1. **Conexão:** as peças principais estão ligadas (comando `/` → janela, chat → orquestrador → Action Kernel → Central), mas há caminhos paralelos que fogem do Kernel: voz, `/api/browser/run` (`app/ui/panel/server.py:1737-1747` chama a ferramenta direto), `/api/finance` e passos internos de Swarm e Racing.
2. **Serve ao que ela quer?** Serve bem para chat com controle de PC e janelas sem IA. Não serve ainda para rotinas, gatilhos, palmas, proatividade completa e celular conectado ao PC: não existem ou estão quebrados.
3. **Fluxos:** curtos e bons quando há comando (`/financas`); com atrito quando passam pelo modelo (aprovação sempre igual, sem lembrar a escolha, sem desfazer); a sequência por etapas para quando uma etapa é aprovada.
4. **IA:** autonomia entre os níveis 1 e 2 de 5. Executa uma ferramenta por vez e várias etapas (até 8 por padrão, de 1 a 20, `react_loop.py:54`), pede aprovação nos riscos altos, mas não tem rotinas, permissões duradouras, nem age por conta própria de forma fechada. A hipótese do item C2 procede.

## 2. Como tudo se conecta (código real)

```mermaid
flowchart TD
  subgraph UI[Interface React]
    CH[Chat e compositor]
    SL[Menu / e Paleta<br/>commands/registry.ts]
    WN[Janelas<br/>windows/registry.ts]
    CF[Configuracoes]
    CE[Central de Execucoes]
  end
  subgraph TR[Transportes]
    REST[REST /api/*]
    STR[/api/chat/stream]
    WS[WebSocket legado<br/>so loopback]
  end
  subgraph AG[Agente]
    OR[Orquestrador<br/>orchestrator.py]
    MD[Modos: geral, tutor, por etapas, swarm, racing]
    RT[Roteamento de modelos]
    TC[Catalogo 55 ferramentas<br/>catalog.py / registry.py]
    AK[Action Kernel<br/>action_executor.py]
  end
  subgraph ST[Armazenamento]
    AJ[(action_journal.sqlite3<br/>historico local)]
    DB[(lifestyle.db, cofre, memorias)]
    SB[(Supabase evolute_snapshots)]
  end
  VZ[Voz: TTS, STT, ligacao, wake word]
  PA[ProactiveDaemon / scheduler horario]
  MO[Celular: WebView]
  CH --> STR --> OR --> MD --> RT
  OR --> AK --> TC
  AK --> AJ --> CE
  SL --> WN
  WN -->|/api/finance direto| DB
  WN -->|/api/controls/run| AK
  VZ -->|texto| STR
  VZ -.->|ferramentas sem historico| TC
  CF --> REST --> SB
  PA -->|so desktop| OR
  MO --> REST
  MO -.-> WS
  REST -.->|/api/browser/run: sem Kernel| TC
```

**Desvios marcados:** (1) voz → ferramenta fora do histórico (C6); (2) `/api/browser/run` sem Kernel (`server.py:1737-1747`); (3) o executor do turno recebe todas as ferramentas registradas (`orchestrator.py:497-499` e `:609-611`), e a lista por modo só filtra o que o modelo vê (C3); (4) dois caminhos de execução no turno (nativo e por marcadores, `orchestrator.py:497` e `:609`); (5) memória de preferência grava sem recibo (`orchestrator.py:280`); (6) `wake_word` sai por WebSocket legado e nenhum hook React o trata; (7) peças soltas: Tool Forge sem botão, automação de desktop não registrada, Composio/Kasa desligados, `app/core/scheduler.py` só roda resumo por hora.

| Origem → destino | Passa pelo Kernel? | Aparece na Central? |
|---|---|---|
| Chat → ferramenta | Sim | Sim |
| Janela Controles → `/api/controls/run` | Sim (`controls.py:3-6, 51`) | Sim |
| Janela Finanças → `/api/finance` | Não (leitura/registro direto) | Não |
| Voz → ferramenta | Parcial (via chat) | Não (C6) |
| `/api/browser/run` | Não | Não |
| Swarm e Racing (passos internos) | Não | Parcial |
| Rotina/gatilho/palma | Não existe | Não existe |
| Celular → API | Sim, quando usa o chat | Sim; direto do aparelho quebra (S4) |

## 3. Fluxos (nota hoje)

Detalhe passo a passo dos fluxos-alvo na seção 5 do plano 017.

| Fluxo | Modelo / aprovação hoje | Nota |
|---|---|---|
| a) "abre minhas finanças" | 1 modelo, 0 aprovações | bom (poderia ser 0 modelo) |
| b) `/gastos` | 0 modelo, 0 aprovações | bom |
| c) "anota que gastei 50 reais" | 1 modelo, risco `low` por padrão do `BaseTool`; `finance_tool` não está em `TOOL_CATALOG` | com atrito (sem alvo/efeito nem desfazer) |
| d) "fecha o Spotify" | 1 modelo, aprovação conforme o risco do alvo (`catalog.py:61-66`), tela mostra pouco | com atrito |
| e) voz com ferramenta | passa pelo chat; fora do histórico | com atrito |
| f) "lembra que prefiro X" | grava por palavra-chave, sem modelo extra e sem fonte visível (`orchestrator.py:280-283`) | com atrito |
| g) várias etapas | 1 modelo por etapa; aprovar uma etapa encerra a sequência | com atrito |
| h) proativo | `ProactiveDaemon` só no desktop (`main.py:190-193`); ciclo não fechado | com atrito |
| i) rotina agendada | — | inexistente |
| j) celular | chat direto quebra com resposta vazia; sem modo conectado | quebrado |

## 4. Autonomia e controle

- **Nota: 1,5 de 5.** Faz uma ferramenta por vez no chat e várias etapas no modo por etapas, com aprovação nos riscos `high`/`critical`. Não tem rotinas confiáveis (nível 3), nem proatividade fechada (nível 4), nem cria ferramentas (nível 5, o Tool Forge não tem botão).
- **Faz sozinha:** ferramentas `observe` e `low`, abrir janelas, registrar lançamentos e notas, controlar volume/mídia.
- **Sempre pergunta:** `high` e `critical` (arquivos, scripts, terminal, WhatsApp, alvos de risco alto). Sem lembrar a decisão.
- **Segundo plano:** só o resumo diário (uma chamada ao modelo por dia, verificada a cada hora, `orchestrator.py:237-275`) e o `ProactiveDaemon` no desktop. Não executa nada por conta própria de forma auditável.
- **Aprende:** grava preferências por palavra-chave e conversas no perfil (`importance=0.25`); o uso na resposta não é citado.
- **Hipótese C2:** muita autonomia sem aprovação constante **exige** permissões duradouras por escopo e rotinas de confiança. Procede: hoje a única alternativa a perguntar é rebaixar o risco da ferramenta inteira, o que afrouxa o controle para todos os alvos.
- **Para subir de nível sem perder controle:** concessões por escopo com validade e revogação (C2), retomar após aprovação (C8), rotinas pelo Kernel (A1/A2), proatividade com consentimento (A8).

## 5. Os 5 problemas principais

1. **Caminhos fora do Kernel:** voz, `/api/browser/run`, Swarm/Racing. Quebra a promessa "tudo auditável". (C6, C10, AQ1)
2. **O servidor não aplica a lista de ferramentas por modo:** o executor aceita todas as 55 registradas. (C3)
3. **Aprovação pobre e sem memória de escolha:** a usuária cansa de aprovar e não ganha autonomia. (C1, C2)
4. **Rotinas, gatilhos e palmas não existem;** o cadastro de comandos só está no frontend. (A1, A2, AQ3)
5. **Ferramentas de módulos pessoais fora do catálogo de risco** (`finance_tool`, `habit_tool`, `task_tool`, `lifeos_tool`) e **celular quebrado** (S4, M1, M2). (AQ2)

## 6. Eficiência (só o que a leitura mostra)

- `app/agent/prompts.py`: 273 linhas, 14 KB para todos os modelos de prompt; o prompt de sistema montado por turno é uma parte disso mais o perfil e as ferramentas. Tamanho exato por modo não foi medido.
- 55 ferramentas registradas (`registry.py`); no Groq, fora do modo tutor, vai um subconjunto de 15 nomes "core" (`registry.py:217-222`); nos demais, o filtro do modo.
- Chamadas ao modelo por turno: 1 no modo geral, mais 1 por ferramenta no ciclo nativo; N no modo por etapas (até 8 por padrão); 1 por dia no resumo episódico. Uso do reflexion e do destilador de habilidades em segundo plano **não foi confirmado**.
- Desperdício claro: abrir janela ou executar comando conhecido hoje pode gastar uma chamada que o PB2 evitaria (fluxos a e e).

## 7. Recomendações

Ver seções 2, 7 e 8 do plano 017: peças-base, fases F0 a F8, lote 3 e definição de pronto.

## 8. O que não foi verificado

Nada foi executado. Ficam para depois: testes, medições de fluidez, hardware, provedores reais, Supabase real, APK, tamanho exato de prompt e ferramentas por modo, e o uso real de reflexion/destilador em segundo plano. Também não foi lido o código de `ProactiveDaemon`, `server.py` por inteiro nem os planos 001 a 016 um a um.
