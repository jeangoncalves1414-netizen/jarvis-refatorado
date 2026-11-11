# Conflitos registrados no lote desktop-batch1

## Item 1: regra canônica da Orbe e build web separado

**Situação: resolvido pela usuária em 2026-11-07.** As decisões abaixo substituem `.agents/rules/jarvis_visual_canonical.md` e foram aplicadas no commit `fc5f703`.

### O conflito

A regra `.agents/rules/jarvis_visual_canonical.md`, `frontend/scripts/postbuild.js` e `tests/test_orb_canonical_integrity.py` vieram do commit `90a759a`. O item 3 da regra mandava sincronizar `frontend/dist` com `mobile_app/app/src/main/assets` a cada `npm run build`, e o postbuild barrava o build se a Orbe mudasse. O item 1 deste lote e o item 1 de `docs/PENDENCIAS_DO_PAINEL.md` pediam o contrário: o build web gera só `frontend/dist`, nunca toca `mobile_app/` e não depende da Orbe.

### Primeira iteração (commit `fe25fd8`)

- `npm run build` passou a ser `tsc -b && vite build`, sem verificar a Orbe e sem copiar nada para o Android. O gancho `postbuild`, que fazia a cópia rodar duas vezes, foi removido.
- A verificação da Orbe e a cópia foram para `frontend/scripts/sync-mobile-assets.js`, o antigo `postbuild.js`, chamado só por `npm run build:mobile`.
- `scripts/build_mobile_apk.ps1` e `.bat` passaram a chamar `npm run build:mobile`.
- **Correção de uma afirmação da primeira iteração.** Este arquivo dizia que "o fluxo do APK mantém a cópia e a verificação da Orbe". Isso valia para `build_mobile_apk.*`, mas não para `scripts/build_mobile_jarvis.ps1 -RebuildWeb`. Esse script chama `npm run build`, que deixou de verificar a Orbe, e faz a própria cópia antes do Gradle. Depois de `fe25fd8`, esse caminho gerava o APK sem a verificação. A revisão apontou isso como bloqueante (achado 1 de `review-item1.json`).

### Decisões da usuária (2026-11-07) e o que foi feito no commit `fc5f703`

1. **A usuária não quer a Orbe.** Um personagem 3D pode vir no futuro, como última prioridade. Os componentes da Orbe (`JarvisOrb3D.tsx`, `JarvisOrb.tsx`) e o `DashboardHero` ficam como estão, sem esforço extra.
2. **A verificação da Orbe não bloqueia mais nenhum build.** Ela foi removida de `sync-mobile-assets.js`, que agora só copia o `dist` para os assets Android. Com isso, `build:mobile`, `build_mobile_apk.*` e `build_mobile_jarvis.ps1 -RebuildWeb` ficam consistentes: nenhum deles verifica a Orbe. `build_mobile_jarvis.ps1` não foi alterado. As mensagens de erro de `build_mobile_apk.ps1` e `.bat` deixaram de citar a Orbe. Isso resolve o achado 1 da revisão sem adicionar a checagem ao script.
3. **A regra `.agents/rules/jarvis_visual_canonical.md` está marcada como OBSOLETA desde 2026-11-07,** com o motivo (identidade neutra Workspace, sem Orbe, possível personagem 3D no futuro). O texto original ficou abaixo, como histórico. A única regra que continua valendo é que os assets Android só são sincronizados por `npm run build:mobile`. Isso resolve o achado 3.
4. **`test_mobile_assets_match_frontend_dist` só roda na geração do APK.** O teste ganhou o marcador `mobile_release`, registrado em `pyproject.toml` e excluído do `addopts`, como já acontece com `integration`, `live`, `network` e `hardware`. Ele roda com `python -m pytest -m mobile_release tests/test_orb_canonical_integrity.py`, depois de `npm run build:mobile`. Os outros quatro testes da Orbe não mudaram e passam. Isso resolve o achado 2.

### O que ainda cita a Orbe como canônica (fora do escopo deste item)

- `docs/FEATURE_ROADMAP_AND_REFERENCE_ANALYSIS.md` (linhas 26 e 53-56) ainda descreve a Orbe como "CANÔNICO FIXO". Não alterei esse arquivo.
- `tests/test_orb_canonical_integrity.py` mantém os quatro testes sobre o conteúdo de `JarvisOrb3D.tsx`. Eles passam e não bloqueiam builds, mas falharão se alguém remover a Orbe no futuro.
