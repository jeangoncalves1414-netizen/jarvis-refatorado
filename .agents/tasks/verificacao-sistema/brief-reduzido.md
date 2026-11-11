# Verificação reduzida (retomada em Sonnet, créditos limitados)

Esta é uma versão menor do plano de `brief.md`. As frentes A e B originais foram interrompidas porque os créditos da usuária estão quase no fim. O objetivo continua sendo responder às perguntas DELA: como os sistemas se conectam, se o app serve para o que ela quer, se os fluxos são bons, se a IA é autônoma e tem controle, e se o primeiro uso com os dados reais é seguro.

**Leia `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\brief.md`** para as regras de segurança, o ambiente e o contexto (todas valem integralmente), e a seção "Frente C" para o roteiro da análise. **Ignore** as seções "Frente A", "Frente B" e as sínteses de lá: o escopo agora é o que está neste arquivo.

## O que já existe do trabalho interrompido
- Worktrees destacados em `c:\Users\maria\Desktop\Jarvis\.worktrees\verify-runtime` (frontend/dist copiado, sem dados) e `c:\Users\maria\Desktop\Jarvis\.worktrees\verify-dados` (pode conter uma cópia de dados reais; veja o que há lá antes de usar, nunca mostre conteúdo). Reutilize-os. Se faltar algo, recrie com `git worktree add --detach`.
- Capturas parciais da frente A em `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\screenshots\` (a01 a a07: primeira impressão sem provedor, chat, configurações, provedor simulado, resposta simples e "Ver execução"). Olhe-as com `read_file` e descreva o que mostram. Não repita essa jornada.
- Processos de teste (backend, Vite, navegador) podem ter ficado ativos. Antes de começar, procure por `python` e `node` cujo diretório ou linha de comando aponte para `.worktrees\verify-` e encerre só esses (confirme a linha de comando antes; nunca encerre o MCP do Blender, o Codex, nem nada da pasta da usuária que não seja de `.worktrees`). Confira portas livres com `Get-NetTCPConnection`.

## Escopo (nesta ordem, pare quando um item for inviável e registre o motivo)
1. **Higiene (curto).** Encerrar processos de teste órfãos (acima). Rodar a suíte pytest completa no worktree `verify-dados` limpo ou em `verify-runtime`: `python -B -m pytest -q -p no:cacheprovider --tb=short tests`, excluindo suítes de hardware, rede ou servidor ao vivo (`smoke_test.py`, `stress_test.py`, `test_live_server.py`). Classificar falhas (defeito real, ambiente ou instável). Rodar `python -m compileall -q app`, `python -c "import app.main"` e `python -m pip check`. Listar as ferramentas do catálogo cujas dependências não estão instaladas.
2. **Primeiro uso com os dados reais (simulação offline sobre CÓPIAS)**, conforme "Frente B, item 2" do `brief.md`: migração do journal, runtime settings no formato novo, `collect_snapshot` (só contagens), finanças sobre o `lifestyle.db` real, memórias, cofre, tarefas e metas. Diga se algo quebra com o formato real e o que mudaria nos dados. Nunca imprima conteúdo.
3. **Sincronização**, conforme "Frente B, item 3": cenários de formato antigo, dois dispositivos, vazio contra preenchido, conflito, item apagado voltando, limites de notas. Use `syncMerge.ts` com node se for possível sem instalar nada; senão, análise por leitura.
4. **Frente C completa** (roteiro no `brief.md`, seção "Frente C"): mapa real das conexões com diagrama mermaid e tabela, adequação ao uso, fluxos a) a j), autonomia e controle com nota na escala 0 a 5, eficiência (tamanho do prompt e das definições de ferramentas por modo, chamadas ao modelo por turno, trabalho em segundo plano), recomendações e arquitetura-alvo. **É o item mais importante: priorize a qualidade dele.** As medições em processo ficam no worktree `verify-runtime`, com a rede bloqueada e sem dados reais.
5. **Fora do escopo desta rodada:** medições de fluidez no navegador (carregamento, tarefas longas, polling, memória) e as demais jornadas de interface. Registre-as como "não verificado" com a observação de que ficam para depois.

## Entregáveis
- `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\frente-b-dados.md` (itens 1 a 3) e `frente-c-arquitetura.md` (item 4), com os formatos do `brief.md`.
- `c:\Users\maria\Desktop\Jarvis\.agents\tasks\verificacao-sistema\report.md`, organizado como na seção "Síntese final" do `brief.md`, mas marcando o que não foi medido (fluidez no navegador).
- Atualizar `c:\Users\maria\Desktop\Jarvis\docs\CONTEXTO_PARA_CHATGPT.md` (sem commit) com a seção 14 e as tabelas VF e AQ na seção 13, como na síntese final do `brief.md`.
- Limpeza: encerrar todos os processos iniciados; remover os worktrees de verificação com `git worktree remove --force` a partir do checkout principal; confirmar com `git worktree list` (o worktree do Codex `C:/Users/maria/.codex/worktrees/f886/Jarvis` não deve ser tocado); confirmar que nenhuma cópia de dados reais ficou em disco.

## Economia
A usuária tem poucos créditos. Seja objetivo: leituras parciais, greps e `read_code`, sem reler arquivos grandes inteiros; não repita análises que as capturas ou os relatórios já cobrem; relatórios enxutos. Não faça correções de código, commits nem push.
