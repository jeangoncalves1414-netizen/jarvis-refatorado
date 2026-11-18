# Guia curto de manutenção

Leia `docs/README.md` antes de alterar uma área. O projeto tem quatro produtos:

- `app/`: agente e servidor local do PC (Python).
- `frontend/`: painel React compartilhado pelo desktop e WebView Android.
- `deploy/cloudflare/`: backend independente do celular (Worker + D1).
- `mobile_app/`: recursos e integrações nativas Android (Kotlin).

## Regras de alteração

- Não altere `frontend/dist`, `mobile_app/app/src/main/assets` ou
  `deploy/cloudflare/public` manualmente. São artefatos publicados; gere-os a
  partir de `frontend/src` e só os atualize quando a publicação/APK fizer parte
  da entrega.
- Preserve contratos HTTP existentes. Antes de mover rota, handler ou formato
  de resposta, crie ou atualize um teste de contrato.
- O desktop é o destino padrão de comandos recebidos no PC; o Android é o
  destino padrão de comandos recebidos no celular. O outro dispositivo exige
  menção explícita.
- Recursos Windows não devem ganhar fallback silencioso no celular. Recursos
  Android não devem rodar no PC sem o alvo explícito e a ponte autorizada.
- Não coloque segredos em fonte, documentação, fixtures, APK ou logs.

## Verificação por área

- Python: `python -m compileall -q app` e `python -m pytest -q <testes focados>`.
- React: em `frontend`, use o gerenciador definido no CI e rode `npm run build`.
- Worker: em `deploy/cloudflare`, `bun run check`.
- Android: `mobile_app\\gradlew.bat -p mobile_app :app:assembleDebug` quando
  houver mudança Kotlin/manifest/recursos.

## Limites de módulos

- `app/ui/panel/server.py`: HTTP, autenticação, arquivos estáticos e despacho;
  regras de domínio ficam em `app/ui/panel/api/` ou serviços.
- `app/agent/`: intenção, plano e execução auditável; não conhece detalhes de UI.
- `app/services/` e `app/storage/`: integração e persistência, sem estado React.
- `frontend/src/`: organize por funcionalidade (`chat`, `lifeos`, `voice`,
  `settings`, `remote`) e mantenha páginas como composição, não como depósito de
  regras de rede.
- `deploy/cloudflare/src/`: autenticação, roteamento, domínio e persistência em
  módulos separados; nunca introduza execução arbitrária no PC.
