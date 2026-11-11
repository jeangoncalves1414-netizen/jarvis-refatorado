# Detecção: referências e reaproveitamento do navegador

## Referências consultadas

- [Video Link Extractor — background.js](https://github.com/jrcramos/video_link_extractor/blob/main/background.js): observação de respostas, classificação por URL/MIME e armazenamento de resultados por aba. Não demonstra busca instantânea de centenas de páginas novas.
- [M3U8D](https://github.com/royswift2007/m3u8-video-sniffer): descreve navegador persistente, captura de requisições/respostas e callbacks da página. A sessão já aberta evita iniciar todo o navegador para cada descoberta.
- [TMDB Player](https://github.com/TomasTNunes/TMDB-Player): adiciona um botão ao TMDB e abre servidores selecionados; não equivale a um indexador geral da web.
- [Playwright: isolamento](https://playwright.dev/python/docs/browser-contexts): contextos isolam cookies e armazenamento mesmo compartilhando o processo do navegador.

Não foi copiado código dessas referências. Não há evidência suficiente para atribuir a velocidade do Seekee a IA.

## Alteração aplicada

O detector automático abria Chromium por URL. Agora até quatro trabalhadores mantêm seus próprios navegadores durante a varredura. Cada trabalhador cria e usa Playwright na mesma thread. Cada URL recebe um contexto novo, fechado ao terminar, preservando isolamento de cookies, armazenamento e callbacks. O relay continua recebendo somente o snapshot da sessão daquela inspeção.

Após 30 segundos sem trabalho, o trabalhador encerra Chromium e Playwright. Uma nova tarefa os reinicia. Falhas também descartam o navegador daquele trabalhador. O encerramento do processo agenda a liberação dos trabalhadores. A admissão continua limitada a quatro inspeções, com espera máxima de 20 segundos por vaga.

A verificação rápida começa na confirmação da navegação (`commit`), observando o DOM e a rede enquanto a página carrega. A verificação completa mantém a espera por `DOMContentLoaded` e sua janela maior de observação. Não se esperam scripts secundários para devolver uma fonte já observada na verificação rápida.

## Evidências

Benchmark local com Chromium real, vídeo sintético, 12 páginas com botão conhecido e quatro tarefas simultâneas:

| Execução | Tempo total | Detectados |
| --- | ---: | ---: |
| Novo navegador por página | 6,00 s | 12/12 |
| Navegadores reaproveitados, incluindo inicialização | 3,23 s | 12/12 |

Ambas as execuções usam a mesma rotina de inspeção rápida; a diferença medida é o ciclo de vida do navegador. Uma medição, sem extrapolação para a internet: aproximadamente 46% menos tempo neste cenário.

Regressões novas verificam captura antes de um script deferido de quatro segundos, reaproveitamento do mesmo navegador, ausência de contextos/cookies remanescentes, descarte por ociosidade, recuperação após erro e encerramento das threads. A suíte existente cobre players alternativos, iframes, links de reprodução, cookies e relay MP4/HLS.

Limites: não foi repetida a validação dos sites externos enviados pelo usuário nesta alteração. Não há promessa de 100 sites instantâneos; rede, scripts, interação e disponibilidade dos hosts ainda limitam a captura. Reutilizar processos não aumenta a cobertura da busca nem adiciona suporte a DASH.
