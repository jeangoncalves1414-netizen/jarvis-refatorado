/* Modo Estudos ENEM — canvas infinito pan/zoom + chat tutor */
(function () {
  const studyScreen = document.getElementById('screen-study');
  if (!studyScreen) return;

  const canvasViewport = document.getElementById('study-canvas-viewport');
  const canvasWorld = document.getElementById('study-canvas-world');
  const sessionList = document.getElementById('study-session-list');
  const chatMessages = document.getElementById('study-chat-messages');
  const chatInput = document.getElementById('study-chat-input');
  const sendBtn = document.getElementById('study-send-button');
  const newSessionBtn = document.getElementById('study-new-session');
  const fullscreenBtn = document.getElementById('study-fullscreen-btn');
  const progressLabel = document.getElementById('study-progress-label');

  let currentSession = null;
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let panStart = { x: 0, y: 0 };
  let pollTimer = null;

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function applyTransform() {
    if (!canvasWorld) return;
    canvasWorld.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  function bindCanvasControls() {
    if (!canvasViewport) return;

    canvasViewport.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const rect = canvasViewport.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const newScale = Math.min(3, Math.max(0.2, scale * delta));
      panX = mx - (mx - panX) * (newScale / scale);
      panY = my - (my - panY) * (newScale / scale);
      scale = newScale;
      applyTransform();
    }, { passive: false });

    canvasViewport.addEventListener('mousedown', (e) => {
      if (e.button === 1 || e.button === 2 || e.altKey || e.code === 'Space') {
        isPanning = true;
        panStart = { x: e.clientX - panX, y: e.clientY - panY };
        canvasViewport.classList.add('is-panning');
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!isPanning) return;
      panX = e.clientX - panStart.x;
      panY = e.clientY - panStart.y;
      applyTransform();
    });

    window.addEventListener('mouseup', () => {
      isPanning = false;
      canvasViewport?.classList.remove('is-panning');
    });

    canvasViewport.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  function renderWhiteboard(elements) {
    if (!canvasWorld) return;
    canvasWorld.innerHTML = '';
    (elements || []).forEach((el) => {
      const node = document.createElement('div');
      node.className = 'study-element';
      node.style.left = `${el.x || 0}px`;
      node.style.top = `${el.y || 0}px`;
      if (el.type === 'image') {
        const img = document.createElement('img');
        img.src = el.content || '';
        img.alt = 'Imagem explicativa';
        img.style.width = `${el.width || 250}px`;
        img.style.height = `${el.height || 180}px`;
        img.className = 'study-element-image';
        node.appendChild(img);
      } else {
        node.className += ' study-element-text';
        node.style.fontSize = `${el.size || 16}px`;
        node.style.color = el.color || '#ffffff';
        if (el.role) node.dataset.role = el.role;
        node.textContent = el.content || '';
      }
      canvasWorld.appendChild(node);
    });
  }

  async function loadWhiteboard(sessionId) {
    if (!sessionId) return;
    try {
      const r = await fetch(`/api/sessions/${sessionId}/whiteboard`);
      if (r.ok) {
        const j = await r.json();
        renderWhiteboard(j.whiteboard || []);
      }
    } catch (e) {
      console.warn('Falha ao carregar whiteboard', e);
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => {
      if (currentSession) loadWhiteboard(currentSession);
    }, 2500);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function refreshStudySessions() {
    if (!sessionList) return;
    try {
      const r = await fetch('/api/sessions?type=tutor');
      const j = await r.json();
      const sessions = j.sessions || [];
      sessionList.innerHTML = '';
      if (!sessions.length) {
        sessionList.innerHTML = '<p class="text-on-surface-variant text-body-sm px-2">Nenhuma sessão de estudo.</p>';
        return;
      }
      sessions.forEach((s) => {
        const btn = document.createElement('button');
        btn.className = `study-session-btn w-full text-left p-3 rounded-lg border transition-all ${s.id === currentSession ? 'border-primary-fixed-dim/40 bg-white/5' : 'border-white/5 hover:bg-white/5'}`;
        btn.dataset.sessionId = s.id;
        const count = (s.whiteboard || []).length;
        btn.innerHTML = `<div class="text-label-md font-label-md text-on-surface">${escapeHtml(s.title || 'Estudo')}</div><div class="text-label-sm text-on-surface-variant mt-1">${count} elementos no quadro</div>`;
        sessionList.appendChild(btn);
      });
    } catch (e) {
      console.error('Erro ao listar sessões de estudo', e);
    }
  }

  async function loadProgress() {
    if (!progressLabel) return;
    try {
      const r = await fetch('/api/tutor/progress');
      if (r.ok) {
        const j = await r.json();
        const stage = j.progress?.current_stage || '—';
        const solved = j.progress?.stats?.questions_solved || 0;
        const due = j.due_flashcards ?? j.progress?.stats?.flashcards_due ?? 0;
        progressLabel.textContent = `${stage} · ${solved} questões · ${due} cards`;
      }
    } catch (_) {}
  }

  async function createStudySession(title) {
    try {
      const r = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || 'Sessão ENEM', type: 'tutor' }),
      });
      const j = await r.json();
      return j.id;
    } catch (e) {
      console.error('Erro ao criar sessão', e);
      return null;
    }
  }

  function appendStudyMessage(role, text) {
    if (!chatMessages) return;
    const div = document.createElement('div');
    div.className = role === 'user' ? 'study-msg study-msg-user' : 'study-msg study-msg-tutor';
    div.innerHTML = `<span class="study-msg-role">${role === 'user' ? 'Você' : 'Professor'}</span><p>${escapeHtml(text)}</p>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function tryLocalTutorCommand(text) {
    const n = text.trim().toLowerCase();
    const open = (mode, fn) => {
      window.JarvisStudyToolbar?.openOverlay(mode);
      fn?.();
      appendStudyMessage('assistant', `Modo ${mode} aberto.`);
      return true;
    };
    if (/^(review|revisar|revisar cards|flashcards|cards|meus cards)$/.test(n)) {
      return open('review', () => window.JarvisStudyFlashcards?.open?.());
    }
    if (/^(feynman|explicar de volta)$/.test(n)) {
      return open('feynman', () => window.JarvisStudyFeynman?.refresh?.());
    }
    if (/^(quiz|teste|test me|testar)$/.test(n)) {
      return open('quiz', () => window.JarvisStudyAssessment?.refresh?.());
    }
    if (/^(progress|progresso|onde estou|dashboard)$/.test(n)) {
      return open('progress', () => window.JarvisStudyDashboard?.refresh?.());
    }
    if (/^(quest(ã|a)o|questões|questions|enem|banco)$/.test(n)) {
      return open('questions', () => window.JarvisStudyEnem?.open?.());
    }
    return false;
  }

  async function sendStudyMessage(extra = {}) {
    const text = (extra.message ?? chatInput?.value ?? '').trim();
    if (!text) return;
    if (chatInput && !extra.message) chatInput.value = '';

    if (!extra.enem_context && !extra.enem_question_id && tryLocalTutorCommand(text)) {
      return;
    }

    if (!currentSession) {
      currentSession = await createStudySession(text.slice(0, 40));
      await refreshStudySessions();
    }
    if (!currentSession) return;

    appendStudyMessage('user', text);
    if (window.JarvisOrb) window.JarvisOrb.setState('thinking');

    const payload = {
      message: text,
      session_id: currentSession,
      mode: 'tutor',
      ...extra,
    };

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const j = await r.json();
      appendStudyMessage('assistant', j.summary || 'Sem resposta.');
      if (j.whiteboard_updated) await loadWhiteboard(currentSession);
      await loadProgress();
      window.JarvisStudyDashboard?.refresh();
      if (window.JarvisOrb) {
        window.JarvisOrb.setState('speaking');
        const speakText = (j.summary || '').replace(/\[tool:[^\]]+\]/g, '').trim();
        if (speakText && window.JarvisVoice?.speak) window.JarvisVoice.speak(speakText);
        setTimeout(() => window.JarvisOrb?.setState('idle'), 3000);
      }
    } catch (err) {
      appendStudyMessage('assistant', `Erro: ${err.message || err}`);
      if (window.JarvisOrb) window.JarvisOrb.setState('error');
    }
  }

  async function loadStudyHistory(sessionId) {
    if (!chatMessages || !sessionId) return;
    chatMessages.innerHTML = '';
    try {
      const r = await fetch(`/api/sessions/${sessionId}/history`);
      if (r.ok) {
        const j = await r.json();
        (j.history || []).forEach((m) => appendStudyMessage(m.role || 'assistant', m.content || m.text || ''));
      }
    } catch (e) {
      console.warn('Falha ao carregar histórico de estudo', e);
    }
  }

  sessionList?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.study-session-btn');
    if (!btn) return;
    currentSession = btn.dataset.sessionId;
    await refreshStudySessions();
    await loadWhiteboard(currentSession);
    await loadStudyHistory(currentSession);
    startPolling();
  });

  newSessionBtn?.addEventListener('click', async () => {
    currentSession = await createStudySession('Nova sessão ENEM');
    scale = 1; panX = 0; panY = 0;
    applyTransform();
    renderWhiteboard([]);
    if (chatMessages) chatMessages.innerHTML = '';
    await refreshStudySessions();
    startPolling();
  });

  sendBtn?.addEventListener('click', () => sendStudyMessage());
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendStudyMessage(); }
  });

  async function ensureSession(title) {
    if (currentSession) return currentSession;
    currentSession = await createStudySession(title || 'Questão ENEM');
    await refreshStudySessions();
    startPolling();
    return currentSession;
  }

  fullscreenBtn?.addEventListener('click', () => {
    const target = document.getElementById('study-canvas-shell');
    if (!document.fullscreenElement && target?.requestFullscreen) {
      target.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  });

  bindCanvasControls();
  applyTransform();
  loadProgress();

  window.JarvisStudy = {
    getSessionId: () => currentSession,
    ensureSession,
    loadWhiteboard,
    renderWhiteboard,
    appendStudyMessage,
    sendTutorMessage: (message, opts = {}) => sendStudyMessage({ message, ...opts }),
    onEnter: async () => {
      await refreshStudySessions();
      startPolling();
      loadProgress();
      window.JarvisStudyDashboard?.refresh();
      window.JarvisStudyFlashcards?.refreshDueCount();
      window.JarvisStudyEnem?.refresh?.();
    },
    onLeave: () => stopPolling(),
  };
})();
