/* Modo Feynman — explicar de volta */
(function () {
  const listEl = document.getElementById('study-feynman-list');
  const topicInput = document.getElementById('study-feynman-topic');
  const explainInput = document.getElementById('study-feynman-explanation');
  const submitBtn = document.getElementById('study-feynman-submit');

  if (!submitBtn) return;

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadAttempts() {
    const r = await fetch('/api/tutor/feynman');
    if (!r.ok) return [];
    const j = await r.json();
    return j.attempts || [];
  }

  function renderList(attempts) {
    if (!listEl) return;
    if (!attempts.length) {
      listEl.innerHTML = '<p class="text-on-surface-variant text-sm">Nenhuma tentativa ainda.</p>';
      return;
    }
    listEl.innerHTML = attempts.slice().reverse().map((a) => `
      <div class="study-assessment-item">
        <strong>${escapeHtml(a.topic || 'Tópico')}</strong>
        <span class="text-on-surface-variant text-xs ml-2">${escapeHtml(a.date || '')}</span>
        ${a.grade != null ? `<span class="text-primary-fixed-dim text-xs ml-2">Nota: ${a.grade}/5</span>` : ''}
        <p class="mt-2 text-sm text-on-surface-variant">${escapeHtml((a.explanation || '').slice(0, 200))}${(a.explanation || '').length > 200 ? '…' : ''}</p>
      </div>
    `).join('');
  }

  submitBtn.addEventListener('click', async () => {
    const topic = (topicInput?.value || '').trim();
    const explanation = (explainInput?.value || '').trim();
    if (!topic || !explanation) return;

    await fetch('/api/tutor/feynman', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, explanation }),
    });

    const chatInput = document.getElementById('study-chat-input');
    if (chatInput) {
      chatInput.value = `[FEYNMAN] Avalie minha explicação sobre "${topic}":\n\n${explanation}`;
      document.getElementById('study-send-button')?.click();
    }

    if (topicInput) topicInput.value = '';
    if (explainInput) explainInput.value = '';
    await refresh();
  });

  async function refresh() {
    renderList(await loadAttempts());
  }

  window.JarvisStudyFeynman = { refresh };
})();
