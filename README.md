# Jarvis Rebuild

Este projeto é uma reconstrução modular de uma assistente pessoal de desktop com foco em:
- voz e interação natural,
- automação de tarefas,
- memória e contexto,
- painel novo e extensível.

## Estrutura inicial
- app/core: ciclo de vida e configuração da aplicação
- app/agent: orquestração do agente
- app/domain: módulos de domínio (voz, arquivos, produtividade)
- app/services: integrações externas e adaptadores
- app/ui: painel web simples e modular
- tests: validação inicial dos fluxos principais

## Como executar

```bash
python -m app.main --demo
```

ou, após instalar as dependências:

```bash
jarvis-rebuild --demo
```
