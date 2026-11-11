# Isolamento do histórico e recuperação de memória — 10/11/2026

## Evidência

- O chat `a1886d3e-84e4-4be5-a40e-1fcc87b0dd75` começa com `teste` e contém a resposta incorreta sobre a primeira mensagem.
- `Olá quero que você abra` é a primeira mensagem do chat `d2f88101-51fc-4a15-87f0-daaf73a2e579` e também estava em `data/memory.json`, como `general_preference`.
- `_remember_preferences` classificava qualquer `quero que você` como preferência. Todas as preferências eram incluídas no prompt de outros chats.
- Além disso, consultas semânticas globais e de conversas privadas eram automáticas. O provedor Groq recortava o histórico às dez mensagens recentes, enquanto o servidor descartava mensagens salvas acima de quarenta entradas.
- Não é necessário supor troca de IDs de sessão para explicar a contaminação: existe um caminho explícito do registro errado ao prompt. Sem o prompt exato daquela chamada, não se atribui exclusividade causal a um componente do modelo.

## Alterações

1. Preferências exigem linguagem explícita e duradoura. Comandos avulsos não são gravados como preferências nem disparam extração apenas por conter `quero que você`.
2. Preferências legadas inválidas são filtradas na leitura do contexto, sem apagar o arquivo original. Conferência local: oito registros antigos, zero elegíveis para personalização automática.
3. Busca semântica global e memória privada de conversas exigem intenção de recuperação. Pedidos sobre este chat e pedidos negativos não disparam a busca. Recuperação intencional preenche `memory_lookup`, já exibido pelo painel.
4. Perguntas simples sobre a primeira/última mensagem consultam diretamente o histórico da sessão, antes dos limites do modelo e sem ferramentas. Perguntas mais amplas sobre este chat recebem a instrução de não preencher lacunas com memórias; preferências, perfil, fatos e contexto situacional não entram nesses pedidos.
5. Histórico persistido deixa de ser cortado em quarenta mensagens; o contexto enviado ao modelo permanece limitado. Não se recuperam automaticamente mensagens apagadas anteriormente.
6. Memórias vetoriais novas extraídas de falas carregam a origem `session_id`.

## Verificação

- 179 testes passaram em contexto, memória, parâmetros de ferramentas, isolamento por identidade, runtime, loop e livecall.
- Após acrescentar casos de negação e conversas anteriores, 48 testes de política de contexto/memória passaram (incluem seis casos adicionais; 185 casos distintos entre as duas execuções).
- Compilação Python e verificação do diff sem erros.
- Conferência somente de leitura dos dados reais: a função corrigida responde `teste` para a pergunta relatada.
- Não houve exclusão de memórias, alteração dos chats existentes, chamada a provedor ou gravação de áudio. Nenhuma dependência foi adicionada. O aplicativo não foi reiniciado.

## Limites

- A interpretação de intenção usa regras locais; perguntas de histórico fora dos formatos simples ainda passam pelo modelo com o escopo restrito. Não é garantia de ausência de alucinações.
- Preferências legítimas continuam personalizando pedidos comuns; conversas brutas deixam de ser recuperadas automaticamente pelo caminho semântico/privado.
- Histórico já perdido em versões anteriores não pode ser reconstruído por estas alterações.
- Validação em chamada real depende de reiniciar o processo desktop, inclusive a instância na bandeja.
