# Aberturas repetidas e interpretação do pedido por voz

## Evidência local

O diário de ações e o histórico da conversa confirmam três execuções de `web_search/open_url` no pedido `run_4ddaf5fbb0fa4a3a85d7a2e188dc25c4`: Roblox sem www, com www e sem www novamente. Nenhuma abertura do Spotify nesse pedido. A reclamação seguinte gerou uma quarta abertura em outro pedido.

O pedido anterior de abrir Google, abrir Spotify, esperar e fechar Spotify registrou as quatro ações. O verificador contou “aguarde 10 segundos e depois de 10 segundos” como duas esperas e marcou uma pendência falsa.

## Correções

- Reconhecer “tá quero...” e “ao mesmo tempo abrir...” como pedido de várias ações; não dividir nomes de domínio pelo ponto.
- Verificar os alvos Roblox/Google e domínios explícitos, além de Spotify/YouTube. Pedidos com “ao mesmo tempo” sem espera podem ser conferidos em qualquer ordem; isso não introduz execução paralela de ferramentas.
- Tratar a referência consecutiva “e depois de N segundos” como a mesma espera; duas ordens explícitas de esperar continuam duas etapas.
- Reutilizar o recibo de aberturas consecutivas já confirmadas no mesmo executor/turno. Canonicalizar www e barra na raiz, preservando protocolo, porta, caminho, query e fragmento. Outro comando encerra essa reutilização. Pedidos explícitos de repetição e efeitos não confirmados não usam o atalho.
- Não duplicar recibos/respostas ao reutilizar uma abertura.
- Perguntas retrospectivas reconhecidas consultam os últimos recibos da conversa sem executar ferramentas. O executor também recusa execução nesses pedidos.

## Validação

97 testes de política, executor, conversa, loop e contexto passaram; mais uma reprodução integrada passou: o modelo simulado solicita Roblox três vezes, tenta encerrar sem Spotify e depois corrige a pendência. Foram executadas somente uma abertura de Roblox e uma de Spotify, com dois recibos.

Compilação Python e diff-check aprovados. Nenhum aplicativo real foi aberto ou fechado nos testes. A interpretação de linguagem continua baseada em regras limitadas; os testes não garantem todas as formulações possíveis. Mudanças somente no backend: reiniciar completamente o Jarvis para carregar.
