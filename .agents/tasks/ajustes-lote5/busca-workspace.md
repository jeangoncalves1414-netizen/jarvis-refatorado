# Buscar no workspace no tema do workspace
## O que mudou
- `frontend/src/styles/command-palette.css` (novo, importado em `main.tsx` depois de `styles.css`): estilo do popup `CommandPalette` com os tokens `--ws-*`. Cartão `--ws-panel` com borda `--ws-border`, cabeçalho e rodapé em `--ws-bg`, ícone de busca e item selecionado em `--ws-accent`/`--ws-accent-soft`/`--ws-accent-line`, `kbd` e categoria como pílulas discretas. Sem o ciano/glow antigo.
- Escopo `.ws-command-dialog`, então não afeta outros componentes. O `dialog` ganhou fundo escuro com blur leve; o `::backdrop` nativo ficou transparente.
- As classes `cmd-palette-header`, `cmd-item-body`, `cmd-empty-state`, `cmd-footer-*` etc. usadas pelo componente não tinham CSS; agora têm. Os blocos antigos `cmd-*` em `styles.css` continuam (sobrescritos, parcialmente órfãos).
- `CommandPalette.tsx` não foi alterado: busca, Ctrl+K, setas, Enter, Esc, foco no campo, clique fora e sons seguem iguais.
## Observações
- Só `tsc --noEmit`; sem verificação visual.
- O estado vazio ainda usa o emoji 🔍.
## Testar
Ctrl+K (ou botão "Buscar no workspace"): digitar, navegar com setas, Enter, Esc, clique fora; conferir o visual em tela estreita.
