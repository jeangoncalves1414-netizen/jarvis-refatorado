# Pesquisa: detecção de mídia do Seekee e caminho para o Jarvis

Data: 2026-11-11. Escopo desta etapa: pesquisa, auditoria do detector atual e experimento local. Não representa uma nova implementação em produção.

## Conclusão

Há problemas reproduzíveis no detector atual que podem ser corrigidos. O caminho recomendado é combinar observação contínua de DOM/rede, interação normal com o player e manutenção da sessão de navegação. IA pode ajudar a interpretar consultas e organizar resultados; não há evidência pública suficiente para atribuir a extração de vídeos do Seekee a um modelo de IA.

## O que sabemos sobre o Seekee

- A [listagem do pacote correto no Google Play](https://play.google.com/store/apps/details?id=com.enzo.paulo&hl=pt_BR) anuncia busca com IA, mas não publica a arquitetura do extrator. O site vinculado é [seekee.ai](https://www.seekee.ai/). Sites de download e aplicativos homônimos não foram tratados como documentação técnica oficial.
- O recurso local `scratch/seekee-reference/assets/float_video.js` contém observadores de eventos `play`, cliques e mudanças no DOM (`MutationObserver`, linha 336). Envia URL, título, duração e dimensões pela ponte nativa `quan_function.postMessage`, incluindo o evento `video_intercepted`. É evidência direta de integração entre página e player nativo, não de inferência por IA.
- A inspeção do celular confirmou menu 1–24 de episódios e controles de qualidade, áudio e velocidade. Não revela como a lista foi produzida. Regras por site, dados estruturados, análise da página ou serviços remotos continuam hipóteses.
- A descompilação foi parcial. Classes Media3 encontradas em dependências de publicidade não provam qual motor o player principal usa. Não foi recuperada a arquitetura de busca/indexação nem confirmado um mecanismo de preservação de cookies do Seekee.

## Problemas no Jarvis identificados por leitura do código

1. `cinema_page.inspect_dynamic` espera 1200 ms, tenta `video.play()` somente nos elementos já existentes e espera mais 700 ms. Players criados posteriormente ou por um botão personalizado podem não ser vistos.
2. O navegador de detecção é fechado ao final. O frontend recebe a URL, mas não a sessão de origem. A existência da URL não garante reprodução fora dela.
3. `CinemaDiscoveryService.probe` termina quando a primeira consulta HTTP falha; a etapa dinâmica nem sempre chega a ser tentada. Um erro deve ser classificado, e não escondido como ausência de vídeo.
4. Se o HTML contém qualquer candidato direto, a inspeção dinâmica é omitida. Esse candidato pode ser apenas trailer, anúncio ou uma URL inválida.
5. Respostas `video/*` podem incluir segmentos, que não equivalem a um filme reproduzível. É necessário separar manifesto principal, variantes, segmentos e arquivos completos.
6. Há três trabalhadores no frontend e só duas vagas de navegador, com aquisição limitada a dois segundos. Esgotamento de capacidade pode resultar em lista vazia, confundida com ausência de mídia.
7. O verificador retorna `compatible: false` para timeout, cancelamento e falha de reprodução. Deve distinguir incompatível de não confirmado.

## Experimento executado

Script: `scratch/seekee-reference/detection-experiment.py`. Resultado: `scratch/seekee-reference/detection-experiment.json`. Usa apenas servidor local, vídeo sintético de 160 pixels de largura e cookie fictício. A permissão para URL local existe exclusivamente no callback desse experimento; nenhuma validação de produção foi relaxada.

| Caso | Detector atual | Navegador mantido aberto |
| --- | --- | --- |
| Vídeo imediato | Encontrou 1 fonte | Controle positivo |
| Vídeo inserido após 3,5 segundos | Encontrou 0 fontes | Vídeo carregado, readyState 4 |
| Vídeo criado por botão Play | Encontrou 0 fontes | Vídeo carregado após clique, readyState 4 |
| Vídeo que exige cookie da página | Encontrou 1 fonte | Vídeo carregado na sessão original |

A URL do último caso respondeu HTTP 200 no contexto original e 403 num contexto novo. Isso prova uma limitação da transferência de URL isolada, mas não demonstra que esse seja o motivo da falha em cada site real citado pelo usuário.

## Caminho de implementação

### 1. Resolver e diagnosticar antes de ampliar a busca

Manter um pequeno conjunto de navegadores ativos e uma fila de tarefas. Usar prazo total por página e observação por eventos, registrando iframes novos, vídeos criados por scripts e respostas de rede desde antes da navegação. Priorizar manifestos e arquivos completos; descartar segmentos como candidatos independentes. Registrar estados distintos: mídia encontrada, reproduzível no Jarvis, exige interação, timeout, bloqueado pelo site e falha de rede.

Para páginas que exigem interação, oferecer abertura em janela de navegação isolada e capturar a mídia após o clique normal do usuário. Regras testadas para botões de players conhecidos podem automatizar esse passo; cliques arbitrários em qualquer botão não são um bom substituto.

### 2. Preservar o contexto de reprodução

Preferir continuar a reprodução na própria sessão para fontes que dependem dela. Usar o player HLS existente quando o stream realmente funcionar nele. Avaliar uma sessão de mídia identificada por ID opaco, em vez de retornar apenas uma URL efêmera. Se for necessária uma ponte de streaming, limitar aos recursos detectados daquela sessão, com expiração, validação de redirecionamentos e suporte a Range/manifestações relativas. Cookies ficam no backend ou no navegador, nunca no histórico/localStorage ou em logs.

WebView2 é um caminho plausível no Windows, pois o projeto já usa pywebview, mas exige confirmar o backend efetivo e a integração nativa disponível. A janela externa não deve receber o `js_api` privilegiado do painel do Jarvis. Não basta colocar o site num iframe: isso pode ser proibido pelo próprio site e não preserva necessariamente a sessão do navegador de inspeção.

### 3. Episódios, qualidades e idiomas

Combinar JSON-LD, links e seletores do DOM com adaptadores pequenos por site, usando páginas de teste para impedir que números de paginação virem episódios. Manter identificadores de temporada/episódio e a página de origem. Ler resoluções e idiomas de manifestos e faixas efetivas. Rótulos como “dublado” ajudam na organização, mas não comprovam uma faixa de áudio. IA pode organizar rótulos ambíguos, sempre com evidência da página; não deve inventar URLs ou episódios.

### 4. Melhorar a descoberta separadamente

Combinar título em português, título original, ano e tipo de conteúdo; usar busca nativa de fontes e consultas web. Classificar resultados por correspondência ao título, presença de player e histórico recente de reprodução verificada. Evitar classificar uma página como gratuita só por pertencer a um domínio escolhido. Não é possível prometer os mesmos resultados do Seekee sem conhecer sua indexação.

### Critério para considerar resolvido

Primeiro passar os casos imediato, tardio, após clique e com sessão, mais manifesto HLS, iframe e cancelamento. Depois testar ponta a ponta no desktop em uma matriz real das fontes escolhidas: busca, episódio correto, primeiro quadro, áudio, troca de episódio e reconexão. Informar separadamente quais fontes foram verificadas e quais continuam bloqueadas. Não usar o número de URLs detectadas como medida de sucesso.

## Documentação primária consultada

- [Playwright: monitoramento de rede e espera por resposta após clique](https://playwright.dev/python/docs/network).
- [Playwright: compartilhamento de cookies entre BrowserContext e APIRequestContext](https://playwright.dev/python/docs/api/class-apirequestcontext).
- [HLS.js: recursos HLS precisam permitir CORS](https://github.com/video-dev/hls.js#cors).
- [MDN: URLs blob dependem de seu contexto de criação](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/blob).
- [Microsoft: eventos de requisição e resposta do WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/how-to/webresourcerequested).
- [Microsoft: isolamento de conteúdo externo e APIs nativas](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security).
- [Android Media3: reprodução e seleção de variantes HLS](https://developer.android.com/media/media3/exoplayer/hls).

Limite: esta pesquisa não implementou o novo ciclo de vida das sessões e não confirmou reprodução em todos os sites citados. Não envolve contornar DRM, autenticação ou desafios de acesso.

## Implementação posterior nesta sessão

Implementada a primeira etapa do plano:

- Observador instalado antes dos scripts da página, incluindo novos frames. Janela de observação de seis segundos após a navegação e acionamento apenas de controles conhecidos Video.js/JW/Plyr. Botões arbitrários continuam exigindo interação do usuário.
- Inspeção dinâmica também depois de falha HTTP ou quando o HTML já contém um candidato. Manifestos e respostas efetivamente observadas têm prioridade; fragmentos `.ts`/`.m4s` não são tratados como filmes independentes na captura de rede.
- Estados `detected`, `unconfirmed`, `blocked`, `timeout`, `busy` e `error`. Verificação no frontend distingue confirmação, timeout, cancelamento e falha. Espera por uma das duas vagas de navegador ampliada para 20 segundos; não há pool persistente de navegadores automáticos nesta etapa.
- Botão **Abrir sessão do site** nos resultados, nas mídias e na entrada por URL. Abre uma janela Chromium isolada, sem ponte nativa do Jarvis nem perfil pessoal, mantendo a navegação e a reprodução no mesmo contexto. Até duas sessões, fechamento explícito pelo painel ou pela janela. Cookies não são enviados ao frontend.
- A janela de sessão abre novamente a página de origem e cria sua própria sessão. Não transfere cookies da inspeção automática. A reprodução é feita no player do site nessa janela, não foi implementada uma ponte de streaming para o player customizado do Jarvis.

Validação: 28 testes Python existentes e oito novos testes passaram. Os novos testes usam Chromium real e vídeo sintético: carregamento tardio, controle conhecido, recusa de clicar em botão arbitrário, bloqueio, fragmentos, cookie de sessão, liberação ao fechar e rotas. Nove testes de interface existentes e dois novos passaram; os dois novos foram repetidos após corrigir a preparação da consulta no teste. Build TypeScript/Vite concluído, com avisos de tamanho de bundle e importação já existentes.

Consulta real repetida em `animesonlinecc.to/episodio/naruto-shippuden-episodio-1/`: dois players incorporados, zero fontes diretas, 186 links classificados como episódios, estado `unconfirmed`. Esses links não foram todos reproduzidos nem confirmados como pertencentes à mesma série. Evidência resumida: `scratch/seekee-reference/live-session-probe-summary.json`.

Permanecem pendentes para equivalência ao Seekee: adaptadores específicos das fontes, classificação da busca por reprodução real, associação robusta dos episódios ao título e integração de streams dependentes de sessão ao player customizado. A disponibilidade em sites reais não está garantida. O processo principal do Jarvis não foi reiniciado automaticamente; é necessário reabrir o aplicativo para carregar o backend atualizado.

## Atualização de implementação e validação

O item de integração de sessão ao player customizado foi concluído após a primeira etapa descrita acima:

- A sessão de site agora observa requisições de mídia iniciadas pela navegação normal do usuário e entrega ao player do Jarvis uma URL local opaca. O endereço de mídia, cookies, `Referer`, `Origin` e `User-Agent` ficam no backend.
- O relay preserva `Range` para MP4, reescreve listas HLS e referências de variantes/áudio/chaves para URLs locais opacas, expira por inatividade e deixa de funcionar ao fechar a sessão. Salvar uma mídia guarda a página de origem, não uma URL temporária do relay.
- A varredura automática cria um relay curto, separado e com expiração, para verificar a mídia detectada mesmo depois de encerrar o navegador de inspeção. O filtro de compatibilidade mantém somente resultados confirmados nessa página de pesquisa.
- Testes com Chromium real e um servidor local verificaram MP4 e HLS que exigem cookie de origem, reprodução em um navegador consumidor sem esse cookie, encaminhamento de `Range`, redirecionamento sem cabeçalhos sensíveis, expiração e autorização da rota do relay. Não há bypass de DRM, login, paywall ou desafios do site.
- A leitura da página real de Naruto Shippuden passou a identificar os 500 links do índice da própria série, sem confundir links de comentários com episódios. Na observação de 2026-11-11, os iframes dessa página exibiam “Video is unavailable”; portanto não houve mídia direta real confirmada para reproduzir. Esse estado agora é apresentado como indisponível, e não como uma falha genérica do detector.
- A busca web também passou a exigir correspondência suficiente com o título pesquisado e tenta um segundo provedor antes do fallback. Isso elimina resultados evidentemente não relacionados, como páginas sobre a letra “O” na busca por “O Exterminador do Futuro”.

Validação final desta atualização: 45 testes Python direcionados e 12 testes Playwright de interface passaram; o build TypeScript/Vite de produção concluiu. Restam os avisos conhecidos de chunks grandes do frontend.

## Player próprio, sem páginas incorporadas

O player do Jarvis não usa mais uma página externa como fallback dentro de um `iframe`. Ele só aceita URLs de mídia direta MP4/HLS e URLs opacas do relay da sessão. Uma URL de página exige primeiro a detecção de mídia ou uma sessão isolada; a página não é clicável dentro do player e, por isso, não pode redirecionar o clique para anúncios. Essa separação não remove anúncios nem extrai conteúdo de páginas de terceiros: ela impede que uma página seja confundida com mídia.

## APK recebido como “Web Video Cast”

O arquivo `D:/Downloads/uptodown-com.instantbits.cast.webvideo.apk` foi conferido antes de ser usado como referência. Seu manifesto declara pacote `com.uptodown`, aplicação `com.uptodown.UptodownApp`, nome “Uptodown App Store” e versão 7.44; portanto não corresponde ao Web Video Cast apesar do nome do arquivo. A análise foi interrompida e nenhum código ou comportamento desse APK foi incorporado ao Jarvis. SHA-256: `8f8a7b2416d84d64d418dc4e194cd8ab6f4394d51651bf2e1aac47207503fd92`.

## Referência Web Video Caster recebida depois

O APK `D:/Downloads/Web Video Caster_Premium - v6.1.0_Tekmods.com.apk` declara o pacote esperado `com.instantbits.cast.webvideo`, versão 6.1.0. A cópia é modificada: contém uma classe duplicada também dentro de `assets/OK.apk`. Essa parte e qualquer mecanismo de licença foram excluídos da análise. SHA-256: `78d1fadd37112c53f096cd4367114328824605ee1875157212eaa10869b2dbce`.

O JADX conseguiu gerar 16.113 fontes antes de encerrar com 36 erros em classes obfuscadas; a execução completa atingiu o teto de memória de 10 GB. A saída disponível confirma conceitos gerais, sem copiar código: tipos separados para MP4, HLS/M3U8, WebM e DASH/MPD; um registro de URL de proxy com URL de origem, possível MIME type, cabeçalhos, isolamento/incógnito e data de atualização; e um servlet de proxy de mídia. Esses pontos validam o desenho já adotado no Jarvis: página externa isolada, mídia direta capturada separadamente e relay local que retém cookies/cabeçalhos no backend.

Como resultado prático adicional, candidatos com assinatura inequívoca de rede de anúncios (`adserver`, `doubleclick`, `googlesyndication`, `adsystem`, `advertising`, `preroll`, caminho `/ads/` ou VAST) passaram a ser rotulados e ficam fora da reprodução automática. Essa regra não remove anúncios de terceiros nem tenta contornar proteção; apenas evita selecionar uma mídia que já se apresenta como anúncio.
