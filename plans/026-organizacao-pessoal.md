# Organização pessoal — implementação

Escopo autorizado: controles consistentes de hábitos, finanças, treinos, tarefas,
notas e registros pessoais; correção contextual; recibos com desfazer persistente;
Hoje compacto e personalizável; captura rápida; relações explícitas; histórico,
idempotência e prévia de alterações amplas. Testar no final com dados isolados.

Estratégia: preservar os bancos atuais, adicionar histórico por diferenças e uma
ferramenta de organização para operações avançadas. Reutilizar painéis, eventos e
popups existentes. Nunca desfazer por cima de uma edição posterior.

Checklist:
- [x] Histórico e desfazer persistentes, identidade de operação e conflitos
- [x] CRUD e correções contextuais; planejamento/sessões e registros livres
- [x] Finanças com conta, parcelas, recorrências, transferências e estornos
- [x] Relações explícitas e reversíveis, prévia de alterações amplas
- [x] Hoje, captura rápida, recibos e preferências de movimento/blocos
- [x] Testes de serviços, agente/API, build e interface com dados isolados

Resultados e limites: `docs/organizacao-pessoal-2026-11-10.md`.
