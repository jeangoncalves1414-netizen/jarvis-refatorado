# LifeOS no tema do workspace
## O que mudou
- O que a usuária vê na janela "Evolução"/Life OS é o app separado `/evolute/` embutido em iframe por `EvoluteHubPage.tsx`. Os dois foram refeitos.
- `frontend/src/styles/ws-tokens.css` (novo): fonte única dos tokens `--ws-*` (antes só em `.agent-workspace` no `workspace.css`, de onde foram removidos). Agora em `:root, .agent-workspace`, com novos `--ws-accent-ink/-soft/-line`, `--ws-warn/-danger/-ok/-info`, `--ws-hover`, `--ws-field`, `--ws-radius`.
- `evolute/src/index.css`: importa `ws-tokens.css` do frontend (sem duplicar paleta) e remapeia a paleta monocromática do Tailwind (`--color-black`, `--color-neutral-*`) para os tokens. `bg-white`/`border-white` viram o acento verde-menta, gráficos brancos (recharts) também, fonte Geist, scrollbar e foco iguais ao chat. Todas as telas do app (hábitos, água, treino, estudos, leitura, mente, anti-vício, álbum, calendário, busca interna, config) herdam o tema sem mudar lógica nem dados.
- `EvoluteHubPage.tsx`: estilos inline trocados por classes `lo-*`; moldura (barra Recarregar / Janela / Resumo, loader) e hub de resumo (água, hábitos, treino, estudo, fala do dia). Lógica, API (`/api/evolute/*`), fallback em localStorage e sync (`jarvis-sync-applied`) intactos.
- `styles/lifeos.css` (novo): componentes `lo-*` e o HUD "Life OS · Hoje" do painel inicial (`lifeos-hud-*`, mesmas classes de `DashboardPage`, agora no tema). Removidos de `styles.css` os blocos órfãos antigos (HUD roxo, `evolute-integrated-view*`, `lifeos-hud-open-btn`).
- Registro de janelas, comandos `/lifeos`, `/agua`, `/foco` e funcionamento sem IA não foram tocados.
- `evolute/dist` foi reconstruído com `npm run build` (dist é ignorado pelo git; o backend serve esse build). Um APK precisa de novo build próprio.
## Para Calendário e Busca reutilizarem
- Tokens: `--ws-bg, --ws-sidebar, --ws-panel, --ws-border, --ws-text, --ws-muted, --ws-accent, --ws-accent-ink, --ws-accent-soft, --ws-accent-line, --ws-warn, --ws-danger, --ws-ok, --ws-info, --ws-hover, --ws-field, --ws-radius` (disponíveis em qualquer lugar, não só dentro de `.agent-workspace`).
- Componentes em `styles/lifeos.css`: `.lo-card` (painel), `.lo-eyebrow` (rótulo de seção), `.lo-pill` (+`.accent`/`.warn`), `.lo-btn` (+`.primary`/`.ghost`), `.lo-bar > span` (barra de progresso), `.lo-notice`, `.lo-grid`/`.lo-span`/`.lo-col`, `.lo-tile`, `.lo-spinner`. Também `.st-*` de `styles/settings.css` (campos, listas) se `.agent-workspace` envolver.
- Padrão: fundo `--ws-bg`, cartões `--ws-panel` com borda `--ws-border` e raio 12px, botão principal em `--ws-accent` com texto `--ws-accent-ink`, secundário com `--ws-accent-soft`/`--ws-accent-line`.
- O Calendário e a Busca do Life OS (dentro de `/evolute`) já herdam o tema pelo remapeamento; as versões do Jarvis principal ainda precisam das classes acima.
## Arquivos
frontend/src/styles/ws-tokens.css (novo), styles/lifeos.css (novo), styles/workspace.css, styles.css, main.tsx, pages/EvoluteHubPage.tsx, evolute/src/index.css
## Observações
- Sem verificação visual nem testes; só `tsc --noEmit` (limpo) e `npm run build` do evolute (ok).
- Os componentes do app evolute ainda usam classes Tailwind (pretas/cinzas) remapeadas; ajustes finos por tela podem aparecer ao testar.
