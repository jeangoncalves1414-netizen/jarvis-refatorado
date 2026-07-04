# Arquitetura e Módulos

## Arquitetura proposta
A arquitetura do novo projeto deve seguir uma organização modular com camadas bem separadas:

- Core: configuração, ciclo de vida, estado global.
- Agent Runtime: orquestração, decisão, planejamento e execução.
- Domain Modules: funcionalidades específicas do produto.
- Services: integrações com APIs, banco de dados e recursos externos.
- UI: painel principal e módulos visuais.
- Storage: persistência e memória.

## Estrutura de módulos recomendada

```text
app/
  core/
  agent/
  domain/
  services/
  ui/
  storage/
  shared/
  main.py
```

## Responsabilidades por módulo

### app/core
- carregar configurações,
- inicializar estado global,
- controlar ciclo de vida,
- lidar com logging e erros.

### app/agent
- receber intenção do usuário,
- gerenciar contexto,
- decidir qual módulo usar,
- orquestrar ações.

### app/domain
- voz,
- arquivos,
- produtividade,
- automação,
- visão,
- notas,
- finanças,
- memória.

### app/services
- LLM,
- TTS/STT,
- visão computacional,
- armazenamento,
- integrações externas.

### app/ui
- painel principal,
- widgets,
- navegação,
- componentes reutilizáveis.

### app/storage
- banco local,
- memória persistente,
- snapshots,
- estado do agente.

## Regras arquiteturais
- cada módulo deve ter uma responsabilidade única,
- não misturar lógica de UI com lógica de domínio,
- evitar arquivos gigantescos,
- manter interfaces pequenas e claras,
- usar dados estruturados e bem definidos.
