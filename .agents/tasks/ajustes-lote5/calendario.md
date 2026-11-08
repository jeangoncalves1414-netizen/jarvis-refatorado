# Calendário no tema do workspace
- `components/Calendar.tsx`: classes `calendar-*` trocadas por `cal-*`. Layout em dois cartões: calendário à esquerda, painel do dia (agendar e lembretes do dia) à direita, com estado vazio. Lógica, API `/api/calendar`, lembretes e cancelamento intactos.
- `styles/calendar.css` (novo, importado no componente): usa os tokens `--ws-*` (cartão `--ws-panel`, borda `--ws-border`, botão primário em `--ws-accent` com `--ws-accent-ink`), tematiza o react-day-picker (hoje, selecionado, ponto nos dias com evento) e o modal de lembrete.
- Os estilos antigos `calendar-focus*` em `styles.css` ficaram órfãos (não removidos).
- Só `tsc --noEmit` (limpo); sem verificação visual.
