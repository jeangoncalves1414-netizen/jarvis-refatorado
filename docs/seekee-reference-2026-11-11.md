# Referência Seekee e cinema desktop — 2026-11-11

## Evidência

XAPK fornecido: `D:/Downloads/seekee.apk.2.14.0.xapk`, pacote `com.enzo.paulo`, versão 2.14.0 (222). SHA256: `e90601e8cc4697c29386fc2bc7de684559d0535fe0363b5cfa87813404f1eb55`.

Análise estática parcial com JADX 1.5.6: 8066 classes processadas e três erros. Proteção Ijiami e bundle Hermes impedem afirmar recuperação completa da lógica. Os recursos expõem categorias em português, metadados de recomendações e scripts de comunicação de vídeos/iframes com a camada nativa. Nenhuma API privada ou recurso visual do APK foi copiado para o desktop.

Inspeção autorizada por ADB no moto e20: player aberto em “Português Dublado — O Mentalista Temporada 4 (1)”. Captura confirma controles de qualidade (540P), velocidade (1.0), áudio, legendas desabilitadas nesse estado, episódios, próximo episódio, brilho, volume e saltos de dez segundos. Menu de episódios aberto e confirmado visualmente: botões 1–24, episódio 1 destacado. Não há seletor de temporadas nessa captura. Os controles somem por inatividade; capturas ADB funcionaram após reconexão. Evidências locais em `scratch/seekee-reference/phone-retry.png` e `phone-episode-menu.png`.

## Implementação

- Catálogo com preferência por português; fallback sinaliza idioma original.
- Abas de filmes, séries, animes e sites, seleção de fonte/domínio e exclusão de Netflix/Amazon na descoberta.
- Interface de cinema e player ampliada, histórico local e paginação.
- Filtro da página atual com três tarefas concorrentes, cache e cancelamento. Compatibilidade exige carregamento real de vídeo; iframe isolado não conta como confirmação.
- Leitura de mídia, episódios e temporadas expostos em HTML/JSON-LD, com inspeção dinâmica limitada. Player HLS oferece resoluções e faixas de áudio quando presentes no manifesto.
- Seleção de episódio e avanço ao próximo preservam a lista detectada.

## Validação e limites

Compilação TypeScript/Vite concluída. Nove testes Playwright passaram, incluindo vídeo MP4 real de teste, HLS com áudio/qualidade, cancelamento, concorrência, episódios e largura responsiva. Na validação anterior, 28 testes Python passaram.

Consulta real de Exterminador do Futuro retornou oito títulos em português. Busca nativa de animes retornou títulos de Naruto; uma página de episódio expôs players Blogger, sem stream direto confirmado. Flixlat apresentou bloqueio Cloudflare. Portanto, a implementação não comprova reprodução em todos os sites citados, nem equivalência à extração do Seekee. Resoluções, dublagens e episódios dependem do que cada fonte expõe. Não há contorno de DRM, autenticação ou desafios de acesso.

O backend em execução não foi reiniciado nesta validação; reiniciar o Jarvis é necessário para carregar as alterações Python. Alterações preexistentes no repositório foram preservadas.
