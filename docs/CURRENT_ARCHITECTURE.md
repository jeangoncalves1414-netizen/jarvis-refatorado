# Arquitetura atual do Jarvis

## Produtos e responsabilidades

```text
app/                    PC local: agente, automação Windows e API HTTP
frontend/               Painel React usado pelo desktop e pelo WebView Android
deploy/cloudflare/      Serviço independente do celular: Worker + D1
mobile_app/             App Android: alarmes, microfone, TTS/STT nativo e ponte
```

O React não é um segundo produto: ele é a interface comum. O Android só deve
conter capacidade nativa, permissões, tarefas de segundo plano e a ponte com o
Worker. A automação de Windows permanece no PC; o Worker não deve executar
comandos arbitrários no computador.

## Fluxos principais

```text
PC:       React -> API local -> Orchestrator -> catálogo de ferramentas -> Windows/serviços
Celular:  React WebView -> Worker -> D1/provedores de voz e IA
Android:  recursos nativos <-> WebView/Worker (alarme, STT, TTS, notificações)
```

Uma ponte remota é sempre opcional e autenticada. No PC, comandos sem alvo
explícito atuam no PC. No celular, comandos sem alvo explícito atuam no Android.
Se o destino contrário foi citado mas a ponte não existe, o sistema informa a
limitação em vez de usar um fallback silencioso.

## Limites de código

| Área | Deve conter | Não deve conter |
| --- | --- | --- |
| `app/ui/panel/server.py` | HTTP, auth, estáticos, despacho | regra de negócio de rota |
| `app/ui/panel/api/` | handlers e validação HTTP por domínio | estado global importado do servidor |
| `app/agent/` | prompts, plano, execução e recibos | detalhes de WebView/React |
| `app/services/` | integrações e hardware | lógica de apresentação |
| `app/storage/` | repositórios e configurações | decisões de UI |
| `frontend/src/pages/` | composição de tela | clientes HTTP extensos ou lógica reutilizável |
| `frontend/src/hooks/` | estado por recurso | um hook universal para domínios distintos |
| `deploy/cloudflare/src/` | rotas, domínio e D1 do mobile | execução local do Windows |

## Convenções de manutenção

- Mova uma família de rotas ou uma funcionalidade por vez. Primeiro caracterize
  a resposta atual, depois extraia, mantendo URL e JSON iguais.
- Mantenha uma fachada compatível quando separar módulos centrais, como
  `runtime_settings.py`; isso permite migrar consumidores em etapas.
- Prefira contratos HTTP e tipos compartilhados por documento/fixture a duplicar
  regras entre Python, TypeScript e Kotlin.
- Código novo deve nascer no módulo da funcionalidade; não aumente arquivos
  centrais sem uma razão de infraestrutura.
