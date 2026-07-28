/* Quiz / avaliações da etapa */
(function () {
  const listEl = document.getElementById('study-quiz-list');
  const startBtn = document.getElementById('study-quiz-start');
  const recordBtn = document.getElementById('study-quiz-record');
  const correctInput = document.getElementById('study-quiz-correct');
  const totalInput = document.getElementById('study-quiz-total');

  if (!startBtn) return;

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadAssessments() {
    const r = await fetch('/api/tutor/assessments');
    if (!r.ok) return [];
    const j = await r.json();
    return j.assessments || [];
  }

  function renderList(items) {
    if (!listEl) return;
    if (!items.length) {
      listEl.innerHTML = '<p class="text-on-surface-variant text-sm">Nenhum quiz registrado.</p>';
      return;
    }
    listEl.innerHTML = items.slice().reverse().map((a) => `
      <div class="study-assessment-item">
        <span class="text-primary-fixed-dim">${escapeHtml(a.stage_id || '')}</span>
        <span class="ml-2">${a.correct}/${a.total}</span>
        <span class="text-on-surface-variant text-xs ml-2">${Math.round((a.score || 0) * 100)}%</span>
        <span class="text-xs text-on-surface-variant ml-2">${escapeHtml(a.date || '')}</span>
      </div>
    `).join('');
  }

  startBtn.addEventListener('click', () => {
    const chatInput = document.getElementById('study-chat-input');
    if (chatInput) {
      chatInput.value = 'quiz — Faça uma avaliação da minha etapa atual com 5 questões, uma de cada vez.';
      document.getElementById('study-send-button')?.click();
    }
  });

  recordBtn?.addEventListener('click', async () => {
    const correct = parseInt(correctInput?.value || '0', 10);
    const total = parseInt(totalInput?.value || '0', 10);
    if (!total) return;

    await fetch('/api/tutor/assessments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correct, total }),
    });

    if (correctInput) correctInput.value = '';
    if (totalInput) totalInput.value = '';
    await refresh();
    window.JarvisStudyDashboard?.refresh();
  });

  async function refresh() {
    renderList(await loadAssessments());
  }

  window.JarvisStudyAssessment = { refresh };
})();
