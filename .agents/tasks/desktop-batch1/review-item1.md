# Orbe fora dos gates de build e marca de alterações locais na versão do painel

Segunda passada do item 1. O commit `fc5f703` responde aos cinco achados da revisão de `fe25fd8`. Por decisão da usuária, a verificação da Orbe saiu também de `sync-mobile-assets.js`, então os três caminhos de APK ficaram iguais e o achado bloqueante sobre `build_mobile_jarvis.ps1 -RebuildWeb` deixou de existir. O teste de igualdade `dist`/assets saiu da execução padrão, a regra canônica foi marcada como obsoleta, os documentos deixaram de apontar para `postbuild.js` e a linha de versão ganhou `*` para árvore suja. Uma conferência pontual confirmou o `dist` regenerado: `index.html`, gravado às 19:13, aponta para `index-6QouVoUz.js`, que contém `commit:"fc5f703"`, e `git status` não mostra nada em `frontend/` nem em `mobile_app/`.

Watch for: nenhum script ou workflow chama `-m mobile_release`, então o teste de igualdade só roda se alguém rodá-lo à mão depois de `build:mobile` (confirmed, não bloqueante). Os quatro testes sobre o conteúdo de `JarvisOrb3D.tsx` continuam na suíte padrão, o que já está registrado em `conflicts.md`.

**Verdict**: APPROVED

## High-level view

`npm run build` virou só `tsc -b && vite build`, e `build:mobile` acrescenta a cópia do `dist` para os assets Android, sem verificar nada. A assimetria da primeira passada foi resolvida removendo a checagem da Orbe de todos os caminhos, em vez de adicioná-la ao terceiro, conforme a decisão registrada em `conflicts.md`. Os logs do script de cópia deixaram de dizer "JARVIS POST-BUILD", o que tira mais um resquício da persona.

A marca de árvore suja na linha de versão se limita a `frontend/`, porque o pacote só sai dali e a raiz sempre tem arquivos não rastreados, como `.agents/tasks/`. `git describe` ficou de fora porque as tags do repositório trocariam o hash por um nome de tag. Sem git, o hash e a marca somem e a config continua carregando.

O marcador `mobile_release` tira o teste de igualdade da execução padrão, no mesmo esquema de `integration` e `hardware`. A descrição do marcador manda rodá-lo ao gerar o APK, mas nenhum dos scripts de APK faz isso. A regra `.agents/rules/jarvis_visual_canonical.md` continua `always_on` porque a sincronização só por `build:mobile` ainda vale. O texto antigo ficou recolhido como histórico.

Nada que altere `mobile_app/` foi executado, então o APK e os assets Android ainda têm o pacote antigo, como `PENDENCIAS_DO_PAINEL.md` agora registra. O desktop pelo caminho normal (pywebview em `/app/`) também não foi aberto.

<details>
<summary>Issues (2)</summary>

1. **`mobile_release` sem chamador** (non-blocking, confirmed): o marcador manda rodar o teste ao gerar o APK, mas nenhum script de APK o executa. Citar `python -m pytest -m mobile_release tests/test_orb_canonical_integrity.py` no passo a passo do APK como conferência manual, ou chamá-lo nos `build_mobile_apk.*` depois da cópia.
2. **Entrega sem conferência nos dois destinos** (non-blocking, confirmed): o desktop por pywebview, `build:mobile` e os scripts de APK alterados não foram executados, o que é coerente com não tocar `mobile_app/`. Na etapa de empacotar o APK, rodar essa cadeia, abrir o desktop em `http://127.0.0.1:8000/app/` e conferir a mesma versão nos dois.

</details>

<details>
<summary>Details</summary>

### `mobile_release` sem chamador

Uma busca por `mobile_release` no repositório só encontra o `pyproject.toml`, o teste e os arquivos de `.agents/tasks/` (confirmed). Nem `build_mobile_apk.ps1`, nem `.bat`, nem `build_mobile_jarvis.ps1` rodam o teste. O passo existe só no texto do marcador e em `conflicts.md`.

O teste compara `frontend/dist/index.html` com o `index.html` dos assets e só roda quando os dois existem. Logo depois de `build:mobile`, os dois são iguais porque um acabou de ser copiado do outro. Se uma das pastas não existir, o script de cópia só emite um aviso e sai com 0, e o teste também é pulado. Por isso, ligar o teste aos scripts de APK acrescenta pouca proteção, e a saída mais barata é tratá-lo como conferência manual documentada.

### Cobertura

A evidência traz comando e resultado para cada verificação, incluindo o snapshot de `mobile_app/app/src/main/assets` antes e depois do build (86 arquivos, 0 diferenças), a ausência de `Dev Hacker` no bundle, os dois smokes contra o `dist` e a config carregada com árvore limpa, suja e sem git. A captura `desktop-chat.png`, de 19:19, mostra `v0.1.0 · fc5f703 · 07/11/2026` no rodapé.

O caso sem git foi verificado só carregando a config com o PATH sem git. Nenhum dev server foi aberto sem git, e a string `v0.1.0 · dev` decorre do `filter(Boolean)` em `AppShell.tsx`, não de uma renderização observada.

Não testado: o desktop pelo caminho normal (pywebview em `http://127.0.0.1:8000/app/`), que é o critério de entrega do item 1 em `PENDENCIAS_DO_PAINEL.md`, porque exigiria subir o backend real. Também não foram executados `npm run build:mobile`, `build_mobile_apk.*` e `build_mobile_jarvis.ps1`, então a cadeia nova de scripts do APK continua sem nenhuma execução.

</details>

<details>
<summary>Arquivos alterados</summary>

- `frontend/package.json`: `build` sem a cópia para o Android; novo `build:mobile`; gancho `postbuild` removido.
- `frontend/scripts/postbuild.js` → `frontend/scripts/sync-mobile-assets.js`: renomeado; verificação da Orbe removida; só copia `dist` para os assets Android.
- `frontend/vite.config.ts`: `define.__PANEL_BUILD__` com versão, commit, `dirty` (`git status --porcelain -- .` em `frontend/`) e data; git com timeout de 3 s e fallback vazio.
- `frontend/src/vite-env.d.ts`: tipo de `__PANEL_BUILD__`, com `dirty`.
- `frontend/src/components/AppShell.tsx`: linha `.ws-build-version` no rodapé da barra lateral, com `*` e `title` para árvore suja.
- `frontend/src/styles/workspace.css`: estilo da linha de versão, oculta com a barra lateral recolhida.
- `scripts/build_mobile_apk.ps1`, `scripts/build_mobile_apk.bat`: chamam `npm run build:mobile`; mensagem de erro sem citar a Orbe.
- `pyproject.toml`: marcador `mobile_release`, excluído do `addopts`.
- `tests/test_orb_canonical_integrity.py`: `test_mobile_assets_match_frontend_dist` marcado com `mobile_release`.
- `.agents/rules/jarvis_visual_canonical.md`: cabeçalho de OBSOLETA; texto original recolhido como histórico.
- `docs/PENDENCIAS_DO_PAINEL.md`, `docs/PROJECT_CONTINUITY.md`, `plans/016-neutral-agent-control-platform.md`: referências a `postbuild.js` e à proibição de `npm run build` atualizadas.

Diff completo: `git -C c:/Users/maria/Desktop/Jarvis diff da00309 fc5f703 -M`

</details>
