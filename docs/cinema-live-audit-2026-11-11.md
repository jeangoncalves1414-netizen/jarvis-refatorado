# Auditoria automática de pesquisa e reprodução

Implementada em `scripts/cinema_live_audit.py`, com até três tarefas simultâneas. Usa a busca e a inspeção reais do Jarvis, depois verifica até duas fontes por página em Chromium, através do relay do próprio projeto. Não interage com o Jarvis já aberto nem com perfis pessoais.

Exemplo, na raiz do projeto:

```powershell
& C:/Users/maria/AppData/Local/Programs/Python/Python311/python.exe scripts/cinema_live_audit.py --query 'It: A Coisa 2017' --url 'https://cinevibehd.com/filmes/it-a-coisa-2017/' --limit 6 --workers 3 --output scratch/cinema-audit/it-2017.json
```

O relatório separa status e tempo de detecção, frames, elementos de vídeo, ações tentadas, respostas DASH, candidatos e teste de reprodução. Só marca `sample_played` quando há imagem decodificada e avanço de pelo menos 0,2 segundo. A tentativa de reprodução dura no máximo 6,5 segundos por candidato. Isso não confirma identidade do filme, duração completa, áudio correto ou ausência de publicidade.

Não salva cookies, cabeçalhos nem URLs de streams. Links de páginas ficam sem query/fragmento. O servidor local de validação tem porta temporária e só serve os relays dessa rodada; é encerrado ao terminar.

## Rodada real

Consulta: It: A Coisa 2017, seis páginas incluindo o exemplo enviado pelo usuário, três verificações concorrentes. Busca: 9,50 s; rodada: 31,12 s. Zero candidatos de mídia capturados; consequentemente nenhuma reprodução pôde ser tentada nesses seis casos.

- CineVibe: três ações, dois frames no primeiro teste, nenhum elemento de vídeo no final da janela.
- Redecanais e Boraflix: terminaram em página vazia/erro de navegação.
- Pobreflix: validação do endereço recusou a URL; a mensagem genérica não distingue falha DNS de endereço não público. Não é evidência de ausência de vídeo. A rotina de relatório foi ajustada depois para classificar `ok=false` como `rejected`.
- OK.ru e Vizer: nenhuma fonte confirmada dentro da janela de observação.

Repetição detalhada somente no CineVibe: 9,73 s, três frames, três ações, zero fontes. Uma requisição de documento para `cinevibehd.com.br` falhou com `net::ERR_FAILED`. Também houve falhas de scripts e requisições de terceiros, que não demonstram por si mesmas a causa do problema no player. Frames finais incluíram `streamtape.com` e um frame sem hostname. Evidência em `scratch/cinema-audit/cinevibe-detailed.json`.

## Validação controlada

Uma página com botão conhecido entrega um vídeo sintético pelo relay e a amostra é decodificada. Uma página cujo botão não é reconhecido termina sem candidatos e não é contada como sucesso. Esse teste impede confundir presença de URL, iframe ou metadata com reprodução real.

O próximo diagnóstico deve observar cada player alternativo por tempo suficiente, sem trocar de servidor enquanto ainda inicializa, e comparar o carregamento do mesmo player na sessão visível. Os resultados desta rodada não demonstram que os sites não têm vídeos nem que o detector já foi corrigido para eles.
