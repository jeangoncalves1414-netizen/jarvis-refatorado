# Documentação atual

Use este índice como ponto de entrada. Documentos de investigações antigas são
histórico, não especificação do comportamento atual.

| Assunto | Fonte de verdade |
| --- | --- |
| Mapa de código e limites entre produtos | `CURRENT_ARCHITECTURE.md` |
| Mobile independente, deploy e segredos Cloudflare | `CLOUDFLARE_MOBILE_INDEPENDENTE.md` |
| Estado, decisões e limitações do produto | `PROJECT_CONTINUITY.md` |
| Pendências funcionais priorizadas | `PENDENCIAS_DO_PAINEL.md` |
| Planos incrementais de engenharia | `../plans/README.md` |
| Instruções rápidas para pessoas/agentes | `../AGENTS.md` |

## Princípios atuais

1. O painel React é a interface compartilhada; o Android acrescenta apenas as
   capacidades nativas que uma página web não tem.
2. O Worker Cloudflare mantém chat, voz e organização pessoal do celular mesmo
   com o PC desligado. Automação Windows continua local ao PC.
3. Cada comando tem um alvo. No PC, a omissão significa PC; no celular, a
   omissão significa celular. Cruzar de dispositivo exige pedido explícito.
4. Ações sensíveis precisam de uma fronteira de autorização e recibo; prompts
   nunca são uma fronteira de segurança.
5. Artefatos compilados são publicados de forma deliberada e não editados à mão.
