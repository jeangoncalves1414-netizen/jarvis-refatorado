# Visão Computacional e Interface

## Visão computacional
O projeto deve contar com uma camada de visão computacional leve para:
- capturar a tela,
- extrair contexto visual,
- resumir o que está sendo exibido,
- auxiliar em tarefas visuais simples.

## Requisitos da camada visual
- leve,
- separada da lógica do agente,
- não dependente de arquivos gigantescos,
- simples de trocar por outro backend no futuro.

## Estratégia recomendada para o painel
O novo painel deve:
- ser moderno,
- ser leve,
- ser modular,
- ser fácil de expandir,
- ter componentes isolados por responsabilidade.

## Estrutura recomendada do painel
- header,
- sidebar,
- área principal,
- widgets de contexto,
- lista de tarefas,
- resumo do agente,
- histórico recente,
- módulo de voz,
- módulo de visão.

## Engine visual recomendada
Para esse projeto, a melhor abordagem é uma engine visual leve baseada em:
- HTML/CSS/JS simples,
- componentes reutilizáveis,
- comunicação com o backend via API simples,
- sem dependência de framework pesado no início.

## Objetivo do visual
O painel não deve ser apenas bonito; ele deve:
- mostrar o estado do agente,
- facilitar o entendimento do sistema,
- reduzir o esforço de manutenção,
- permitir futuras adições sem reescrever tudo.
