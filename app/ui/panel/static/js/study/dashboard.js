/* Dashboard de progresso ENEM — sidebar + overlay */
(function () {
  const stagesEl = document.getElementById('study-dashboard-stages');
  const weakEl = document.getElementById('study-dashboard-weak');
  const statsEl = document.getElementById('study-dashboard-stats');
  const sidebarStatsEl = document.getElementById('study-sidebar-stats');
  const sidebarStagesEl = document.getElementById('study-sidebar-stages');
  const sidebarWeakEl = document.getElementById('study-sidebar-weak');
  const progressLabel = document.getElementById('study-progress-label');

  if (!stagesEl && !sidebarStatsEl) return;

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function stageStatusIcon(status) {
    if (status === 'in_progress') return '🟡';
    if (status === 'completed' || status === 'mastered') return '✅';
    return '⬜';
  }

  async function load() {
    const r = await fetch('/api/tutor/progress');
    if (!r.ok) return null;
    return r.json();
  }

  function renderStats(stats, dueCount, targetEl, compact) {
    if (!targetEl) return;
    if (compact) {
      targetEl.innerHTML = `
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div><span class="text-on-surface-variant">Flashcards</span><br><strong>${stats.flashcards_total || 0}</strong></div>
          <div><span class="text-on-surface-variant">Para revisar</span><br><strong class="text-primary-fixed-dim">${dueCount}</strong></div>
          <div><span class="text-on-surface-variant">Questões</span><br><strong>${stats.questions_solved || 0}</strong></div>
          <div><span class="text-on-surface-variant">Sessões</span><br><strong>${stats.sessions || 0}</strong></div>
        </div>
      `;
      return;
    }
    targetEl.innerHTML = `
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div><span class="text-on-surface-variant">Sessões</span><br><strong>${stats.sessions || 0}</strong></div>
        <div><span class="text-on-surface-variant">Questões</span><br><strong>${stats.questions_solved || 0}</strong></div>
        <div><span class="text-on-surface-variant">Flashcards</span><br><strong>${stats.flashcards_total || 0}</strong></div>
        <div><span class="text-on-surface-variant">Para revisar</span><br><strong class="text-primary-fixed-dim">${dueCount}</strong></div>
        <div><span class="text-on-surface-variant">Quizzes</span><br><strong>${stats.quizzes_taken || 0}</strong></div>
        <div><span class="text-on-surface-variant">Feynman</span><br><strong>${stats.feynman_attempts || 0}</strong></div>
      </div>
    `;
  }

  function renderStages(stages, targetEl, compact) {
    if (!targetEl) return;
    targetEl.innerHTML = stages.map((s) => {
      const pct = Math.round((s.mastery || 0) * 100);
      if (compact) {
        return `
          <div class="study-sidebar-stage" title="${escapeHtml(s.title || s.id)}">
            <span class="study-sidebar-stage-icon">${stageStatusIcon(s.status)}</span>
            <span class="study-sidebar-stage-name">${escapeHtml((s.title || s.id).slice(0, 18))}</span>
            <span class="study-sidebar-stage-pct">${pct}%</span>
          </div>
        `;
      }
      return `
        <div class="study-stage-bar">
          <div class="study-stage-bar-label">
            <span>${escapeHtml(s.title || s.id)}</span>
            <span>${pct}% · ${escapeHtml(s.status || '')}</span>
          </div>
          <div class="study-stage-bar-track">
            <div class="study-stage-bar-fill" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderWeak(weak, targetEl) {
    if (!targetEl) return;
    targetEl.innerHTML = weak.length
      ? weak.map((w) => `<span class="study-weak-spot">${escapeHtml(w)}</span>`).join('')
      : '<span class="text-on-surface-variant text-sm">Nenhum ponto fraco registrado.</span>';
  }

  function render(data) {
    const progress = data?.progress || {};
    const stats = progress.stats || {};
    const stages = progress.stages || [];
    const weak = data?.weak_spots || progress.weak_spots || [];
    const dueCount = data?.due_flashcards ?? stats.flashcards_due ?? 0;

    if (progressLabel) {
      const current = stages.find((s) => s.id === progress.current_stage);
      const stageTitle = current?.title || progress.current_stage || '—';
      progressLabel.textContent = `${stageTitle} · ${stats.questions_solved || 0} questões · ${dueCount} cards`;
    }

    renderStats(stats, dueCount, statsEl, false);
    renderStats(stats, dueCount, sidebarStatsEl, true);
    renderStages(stages, stagesEl, false);
    renderStages(stages, sidebarStagesEl, true);
    renderWeak(weak, weakEl);
    renderWeak(weak, sidebarWeakEl);

    window.JarvisStudyToolbar?.setDueBadge(dueCount);
  }

  async function refresh() {
    render(await load());
  }

  window.JarvisStudyDashboard = { refresh };
})();
