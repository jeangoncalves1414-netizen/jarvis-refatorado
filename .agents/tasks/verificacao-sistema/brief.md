# Verificação de funcionamento e fluidez do sistema (7/11/2026)

## Objetivo
Responder com evidência de EXECUÇÃO, e não só de leitura de código, se o app está funcional e fluido do jeito que a usuária vai usá-lo. A verificação deve mostrar onde quebra, onde trava, o que acontece na primeira vez que ela abrir o app com os dados reais e quais alterações valem a pena antes do lote 3.

**NÃO implementar correções.** Só verificar, medir e sugerir. Sem commit, sem push e sem alterar arquivos rastreados do checkout principal. Relatórios em português (pt-BR), diretos e sem jargão.

## Contexto
- Repositório `c:\Users\maria\Desktop\Jarvis`, branch `main`, HEAD `21d9e12`. Os lotes 1 e 2 vão de `fe25fd8` a `21d9e12`, sobre o checkpoint `da00309`.
- Leia primeiro as seções 1 a 6 e 13 de `c:\Users\maria\Desktop\Jarvis\docs\CONTEXTO_PARA_CHATGPT.md`. Elas trazem projeto, decisões, arquitetura, entregas, o que nunca foi verificado e o backlog.
- Relatório do último lote, com os pontos sensíveis: `c:\Users\maria\Desktop\Jarvis\.agents\tasks\desktop-lote2\report.md`.
- Inventário de recursos com arquivo e linha: `c:\Users\maria\Desktop\Jarvis\.agents\tasks\desktop-feature-parity\report.md`.
- **Como a usuária abre o app:** `python -m app.main`. Isso abre uma janela pywebview/WebView2 em `http://127.0.0.1:8000/app/`, que serve `frontend/dist`, e liga a bandeja, os atalhos globais, o detector de palavra de ativação e o agente proativo. Em desenvolvimento: `python -m app.main --server` mais Vite.
- **O que ela espera do produto:**
  - Painel no nível do ChatGPT/Claude, organizado e sem poluição visual.
  - Módulos como janelas flutuantes abertas sob demanda.
  - Menu `/` e paleta Ctrl+K funcionando sem IA.
  - Registro manual sem IA, com rascunho protegido.
  - Toda ação passando pelo Action Kernel, com risco, aprovação, histórico na Central de Execuções e cancelamento.
  - Sincronização total com o Supabase dela, inclusive das chaves.

## Regras de segurança (valem para todas as etapas)
1. **Nunca escreva, migre ou "conserte" nada** em `c:\Users\maria\Desktop\Jarvis\data` nem em arquivos rastreados do checkout principal. Ler e copiar é permitido. Exceção: a etapa de síntese edita `docs\CONTEXTO_PARA_CHATGPT.md`, que não é rastreado.
2. **Rode tudo em cópias isoladas.** Use worktrees destacados, criados com `git worktree add --detach <caminho> HEAD` dentro de `c:\Users\maria\Desktop\Jarvis\.worktrees\`. Se der erro de lock do git, tente de novo uma vez.
   - Antes de iniciar qualquer processo, leia `app/config.py` e os módulos de armazenamento. Confirme que dados, logs, locks, cofre, memória vetorial, configurações e tokens apontam todos para dentro do worktree.
   - Se algum caminho apontar para fora (`%APPDATA%`, a home da usuária, ou um caminho absoluto para `Desktop\Jarvis\data`), redirecione por variável de ambiente ou configuração suportada. Outra opção é um script de partida descartável que faz monkeypatch antes de iniciar.
   - Se nada disso funcionar, não inicie o processo e registre o motivo.
3. **Nenhuma chamada a serviços reais com credenciais da usuária:** nada de provedores reais de IA ou de voz, nada do Supabase real, nada de outros serviços na nuvem.
   - Confira, só pelos nomes, se há variáveis de ambiente do sistema com chaves de provedor. Se houver, tire-as do ambiente dos processos filhos.
   - No Playwright, bloqueie todas as requisições que não sejam para localhost, inclusive `*.supabase.co`. Registre quais domínios o app tenta acessar e se ele lida bem com a falha.
   - Exceção: o TTS do Edge, que é gratuito e sem credencial, pode ser chamado uma vez com uma frase curta, se for o provedor padrão sem chave.
4. **Nenhum efeito real no Windows.** Não altere volume nem brilho, não bloqueie a tela, não abra nem feche apps, não rode scripts e não use o agente de navegador. Leitura sem efeito é permitida. Exemplo: `Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness`, para saber se o brilho é controlável neste PC.
5. **Microfone desligado.** Palavra de ativação, palmas e STT não podem escutar durante a verificação. Se o servidor iniciar o detector sozinho, desligue por configuração no worktree ou por monkeypatch no script de partida. Confirme que o microfone não foi aberto. No Playwright, negue a permissão de microfone.
6. **Nunca imprima valores de segredos** (`.env`, configurações, tokens) nem conteúdo de dados pessoais (lançamentos, memórias, notas, histórico). Reporte só nomes, contagens, tipos e se passou ou falhou. Não abra nem cite `c:\Users\maria\Desktop\Jarvis\test_fish_audio.py`.
7. Não rode `npm run build:mobile`. Não faça `git push`. Não faça commit.
8. **Encerre todos os processos que iniciar** (servidor, provedor simulado, Vite, navegador) antes de terminar, e registre os PIDs. Se a porta 8000 estiver em uso, evite-a: a usuária pode estar com o app aberto. Use portas livres e confira com `Get-NetTCPConnection`.
9. **Ferramentas.**
   - Crie e edite arquivos (scripts descartáveis, relatórios) só com `fs_write`, `str_replace` e `fs_append`, nunca com PowerShell. Leia com `read_file`, `read_code` e `grep_search`.
   - Use o shell só para comandos curtos e simples: `git`, `python`, `node`, `npx`, `Copy-Item`, `robocopy`, `Get-NetTCPConnection`, `Get-CimInstance`. Um comando por chamada, sem blocos de script. A usuária precisa aprovar à mão o que o Kiro não consegue interpretar.
   - Scripts descartáveis ficam dentro do worktree da etapa ou em `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\scratch\`. Cópias de dados reais ficam só dentro do worktree.
10. **Economia de tokens.** Use leituras parciais e greps. Não leia arquivos grandes inteiros. Ignore `node_modules`, `dist`, `.git`, `__pycache__` e os assets de `mobile_app`.
11. **Ambiente.**
    - Windows/PowerShell.
    - git: `E:\PortableGit-2.54.0-64\cmd\git.exe`, já no PATH.
    - Python: `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe`.
    - Playwright: variável `PLAYWRIGHT_MODULE=C:\Users\maria\AppData\Local\Programs\Python\Python311\Lib\site-packages\playwright\driver\package`. Veja como `frontend\tests\workspace.smoke.cjs` carrega o Playwright.
    - Comandos com `Get-Date` são bloqueados. Use `[datetime]::Now`.

## Formato dos relatórios das frentes
Use estas seções, com no máximo cerca de 350 linhas:
1. Resumo em 5 linhas.
2. O que foi feito.
3. Resultados (tabelas).
4. Falhas, cada uma com: ID, gravidade (crítica, alta, média ou baixa), passos para reproduzir, evidência, causa provável (arquivo:linha) e sugestão.
5. Números de fluidez (só na frente A).
6. O que não foi possível verificar e por quê.
7. Processos encerrados e onde estão os worktrees.

---

## Frente A: o app rodando de verdade (funcional e fluido)
- Worktree: `c:\Users\maria\Desktop\Jarvis\.worktrees\verify-runtime`.
- Copie `c:\Users\maria\Desktop\Jarvis\frontend\dist` para o `frontend\dist` do worktree. O dist do checkout principal já foi gerado a partir do código atual.
- **Não copie** `.env` nem `data/`. Esta frente simula o primeiro uso, sem dados e sem chaves.

1. **Partida.**
   - Inicie o backend do worktree em modo servidor, com o diretório atual no worktree e as regras 2, 3 e 5 garantidas.
   - Meça o tempo até a rota de saúde ou `/app/` responder.
   - Meça memória RSS e CPU em repouso por 60 segundos.
   - Registre erros e avisos do log de partida.
2. **Provedor simulado.**
   - Veja se o backend aceita um provedor compatível com OpenAI ou Ollama com URL configurável. Se aceitar, suba um servidor HTTP local descartável com roteiros fixos:
     - resposta de texto simples;
     - chamada da ferramenta `open_window` para Finanças;
     - chamada de criar tarefa;
     - chamada de limpar o quadro, que exige aprovação e só afeta a conversa;
     - resposta em streaming, se o chat usar SSE.
   - Configure o backend do worktree para usar esse servidor. Assim o caminho real (chat → orquestrador → Action Kernel → aprovação → Central) é testado sem custo.
   - Se não for viável em tempo razoável, registre por quê e verifique só o comportamento sem provedor.
3. **Jornadas no navegador.**
   - Use Playwright contra o backend real do worktree, SEM APIs simuladas, em 1536x960 e 360x844.
   - Salve capturas em `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\screenshots\`.
   - Jornadas:
     - **Primeira impressão sem provedor:** o que aparece, se fica claro como configurar um provedor e se o chat mostra um erro claro ou trava.
     - **Configurações:** salvar o perfil do agente e configurar o provedor simulado.
     - **Chat com o provedor simulado:**
       - resposta simples, medindo a latência do caminho até o primeiro token e até o fim;
       - "Ver execução" abrindo a Central;
       - `open_window` abrindo Finanças;
       - tarefa criada aparecendo no Painel pessoal;
       - proposta de limpar o quadro, aprovada e também recusada, na Central;
       - pedido cancelado;
       - modo Execução por etapas.
     - **Menu `/` e paleta Ctrl+K:** abrir `/gastos` e `/controles` sem IA, e testar um comando desconhecido.
     - **Finanças com a API real do worktree:** adicionar, editar, filtrar, conferir os totais e excluir. Conferir que o rascunho continua depois de recarregar a página.
     - **Controles do PC:** abrir a janela e ler o estado, sem aplicar nada. Conferir o que aparece na Central.
     - **Conversa por voz:** com o microfone negado, a janela deve mostrar um erro claro.
     - **Navegação completa:** passar por todas as áreas da barra lateral e pelos módulos antigos ainda acessíveis (Painel pessoal, Life OS `/evolute/`, Estudos, Memórias, Automações, Integrações, Calendário, Métricas). Procurar botões mortos, telas quebradas, visual inconsistente com o painel novo, erros no console e requisições falhando.
4. **Fluidez, em números.**
   - Carregamento inicial: DOMContentLoaded, load e LCP.
   - JS transferido e os maiores chunks. Há aviso de chunks de diagramas maiores que 800 kB: diga se eles carregam na partida.
   - Latência para abrir cada janela.
   - Tarefas longas (mais de 50 ms) durante as interações.
   - Requisições por minuto com o app parado (polling).
   - Crescimento de memória da página em 5 minutos parada.
   - Latência p50 e p95 das rotas usadas.
5. **Desktop.**
   - Confira por leitura e por requisição que `/app/` serve o dist com os caminhos de assets corretos (a base do Vite).
   - Descreva o que o modo desktop liga a mais que o `--server`: pywebview, bandeja, atalhos, ProactiveDaemon e detector.
   - Não abra a janela pywebview na área de trabalho da usuária.
6. **Leitura sem efeito:** o brilho é controlável neste PC (WMI)?

**Relatório:** `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\frente-a-runtime.md`.

---

## Frente B: dados reais, testes e lógica (offline)
Worktree: `c:\Users\maria\Desktop\Jarvis\.worktrees\verify-dados`.

1. **Suíte completa, primeiro, com o worktree ainda limpo.** Lá é seguro: os testes que escrevem em `data/` escrevem no worktree.
   - Rode `python -B -m pytest -q -p no:cacheprovider --tb=short tests`.
   - Exclua, pelos marcadores de `pyproject.toml` ou por `--ignore`, as suítes de hardware, rede ou servidor ao vivo, como `smoke_test.py`, `stress_test.py` e `test_live_server.py`. Confira antes o que cada uma faz.
   - Classifique cada falha: defeito real, ambiente (dependência ausente, rede, hardware) ou instável.
   - Rode também:
     - `python -m compileall -q app`;
     - a importação do app inteiro, `python -c "import app.main"`, com o diretório atual no worktree;
     - `python -m pip check`.
   - Liste as ferramentas registradas no catálogo cujas dependências não estão instaladas, como kasa e composio. O modelo pode chamá-las e falhar.
2. **Primeiro uso com os dados reais, em simulação offline sobre CÓPIAS.**
   - Liste os nomes e tamanhos dos arquivos de `c:\Users\maria\Desktop\Jarvis\data`. Depois, copie a pasta para o `data/` do worktree.
   - Copie `.env` só se o caminho testado ler esse arquivo. Se `data/` passar de 2 GB, copie só o que os testes precisam: journal, configurações, `lifestyle.db`, cofre, tarefas, metas e memórias.
   - Escreva um script Python descartável que bloqueia a rede, como faz `tests/conftest.py`, e rode-o com o diretório atual no worktree. Ele deve exercitar o que a primeira abertura do app novo faz com esses dados:
     - migração do journal (`data/action_journal.jsonl` para SQLite) e recuperação;
     - carregar as runtime settings no formato novo, com perfil padrão e carimbos por campo;
     - `collect_snapshot` da sincronização, reportando só contagens por seção;
     - consultas e normalização de finanças sobre o `lifestyle.db` real;
     - carregar memórias, cofre de notas, tarefas e metas.
   - Diga se algo quebra com o formato real (schema antigo, campos ausentes, encoding) e o que mudaria nos dados.
3. **A primeira sincronização real.**
   - Descubra por leitura quando a sincronização roda (na abertura, manual ou periódica), em qual lado (`frontend/src/utils/jarvisCloud.ts`, `app/storage/backend_sync.py` ou os dois) e o que acontece quando o snapshot remoto ainda está no formato antigo, do APK antigo ou da versão anterior do app.
   - Simule offline estes cenários:
     - snapshot local novo com remoto no formato antigo (`fieldsFromLegacyVault`);
     - dois dispositivos com provedores diferentes;
     - campo vazio contra campo preenchido;
     - conflito no mesmo campo;
     - item apagado, que deve voltar: confirme e meça;
     - hábitos editados nos dois lados;
     - cofre com mais de 500 notas ou com nota maior que 512 KB: o que acontece com o excedente?
     - valores inválidos.
   - Para o lado TypeScript, `frontend/src/utils/syncMerge.ts` é puro. Rode os cenários com node se der para fazer sem instalar nada, por exemplo transpilando com o esbuild ou o typescript de `frontend/node_modules`. Se não der, analise por leitura e diga isso.
4. **Concorrência e robustez.** Casos: dois clientes do painel abertos, a mesma proposta aprovada duas vezes, cancelamento durante a execução. Confira se os testes existentes já cobrem esses casos e escreva cenário novo só para o que não estiver coberto.

**Relatório:** `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\frente-b-dados.md`. Inclua contagens, falhas classificadas, o que acontece na primeira abertura real, riscos de perda de dados com probabilidade e impacto, e o que não foi possível verificar. Nunca inclua valores de dados pessoais nem segredos.

---

## Síntese antiga (SUBSTITUÍDA pela seção "Síntese final" no fim deste arquivo; não executar)
Leia os dois relatórios das frentes. Consulte código só para confirmar algum ponto. Escreva `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\report.md` em português, direto e sem jargão, para a usuária decidir:

1. **Veredito curto.** O sistema está funcional? Está fluido? Uma frase para cada, com a principal razão.
2. **Tabela por área:** chat e agente, Central e aprovações, janelas e Finanças, Controles do PC, comandos e paleta, configurações e perfil, sincronização, voz, abertura do desktop e celular. Para cada uma: Funciona, Funciona com ressalvas, Quebrado ou Não verificado, com a evidência.
3. **Problemas encontrados,** do mais grave ao menos grave. Para cada um: o que acontece, como reproduzir, causa provável (arquivo:linha), correção sugerida e tamanho (P, M ou G).
4. **Fluidez:** tabela com os números medidos, os gargalos e sugestões concretas.
5. **Primeira abertura com os dados reais:** o que vai acontecer, os riscos e um passo a passo seguro (backup de `data/` e `.env`, ordem, o que observar e como voltar atrás).
6. **Sugestões de alterações** de produto, interface e arquitetura, em ordem de valor e esforço. Ligue cada uma aos IDs do backlog da seção 13 de `docs/CONTEXTO_PARA_CHATGPT.md`. Itens novos recebem IDs novos com o prefixo VF.
7. **Checklist curto** do que só a usuária pode testar: hardware, provedor real, Supabase real e APK.
8. **Ajuste recomendado para o lote 3.**

Depois, atualize `c:\Users\maria\Desktop\Jarvis\docs\CONTEXTO_PARA_CHATGPT.md` com `str_replace` ou `fs_append`, sem commit:
- No final, uma seção "14. Verificação de funcionamento (7/11/2026)" com o veredito, a tabela por área resumida, os 5 problemas mais importantes e o link para o relatório.
- Na seção 13, uma tabela "VF. Achados da verificação" com os itens VF novos.

Por fim, faça a limpeza:
1. Com o diretório atual no checkout principal, remova os dois worktrees de verificação com `git worktree remove --force` para cada um.
2. Confirme com `git worktree list` que só restaram o principal e o do Codex (`C:/Users/maria/.codex/worktrees/f886/Jarvis`), que não deve ser tocado.
3. Confirme que nenhuma cópia de dados reais ficou em disco.

---

## Frente C: como os sistemas se conectam, fluxos, autonomia e eficiência
**Pergunta da usuária, nas palavras dela:** "analisar como os sistemas se conectam, se o uso para o que eu quero está adequado, fluxo adequado, se a IA é autônoma e tem muito controle (...) pra deixar um sistema eficiente, funcional."

**Esta é a frente principal para ela.**
- Ela roda depois das frentes A e B. Leia primeiro os relatórios delas (`frente-a-runtime.md` e `frente-b-dados.md`), para não repetir trabalho e para usar as evidências de execução.
- O trabalho é sobretudo análise de código, citando arquivo e linha.
- Medições pequenas só em processo, num worktree destacado próprio (`c:\Users\maria\Desktop\Jarvis\.worktrees\verify-arquitetura`), com a rede bloqueada e sem dados reais.
- Todas as regras de segurança acima valem.

1. **Mapa real das conexões.** Trace no código como cada parte fala com as outras:
   - interface: chat, janelas, menu `/`, paleta, configurações e Central;
   - transportes: REST, WebSocket legado e streaming HTTP/SSE;
   - orquestrador e seus modos: normal, Execução por etapas (ReAct), Swarm, Racing, tutor e outros;
   - roteamento de modelos e fallback;
   - catálogo e registro de ferramentas;
   - Action Kernel: risco, aprovação, recibos e Runs;
   - adaptadores: sistema, apps, arquivos, scripts, navegador, integrações e dispositivos;
   - armazenamento: journal, runs, tarefas, metas, memória vetorial, cofre, `lifestyle.db` e runtime settings;
   - sincronização: `jarvisCloud.ts`, `backend_sync.py` e Supabase;
   - voz: STT, TTS, palavra de ativação, ligação e pipeline realtime;
   - proatividade: ProactiveDaemon, agendador, metas e monitor ambiente;
   - celular: chat direto e modo conectado.

   **Entregue:**
   - Um diagrama mermaid fiel ao código, não ao ideal.
   - Uma tabela de conexões com as colunas: origem, destino, transporte, passa pelo Action Kernel? e aparece na Central?

   **Marque:**
   - Caminhos duplicados, por exemplo: dois caminhos de tarefas, o registro de janelas em Python e em TS, três transportes de chat.
   - Caminhos que contornam o Action Kernel, como a voz e as rotas diretas.
   - Peças sem uso ou sem ligação.
   - Pontos únicos de falha.
2. **Adequação ao que ela quer.**
   - Considere cada objetivo das seções 2 e 3 de `docs\CONTEXTO_PARA_CHATGPT.md`:
     - agente com muito controle do PC e das áreas da vida;
     - persona trocável;
     - janelas sob demanda;
     - registro sem IA;
     - desktop e celular como um só produto;
     - tudo sincronizado;
     - voz;
     - rotinas e gatilhos, como palmas e horário.
   - Diga se a arquitetura atual suporta bem, mal ou não suporta cada um, e por quê (arquivo:linha).
   - Diga o que mudaria na estrutura, e não só "falta o recurso X".
3. **Fluxos de ponta a ponta.**
   - Para cada fluxo, trace com arquivo:linha e conte os saltos, as chamadas ao modelo e os pontos de aprovação.
   - Aponte os atritos: erro engolido, aprovação demais ou de menos, a usuária sem ver o que acontece, latência desnecessária.
   - Fluxos:
     - a) "abre minhas finanças" pelo chat;
     - b) `/gastos` sem IA;
     - c) "anota que gastei 50 reais no mercado": o agente consegue registrar? Passa pelo Action Kernel? Aparece na Central?
     - d) "fecha o Spotify": proposta, aprovação, execução e resultado;
     - e) um pedido por voz, durante a ligação, que aciona uma ferramenta;
     - f) "lembra que eu prefiro X" e o uso dessa memória numa conversa futura;
     - g) tarefa de várias etapas no modo por etapas: "pesquisa X e cria uma nota com o resumo";
     - h) sugestão proativa a partir de uma meta;
     - i) uma rotina agendada: ainda não existe; diga o que seria preciso e onde encaixa;
     - j) a usuária pedindo algo pelo celular: qual caminho segue e o que funciona sem o PC.
4. **Autonomia e controle.**
   - Faça o inventário das capacidades que o agente realmente tem. Para cada ferramenta: o que controla, risco e aprovação, se funciona (dependências instaladas; use a frente B), se está exposta ao modelo e em quais modos.
   - Responda:
     - o que a IA faz sozinha, sem perguntar;
     - o que sempre pergunta;
     - até quantas etapas segue sozinha e o que a interrompe;
     - se consegue trabalhar em segundo plano enquanto a usuária conversa;
     - se age por conta própria (proatividade, rotinas);
     - se aprende e se corrige (memória, reflexion, healer);
     - o que ela sabe a cada turno (contexto factual, perfil, estado do PC).
   - Classifique o nível atual de autonomia nesta escala:

     | Nível | Significado |
     |---|---|
     | 0 | Só conversa |
     | 1 | Uma ferramenta por vez |
     | 2 | Várias etapas, com aprovação |
     | 3 | Rotinas e gatilhos confiáveis |
     | 4 | Proatividade com consentimento |
     | 5 | Cria e melhora as próprias ferramentas, com aprovação |

   - Diga o que falta, em ordem, para subir de nível sem tirar o controle da dona.
   - Avalie esta hipótese: ter muita autonomia sem pedir aprovação o tempo todo exige permissões duradouras por escopo e rotinas de confiança (item C2 do backlog). Diga se isso procede no código atual.
5. **Eficiência.** Meça em processo, no worktree próprio e com a rede bloqueada:
   - o tamanho do prompt de sistema e das definições de ferramentas enviadas por turno em cada modo, em caracteres e em tokens estimados;
   - quantas ferramentas vão ao modelo em cada modo;
   - quantas chamadas ao modelo um turno típico faz, incluindo título automático, memória, reflexion, resumo e roteadores;
   - o que roda em segundo plano gastando modelo, como o resumo de hora em hora e o daemon proativo;
   - o custo de partida: quantos serviços sobem de cara e quais imports são pesados.

   Diga onde há desperdício e como reduzir. Exemplos: ferramentas por modo ou por intenção, contexto sob demanda, modelo barato para tarefas simples, cache.
6. **Recomendações de arquitetura,** em ordem de valor e esforço.
   - Para cada uma: o problema que resolve, a mudança proposta, os arquivos envolvidos, o tamanho (P, M ou G) e o ID do backlog da seção 13 do CONTEXTO, ou um ID novo com prefixo AQ.
   - Inclua uma arquitetura-alvo enxuta, em diagrama mermaid.
   - Inclua um caminho de migração em etapas pequenas, que não quebrem o que já funciona.

**Relatório:** `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\frente-c-arquitetura.md`, com até cerca de 500 linhas. Siga o mesmo formato geral das outras frentes, incluindo os diagramas.

---

## Síntese final (substitui a seção "Síntese" anterior)
Leia os três relatórios: `frente-a-runtime.md`, `frente-b-dados.md` e `frente-c-arquitetura.md`. Se algum faltar, diga isso e use o que existe.

Escreva `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\report.md` em português simples, organizado pelas perguntas DELA:

1. **Veredito.** Quatro frases, cada uma com a razão principal:
   - Os sistemas estão bem conectados?
   - O app serve para o que ela quer?
   - Os fluxos estão bons?
   - A IA é autônoma e tem muito controle?

   Depois, uma frase sobre se é funcional e fluido.
2. **Como tudo se conecta.** O diagrama mermaid do sistema real, vindo da frente C, explicado em poucas linhas. Aponte os principais desvios: caminhos duplicados, contornos do Action Kernel e peças soltas.
3. **Adequação ao uso.** Tabela com o objetivo, se é suportado (bem, com ressalvas ou não) e o que muda.
4. **Fluxos.** Tabela dos fluxos de a) a j), com nota (bom, com atrito, quebrado ou inexistente) e o atrito principal.
5. **Autonomia e controle.** O nível atual na escala, o que a IA faz sozinha e o que pergunta, e o caminho para subir de nível.
6. **Funciona e é fluido?** Tabela por área (chat e agente, Central e aprovações, janelas e Finanças, Controles do PC, comandos e paleta, configurações e perfil, sincronização, voz, abertura do desktop e celular). Para cada uma: Funciona, Com ressalvas, Quebrado ou Não verificado. Inclua os números de fluidez.
7. **Problemas encontrados,** do mais grave ao menos grave. Para cada um: o que acontece, como reproduzir, causa provável (arquivo:linha), correção e tamanho.
8. **Primeira abertura com os dados reais.** O que vai acontecer, os riscos e um passo a passo seguro: backup, ordem, o que observar e como voltar atrás.
9. **Plano recomendado.**
   - A arquitetura-alvo resumida.
   - As mudanças em ordem de valor e esforço, ligadas aos IDs da seção 13. Itens novos usam VF para achados de execução e AQ para arquitetura.
   - Como fica o lote 3.
10. **Checklist curto** do que só ela pode testar.

Depois, atualize `docs\CONTEXTO_PARA_CHATGPT.md` com `str_replace` ou `fs_append`, sem commit:
- No final, uma seção "14. Verificação e análise de arquitetura (7/11/2026)" com:
  - o veredito;
  - o diagrama do sistema real;
  - a tabela por área, resumida;
  - o nível de autonomia;
  - os 5 problemas mais importantes;
  - o link para o relatório.
- Na seção 13, as tabelas "VF. Achados da verificação" e "AQ. Arquitetura".

Por fim, faça a limpeza:
1. Com o diretório atual no checkout principal, remova os três worktrees de verificação (`verify-runtime`, `verify-dados` e `verify-arquitetura`) com `git worktree remove --force`.
2. Confirme com `git worktree list`. O worktree do Codex (`C:/Users/maria/.codex/worktrees/f886/Jarvis`) não deve ser tocado.
3. Confirme que nenhuma cópia de dados reais ficou em disco.
