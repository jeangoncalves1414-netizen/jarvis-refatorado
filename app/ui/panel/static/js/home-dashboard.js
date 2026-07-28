(function () {
  const subtitleEl = document.getElementById('dashboard-subtitle');
  const tasksListEl = document.getElementById('dashboard-tasks-list');
  const activityListEl = document.getElementById('dashboard-activity-list');
  const timersListEl = document.getElementById('dashboard-timers-list');

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
  }

  function setStat(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function formatTime(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' });
    } catch (_) {
      return iso;
    }
  }

  function renderTasks(tasks) {
    if (!tasksListEl) return;
    const items = tasks?.items || [];
    if (!items.length) {
      tasksListEl.innerHTML = '<p class="text-body-sm text-on-surface-variant">Nenhuma tarefa pendente. Use "New Task" na barra lateral.</p>';
      return;
    }
    tasksListEl.innerHTML = items.map((task) => `
      <div class="dashboard-task-row flex items-center gap-3 p-3 rounded-lg border border-white/5 bg-surface-container-low hover:border-white/10 transition-colors" data-task-id="${escapeHtml(task.id)}">
        <button type="button" class="dashboard-task-toggle shrink-0 w-5 h-5 rounded border border-primary-fixed-dim/40 hover:bg-primary-fixed-dim/10" title="Concluir tarefa" aria-label="Concluir"></button>
        <span class="flex-1 text-body-sm text-on-surface truncate">${escapeHtml(task.title)}</span>
        <button type="button" class="dashboard-task-delete text-on-surface-variant hover:text-error text-sm" title="Remover" aria-label="Remover">
          <span class="material-symbols-outlined text-base">close</span>
        </button>
      </div>
    `).join('');
  }

  function renderActivity(entries) {
    if (!activityListEl) return;
    if (!entries?.length) {
      activityListEl.innerHTML = '<p class="text-body-sm text-on-surface-variant">Nenhuma atividade recente ainda.</p>';
      return;
    }
    activityListEl.innerHTML = entries.map((entry) => `
      <div class="flex gap-3 py-2 border-b border-white/5 last:border-0">
        <span class="material-symbols-outlined text-primary-fixed-dim text-sm mt-0.5">${entry.type === 'study' ? 'school' : entry.type === 'task' ? 'task_alt' : 'chat'}</span>
        <div class="min-w-0 flex-1">
          <p class="text-body-sm text-on-surface truncate">${escapeHtml(entry.message)}</p>
          <p class="text-label-sm text-on-surface-variant">${formatTime(entry.timestamp)}</p>
        </div>
      </div>
    `).join('');
  }

  function renderTimers(timers) {
    if (!timersListEl) return;
    if (!timers?.length) {
      timersListEl.innerHTML = '<p class="text-label-sm text-on-surface-variant">Nenhum timer ativo</p>';
      return;
    }
    timersListEl.innerHTML = timers.map((t) => `
      <div class="flex items-center justify-between text-label-sm text-on-surface-variant py-1">
        <span class="truncate">${escapeHtml(t.label)}</span>
        <span class="text-primary-fixed-dim shrink-0 ml-2">${formatTime(t.fire_at)}</span>
      </div>
    `).join('');
  }

  function renderDashboard(data) {
    if (!data) return;

    const sys = data.system || {};
    const sessions = data.sessions || {};
    const tutor = data.tutor || {};
    const tasks = data.tasks || {};

    if (subtitleEl) {
      subtitleEl.textContent = `${sessions.total || 0} sessões · ${tutor.due_flashcards || 0} flashcards pendentes · ${tasks.pending || 0} tarefas abertas`;
    }

    setStat('dash-stat-cpu', `${Math.round(sys.cpu || 0)}%`);
    setStat('dash-stat-ram', `${sys.ram_used || 0} / ${sys.ram_total || 0} GB`);
    setStat('dash-stat-sessions', String(sessions.total || 0));
    setStat('dash-stat-flashcards', String(tutor.due_flashcards || 0));

    const cpuBar = document.getElementById('statCpuBar');
    const ramBar = document.getElementById('statRamBar');
    const cpuText = document.getElementById('statCpuText');
    const ramText = document.getElementById('statRamText');
    if (cpuText) cpuText.textContent = `${Math.round(sys.cpu || 0)}%`;
    if (ramText) ramText.textContent = `${sys.ram_used || 0} GB / ${sys.ram_total || 0} GB`;
    if (cpuBar) cpuBar.style.width = `${Math.min(100, sys.cpu || 0)}%`;
    if (ramBar) ramBar.style.width = `${Math.min(100, sys.ram_percent || 0)}%`;

    setStat('dash-tutor-stage', tutor.stage || '—');
    setStat('dash-enem-count', String(data.enem?.questions || 0));
    setStat('dash-tasks-pending', String(tasks.pending || 0));

    renderTasks(tasks);
    renderActivity(data.activity);
    renderTimers(data.timers);
  }

  async function loadHudWidgets() {
    try {
      const [realtimeRes, proactiveRes, trayRes] = await Promise.allSettled([
        fetch('/api/realtime').then((r) => r.json()),
        fetch('/api/proactive').then((r) => r.json()),
        fetch('/api/tray').then((r) => r.json()),
      ]);

      if (realtimeRes.status === 'fulfilled' && realtimeRes.value) {
        const rt = realtimeRes.value;
        const w = rt.weather || {};
        if (w.ok) {
          setStat('hud-weather-temp', `${w.temp_c ?? '--'}°C`);
          setStat('hud-weather-desc', w.description || 'Normal');
          setStat('hud-weather-city', w.city || 'Local');
        } else {
          setStat('hud-weather-temp', '--°C');
          setStat('hud-weather-desc', w.error ? 'Indisponível' : 'Erro no clima');
        }

        const f = rt.finance || {};
        if (f.ok && f.currencies) {
          const usdVal = typeof f.currencies.USD?.bid === 'number' ? f.currencies.USD.bid : parseFloat(f.currencies.USD?.bid);
          const eurVal = typeof f.currencies.EUR?.bid === 'number' ? f.currencies.EUR.bid : parseFloat(f.currencies.EUR?.bid);
          const btcVal = typeof f.currencies.BTC?.bid === 'number' ? f.currencies.BTC.bid : parseFloat(f.currencies.BTC?.bid);

          const usd = !isNaN(usdVal) ? `USD: R$ ${usdVal.toFixed(2)}` : 'USD: --';
          const eur = !isNaN(eurVal) ? `EUR: R$ ${eurVal.toFixed(2)}` : 'EUR: --';
          const btc = !isNaN(btcVal) ? `BTC: R$ ${(btcVal / 1000).toFixed(0)}k` : 'BTC: --';
          setStat('hud-fin-usd', usd);
          setStat('hud-fin-eur', eur);
          setStat('hud-fin-btc', btc);
        } else {
          setStat('hud-fin-usd', 'USD: --');
          setStat('hud-fin-eur', 'EUR: --');
          setStat('hud-fin-btc', 'BTC: --');
        }
      }

      if (proactiveRes.status === 'fulfilled' && proactiveRes.value) {
        const pr = proactiveRes.value;
        const cfg = pr.config || {};
        setStat('hud-briefing-time', cfg.briefing_time || '08:00');
        const count = pr.reminders?.length || 0;
        setStat('hud-reminders-count', `${count} lembrete${count === 1 ? '' : 's'} pendente${count === 1 ? '' : 's'}`);
      }

      if (trayRes.status === 'fulfilled' && trayRes.value) {
        const tr = trayRes.value;
        setStat('hud-boot-status', `Boot Windows: ${tr.boot_enabled ? 'Ativo ✅' : 'Desativado'}`);
      }
    } catch (e) {
      console.warn('Falha ao carregar HUD widgets', e);
    }
  }

  async function loadDashboard() {
    try {
      const r = await fetch('/api/dashboard');
      if (r.ok) {
        const data = await r.json();
        renderDashboard(data);
      }
      await loadHudWidgets();
    } catch (e) {
      console.warn('Falha ao carregar dashboard', e);
    }
  }

  // Executa imediatamente na inicialização da página
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadDashboard);
  } else {
    loadDashboard();
  }

  // Polling periódico a cada 25s
  setInterval(loadHudWidgets, 25000);

  async function postTaskAction(action, payload) {
    const r = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, ...payload }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Erro na tarefa');
    await loadDashboard();
    return data;
  }

  tasksListEl?.addEventListener('click', async (event) => {
    const row = event.target.closest('[data-task-id]');
    if (!row) return;
    const taskId = row.dataset.taskId;
    if (event.target.closest('.dashboard-task-toggle')) {
      try {
        await postTaskAction('toggle', { task_id: taskId });
      } catch (e) {
        alert(e.message);
      }
      return;
    }
    if (event.target.closest('.dashboard-task-delete')) {
      if (!confirm('Remover esta tarefa?')) return;
      try {
        await postTaskAction('delete', { task_id: taskId });
      } catch (e) {
        alert(e.message);
      }
    }
  });

  window.JarvisHomeDashboard = { load: loadDashboard, refresh: loadDashboard };
})();
