/* Revisão espaçada — flashcards com SM-2 */
(function () {
  const overlay = document.getElementById('study-overlay-flashcards');
  if (!overlay) return;

  const frontEl = document.getElementById('study-fc-front');
  const backEl = document.getElementById('study-fc-back');
  const counterEl = document.getElementById('study-fc-counter');
  const cardEl = document.getElementById('study-fc-card');
  const actionsEl = document.getElementById('study-fc-actions');

  let queue = [];
  let index = 0;
  let flipped = false;

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadDue() {
    const r = await fetch('/api/tutor/flashcards/due');
    if (!r.ok) return [];
    const j = await r.json();
    return j.cards || [];
  }

  function render() {
    flipped = false;
    cardEl?.classList.remove('is-flipped');
    if (index >= queue.length) {
      if (frontEl) frontEl.innerHTML = '🎉<br><br>Todos os cards de hoje foram revisados!';
      if (backEl) backEl.textContent = '';
      if (counterEl) counterEl.textContent = 'Concluído';
      if (actionsEl) actionsEl.style.display = 'none';
      return;
    }
    const card = queue[index];
    if (frontEl) frontEl.innerHTML = escapeHtml(card.front).replace(/\n/g, '<br>');
    if (backEl) backEl.innerHTML = escapeHtml(card.back).replace(/\n/g, '<br>');
    if (counterEl) counterEl.textContent = `${index + 1} / ${queue.length}`;
    if (actionsEl) actionsEl.style.display = 'flex';
  }

  async function grade(gradeValue) {
    if (index >= queue.length) return;
    const card = queue[index];
    await fetch('/api/tutor/flashcards/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: card.id, grade: gradeValue }),
    });
    index += 1;
    render();
    const remaining = queue.length - index;
    window.JarvisStudyToolbar?.setDueBadge(remaining);
    if (index >= queue.length) {
      window.JarvisStudyDashboard?.refresh();
    }
  }

  cardEl?.addEventListener('click', () => {
    if (index >= queue.length) return;
    flipped = !flipped;
    cardEl.classList.toggle('is-flipped', flipped);
  });

  document.getElementById('study-fc-again')?.addEventListener('click', (e) => { e.stopPropagation(); grade(0); });
  document.getElementById('study-fc-hard')?.addEventListener('click', (e) => { e.stopPropagation(); grade(1); });
  document.getElementById('study-fc-good')?.addEventListener('click', (e) => { e.stopPropagation(); grade(2); });
  document.getElementById('study-fc-easy')?.addEventListener('click', (e) => { e.stopPropagation(); grade(3); });

  window.JarvisStudyFlashcards = {
    async open() {
      queue = await loadDue();
      index = 0;
      if (!queue.length) {
        if (frontEl) frontEl.textContent = 'Nenhum flashcard pendente hoje. Continue estudando!';
        if (counterEl) counterEl.textContent = '0 cards';
        if (actionsEl) actionsEl.style.display = 'none';
        return;
      }
      render();
    },
    async refreshDueCount() {
      const cards = await loadDue();
      window.JarvisStudyToolbar?.setDueBadge(cards.length);
    },
  };
})();
