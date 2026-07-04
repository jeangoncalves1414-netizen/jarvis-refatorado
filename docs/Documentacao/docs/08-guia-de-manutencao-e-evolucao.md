# Guia de Manutenção e Evolução

## Objetivo
Tornar futuras alterações simples, previsíveis e seguras.

## Regras para editar o projeto
- nunca adicione lógica nova em um arquivo já muito grande,
- sempre crie um novo módulo quando a responsabilidade aumentar,
- mantenha o painel desacoplado do núcleo do agente,
- documente cada mudança em um arquivo ou seção apropriada,
- teste mudanças pequenas antes de expandir.

## Boas práticas
- nomear módulos por responsabilidade,
- fazer interfaces pequenas,
- separar modelos de serviços,
- evitar dependências circulares,
- manter o código enxuto.

## Como evoluir sem bagunça
1. entenda o problema,
2. identifique o módulo certo,
3. implemente a menor mudança possível,
4. documente a alteração,
5. valide com testes ou execução simples.

## Checklist de manutenção
- [ ] a mudança ficou em um módulo específico?
- [ ] a documentação foi atualizada?
- [ ] a nova funcionalidade foi testada?
- [ ] a UI continua simples e modular?
- [ ] o agente continua compreensível?
