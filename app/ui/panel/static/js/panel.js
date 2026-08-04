(function(){
  const textarea = document.getElementById('chat-textarea');
  const sendBtn = document.getElementById('chat-send-button');
  const micBtn = document.getElementById('chat-mic-button');
  const messagesContainer = document.getElementById('chat-messages');
  const navButtons = Array.from(document.querySelectorAll('.nav-button[data-screen]'));
  const settingsButton = document.getElementById('settings-button');
  const screens = Array.from(document.querySelectorAll('#screen-area > section[id^="screen-"]'));
  const climateTemperature = document.getElementById('climate-temperature');
  const climateCaption = document.getElementById('climate-caption');
  const cameraModalBackdrop = document.getElementById('camera-modal-backdrop');
  const cameraModalImage = document.getElementById('camera-modal-image');
  const cameraModalTitle = document.getElementById('camera-modal-title');
  const cameraModalDescription = document.getElementById('camera-modal-description');
  const cameraModalClose = document.getElementById('camera-modal-close');
  const sessionListContainer = document.getElementById('session-list');

  let currentSession = null;
  let currentClimateTemp = 22;

  // --- CONTROLE DE MENUS & DE NAVEGAÇÃO ---
  function setActiveNavButton(activeBtn){
    navButtons.forEach(btn => {
      const isActive = btn === activeBtn;
      btn.classList.toggle('text-primary-fixed-dim', isActive);
      btn.classList.toggle('font-bold', isActive);
      btn.classList.toggle('border-r-2', isActive);
      btn.classList.toggle('border-primary-fixed-dim', isActive);
      btn.classList.toggle('bg-white/5', isActive);
      btn.classList.toggle('text-on-surface-variant', !isActive);
      btn.classList.toggle('bg-transparent', !isActive);
    });
  }

  function renderClimateTemperature(value){
    currentClimateTemp = value;
    if(climateTemperature){
      climateTemperature.classList.remove('is-changing');
      void climateTemperature.offsetWidth;
      climateTemperature.classList.add('is-changing');
      climateTemperature.textContent = `${value}°C`;
    }
    if(climateCaption){
      climateCaption.textContent = `Definido para ${value}°C (painel)`;
    }
  }

  async function setClimateTemperature(nextTemp){
    const clampedTemp = Math.max(16, Math.min(30, nextTemp));
    try {
      const response = await fetch('/api/automation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'set_temperature', device: 'climate', value: clampedTemp}),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Falha ao salvar temperatura.');
      renderClimateTemperature(result.target_c);
    } catch (error) {
      console.warn('Falha ao definir temperatura', error);
      if (window.JarvisToast) window.JarvisToast.show('Não foi possível salvar a temperatura.', 'error');
    }
  }

  fetch('/api/climate')
    .then(response => response.ok ? response.json() : Promise.reject(response))
    .then(result => { if (result.ok) renderClimateTemperature(result.target_c); })
    .catch(() => renderClimateTemperature(currentClimateTemp));

  const conversationsSidebar = document.getElementById('conversations-sidebar');
  const settingsBackButton = document.getElementById('settings-back-button');

  function getSessionCacheKey(sessionId){
    return `session_history_${sessionId}`;
  }

  function saveHistoryToLocal(sessionId, history){
    if(!sessionId || !Array.isArray(history)) return;
    try{ localStorage.setItem(getSessionCacheKey(sessionId), JSON.stringify(history)); }catch(e){ console.error('localStorage save failed', e); }
  }

  function loadHistoryFromLocal(sessionId){
    if(!sessionId) return null;
    try{
      const raw = localStorage.getItem(getSessionCacheKey(sessionId));
      return raw ? JSON.parse(raw) : null;
    }catch(e){ console.error('localStorage load failed', e); return null; }
  }

  function saveActiveScreen(screenName){
    try{ localStorage.setItem('active_screen', screenName); }catch(e){ console.error('localStorage save failed', e); }
  }

  function loadActiveScreen(){
    try{ return localStorage.getItem('active_screen'); }catch(e){ return null; }
  }

  function saveActiveSession(sessionId){
    try{ localStorage.setItem('active_session_id', sessionId); }catch(e){ console.error('localStorage save failed', e); }
  }

  function loadActiveSession(){
    try{ return localStorage.getItem('active_session_id'); }catch(e){ return null; }
  }

  // --- CARREGAR SESSÕES REAIS E DINÂMICAS ---
  async function refreshSessionList() {
    if (!sessionListContainer) return;
    try {
      const r = await fetch('/api/sessions');
      if (r.ok) {
        const j = await r.json();
        const sessions = j.sessions || [];
        
        sessionListContainer.innerHTML = '';
        if (sessions.length === 0) {
          sessionListContainer.innerHTML = '<div class="text-center text-on-surface-variant text-body-sm py-4">Nenhuma sessão ativa.</div>';
          // Limpa mensagens e reseta sessão atual quando não há sessões
          currentSession = null;
          if(messagesContainer){
            messagesContainer.innerHTML = '';
            const emptyState = document.createElement('div');
            emptyState.className = 'text-center text-on-surface-variant py-10';
            emptyState.innerHTML = '<p class="text-body-md font-body-md">Nenhuma conversa ativa. Clique em "Novo Chat" para começar.</p>';
            messagesContainer.appendChild(emptyState);
          }
          localStorage.removeItem('activeSession');
          return;
        }
        
        sessions.forEach(s => {
          const btn = document.createElement('button');
          btn.dataset.sessionId = s.id;
          btn.className = `session-button w-full text-left p-3 rounded-lg border border-white/5 hover:bg-white/5 hover:border-white/10 transition-all group focus:outline-none focus:ring-2 focus:ring-primary-fixed-dim focus:ring-offset-2 focus:ring-offset-surface ${s.id === currentSession ? 'bg-surface-container-highest border-primary-fixed-dim/30 active-session' : 'bg-transparent'}`;
          
          const lastMsg = s.history && s.history.length > 0 ? s.history[s.history.length - 1].content : 'Nenhuma mensagem recente.';
          const shortMsg = lastMsg.length > 50 ? lastMsg.slice(0, 50) + '...' : lastMsg;
          
          btn.innerHTML = `
            <div class="flex justify-between items-center mb-1">
              <span class="text-label-md font-label-md ${s.id === currentSession ? 'text-primary-fixed-dim font-bold' : 'text-on-surface group-hover:text-secondary-fixed-dim transition-colors'}">${escapeHtml(s.title || 'Sessão')}</span>
              <span class="text-label-sm font-label-sm text-on-surface-variant">Ativa</span>
            </div>
            <p class="text-body-sm font-body-sm text-on-surface-variant truncate">${escapeHtml(shortMsg)}</p>
          `;
          sessionListContainer.appendChild(btn);
        });
      }
    } catch(e) {
      console.error('Falha ao buscar sessões do backend', e);
    }
  }

  // --- MONITORAMENTO DE TELEMETRIA EM TEMPO REAL ---
  async function updateTelemetry() {
    try {
      const r = await fetch('/api/metrics');
      if (r.ok) {
        const d = await r.json();
        
        const cpuText = document.getElementById('statCpuText');
        const cpuBar = document.getElementById('statCpuBar');
        const ramText = document.getElementById('statRamText');
        const ramBar = document.getElementById('statRamBar');
        
        if (cpuText) cpuText.textContent = `${Math.round(d.cpu)}%`;
        if (cpuBar) cpuBar.style.width = `${d.cpu}%`;
        
        if (ramText) ramText.textContent = `${d.ram_used} GB / ${d.ram_total} GB`;
        if (ramBar) ramBar.style.width = `${d.ram_percent}%`;

        const elProvider = document.getElementById('telemetry-provider');
        const elRequests = document.getElementById('telemetry-requests');
        const elErrors = document.getElementById('telemetry-errors');
        const elUptime = document.getElementById('telemetry-uptime');
        if (elProvider && d.provider) elProvider.textContent = d.provider.toUpperCase();
        if (elRequests && d.total_requests !== undefined) elRequests.textContent = d.total_requests;
        if (elErrors && d.total_errors !== undefined) elErrors.textContent = d.total_errors;
        if (elUptime && d.uptime_seconds !== undefined) elUptime.textContent = `${d.uptime_seconds}s`;
      }
    } catch(e) {
      console.warn('Erro ao atualizar telemetria', e);
    }
  }

  async function fetchLogsAndTelemetry() {
    const logsContainer = document.getElementById('logs-container');
    const levelFilter = document.getElementById('log-level-filter')?.value || '';
    const searchInput = document.getElementById('log-search-input')?.value.toLowerCase() || '';

    try {
      const res = await fetch(`/api/logs${levelFilter ? `?level=${levelFilter}` : ''}`);
      if (res.ok) {
        const data = await res.json();
        const logs = data.logs || [];
        if (logsContainer) {
          const filtered = logs.filter(l => {
            if (!searchInput) return true;
            return (l.message || '').toLowerCase().includes(searchInput) ||
                   (l.component || '').toLowerCase().includes(searchInput);
          });

          if (filtered.length === 0) {
            logsContainer.innerHTML = '<div class="text-on-surface-variant text-center py-8">Nenhum log registrado ainda.</div>';
          } else {
            logsContainer.innerHTML = filtered.slice().reverse().map(l => {
              const badgeColor = l.level === 'ERROR' ? 'bg-error/20 text-error border-error/30' :
                                l.level === 'WARN' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                                'bg-primary-fixed-dim/20 text-primary-fixed-dim border-primary-fixed-dim/30';
              const timeStr = l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : '';
              return `
                <div class="flex items-start gap-2 p-2 rounded bg-surface-container/40 border border-white/5 hover:bg-white/5 transition-colors">
                  <span class="text-on-surface-variant text-[11px] shrink-0 font-mono">${timeStr}</span>
                  <span class="px-1.5 py-0.5 text-[10px] font-bold rounded border ${badgeColor} shrink-0">${l.level}</span>
                  <span class="text-secondary-fixed-dim font-bold text-[11px] shrink-0">[${escapeHtml(l.component || '')}]</span>
                  <span class="text-on-surface text-[12px] flex-1 font-mono break-all">${escapeHtml(l.message || '')}</span>
                </div>
              `;
            }).join('');
          }
        }
      }
    } catch (e) {
      console.error('Falha ao buscar logs', e);
    }
  }

  function initAutoTheme() {
    try {
      const themeMedia = window.matchMedia('(prefers-color-scheme: dark)');
      const applyTheme = (isDark) => {
        const stored = localStorage.getItem('jarvis_theme');
        const useDark = stored ? stored === 'dark' : isDark;
        if (useDark) {
          document.documentElement.classList.add('dark');
          document.documentElement.classList.remove('light');
        } else {
          document.documentElement.classList.remove('dark');
          document.documentElement.classList.add('light');
        }
      };
      applyTheme(themeMedia.matches);
      themeMedia.addEventListener('change', (e) => applyTheme(e.matches));
    } catch(e) {}
  }

  window.JarvisToast = {
    show(message, type = 'info', duration = 4000) {
      const container = document.getElementById('toast-container');
      if (!container) return;
      const toast = document.createElement('div');
      toast.className = `pointer-events-auto flex items-center gap-3 p-4 rounded-xl border backdrop-blur-md shadow-2xl transition-all duration-300 transform translate-y-4 opacity-0 ${
        type === 'error' ? 'bg-surface-container-high/95 border-error/50 text-error shadow-[0_0_20px_rgba(239,68,68,0.2)]' :
        type === 'success' ? 'bg-surface-container-high/95 border-primary-fixed-dim/40 text-primary-fixed-dim shadow-[0_0_20px_rgba(0,218,248,0.2)]' :
        'bg-surface-container-high/95 border-white/10 text-on-surface'
      }`;
      const iconName = type === 'error' ? 'warning' : type === 'success' ? 'check_circle' : 'info';
      toast.innerHTML = `
        <span class="material-symbols-outlined shrink-0 text-xl" style="font-variation-settings: 'FILL' 1;">${iconName}</span>
        <div class="flex-1 text-body-sm font-body-sm leading-tight">${escapeHtml(message)}</div>
        <button class="text-on-surface-variant hover:text-white transition-colors p-1" onclick="this.parentElement.remove()">
          <span class="material-symbols-outlined text-sm">close</span>
        </button>
      `;
      container.appendChild(toast);
      requestAnimationFrame(() => {
        toast.classList.remove('translate-y-4', 'opacity-0');
      });
      setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }
  };

  // --- CARREGAR HISTÓRICO DE CHAT ---
  async function loadSessionHistory(sessionId){
    if(!sessionId || !messagesContainer) return;

    const previousHeight = messagesContainer.getBoundingClientRect().height;
    messagesContainer.style.minHeight = `${Math.ceil(previousHeight)}px`;
    messagesContainer.style.overflow = 'hidden';
    messagesContainer.style.opacity = '0.9';

    let history = [];
    try{
      const r = await fetch(`/api/sessions/${sessionId}/history`);
      if(r.ok){
        const j = await r.json();
        history = j.history || j.messages || j.data || [];
      }
    }catch(e){
      console.error('failed load history', e);
    }
    if(history.length === 0){
      const localHistory = loadHistoryFromLocal(sessionId);
      if(Array.isArray(localHistory)) history = localHistory;
    }

    const fragment = document.createDocumentFragment();
    if(history.length === 0){
      const emptyState = document.createElement('div');
      emptyState.className = 'text-center text-on-surface-variant py-10';
      emptyState.textContent = 'Sem histórico de mensagens nesta sessão.';
      fragment.appendChild(emptyState);
    } else {
      history.forEach(m => {
        let contentHtml = '';
        if (m.role === 'assistant' && typeof marked !== 'undefined') {
          contentHtml = '<div class="markdown-body text-body-md font-body-md">' + marked.parse(m.content || m.text || '') + '</div>';
        } else {
          contentHtml = '<p>' + escapeHtml(m.content || m.text || '') + '</p>';
        }
        fragment.appendChild(createMessageElement(m.role || 'assistant', contentHtml));
      });
    }

    requestAnimationFrame(() => {
      messagesContainer.replaceChildren(fragment);
      messagesContainer.style.minHeight = '';
      messagesContainer.style.overflow = '';
      messagesContainer.style.opacity = '';
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
  }

  // --- TRANSIÇÕES E EFEITOS 3D DOS CARDS ---
  function setSectionCardDelays(screen){
    const cards = Array.from(screen.querySelectorAll('.screen-content > *, .screen-card-animated, .glass-card, .glass-surface'));
    const directions = ['from-left', 'from-right', 'from-bottom', 'from-top'];
    cards.forEach((card, index) => {
      const delay = Math.min(index * 45, 520);
      card.style.transitionDelay = `${delay}ms`;
      card.classList.remove('card-enter', 'from-left', 'from-right', 'from-top', 'from-bottom');
      void card.offsetWidth;
      card.classList.add('card-enter');
      card.classList.add(directions[index % directions.length]);
    });
  }

  function resetSectionCardDelays(screen){
    screen.querySelectorAll('.screen-content > *, .screen-card-animated, .glass-card, .glass-surface').forEach(card => {
      card.style.transitionDelay = '0ms';
      card.classList.remove('card-enter', 'from-left', 'from-right', 'from-top', 'from-bottom');
    });
  }

  function switchScreen(screenName){
    if (screenName !== 'study' && window.JarvisStudy?.onLeave) window.JarvisStudy.onLeave();
    screens.forEach(screen => {
      const isTarget = screen.id === `screen-${screenName}`;
      if(isTarget){
        resetSectionCardDelays(screen);
        setSectionCardDelays(screen);
        screen.classList.remove('hidden', 'screen-visible');
        screen.classList.add('screen-queued');
        screen.classList.remove('screen-visible');
        window.setTimeout(() => {
          screen.classList.remove('screen-queued');
          screen.classList.add('screen-visible');
        }, 180);
      } else {
        screen.classList.remove('screen-visible');
        screen.classList.remove('screen-queued');
        window.setTimeout(() => {
          if(screen.id !== `screen-${screenName}`){
            screen.classList.add('hidden');
          }
        }, 360);
      }
    });
    if(conversationsSidebar){
      conversationsSidebar.classList.toggle('hidden', screenName !== 'chat');
    }
    if (screenName === 'study' && window.JarvisStudy?.onEnter) {
      window.JarvisStudy.onEnter();
    }
  }

  // --- ATIVAR INTERATIVIDADE DE BOTÕES E TRAVAS ---
  document.querySelectorAll('#screen-area button:not(#chat-send-button):not(.nav-button):not(.session-button)').forEach(btn => {
    btn.classList.add('interactive-control');
  });

  document.querySelectorAll('.access-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const isLocked = btn.dataset.accessState === 'locked';
      btn.dataset.accessState = isLocked ? 'unlocked' : 'locked';
      btn.classList.toggle('locked', !isLocked);
      btn.classList.toggle('unlocked', isLocked);
      const icon = btn.querySelector('.material-symbols-outlined');
      const label = btn.querySelector('.status-label');
      if(icon){
        icon.textContent = isLocked ? 'lock_open' : 'lock';
      }
      if(label){
        label.textContent = isLocked ? 'Desbloqueado' : 'Bloqueado';
        label.className = `status-label text-label-sm font-label-sm ${isLocked ? 'text-error' : 'text-primary-fixed-dim'}`;
      }
      btn.classList.add('is-changing');
      window.setTimeout(() => btn.classList.remove('is-changing'), 220);
    });
  });

  // --- CÂMERA EM MODAL FULLSCREEN ---
  function getCameraImageSource(trigger){
    const section = trigger.closest('section');
    const sectionImage = section?.querySelector('img');
    if(sectionImage){
      return sectionImage.currentSrc || sectionImage.src || trigger.dataset.cameraImage || '';
    }
    return trigger.dataset.cameraImage || '';
  }

  function openCameraModal(title, imageSrc, description){
    if(cameraModalBackdrop && cameraModalImage && cameraModalTitle && cameraModalDescription){
      cameraModalTitle.textContent = title || 'Câmera de Segurança';
      cameraModalDescription.textContent = description || 'Transmissão em tempo real';
      cameraModalImage.src = imageSrc || '';
      cameraModalImage.alt = title || 'Transmissão da câmera';
      cameraModalBackdrop.classList.add('is-open');
      cameraModalBackdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('camera-modal-visible');
      document.documentElement.classList.add('camera-modal-visible');
    }
  }

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('.camera-open-btn');
    if(!trigger) return;
    event.preventDefault();
    event.stopPropagation();
    const sourceImage = getCameraImageSource(trigger);
    const previewTitle = trigger.dataset.cameraTitle || 'Câmera de Segurança';
    const previewDescription = trigger.dataset.cameraDescription || 'Transmissão ao vivo';
    openCameraModal(previewTitle, sourceImage, previewDescription);
  });

  const closeCameraModal = () => {
    cameraModalBackdrop?.classList.remove('is-open');
    cameraModalBackdrop?.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('camera-modal-visible');
    document.documentElement.classList.remove('camera-modal-visible');
  };

  cameraModalClose?.addEventListener('click', closeCameraModal);
  cameraModalBackdrop?.addEventListener('click', (event) => {
    if(event.target === cameraModalBackdrop) closeCameraModal();
  });
  document.addEventListener('keydown', (event) => {
    if(event.key === 'Escape') closeCameraModal();
  });

  // --- CONTROLE DE CLIMA ---
  document.querySelectorAll('#screen-automations button[data-temperature-step]').forEach(btn => {
    btn.addEventListener('click', () => {
      const step = Number(btn.dataset.temperatureStep || 1);
      setClimateTemperature(currentClimateTemp + step);
    });
  });

  // --- CONFIGURAÇÕES & EVENT LISTENERS ---
  if(settingsButton){
    settingsButton.addEventListener('click', event => {
      event.preventDefault();
      switchScreen('settings');
      saveActiveScreen('settings');
      setActiveNavButton(null);
    });
  }

  if(settingsBackButton){
    settingsBackButton.addEventListener('click', event => {
      event.preventDefault();
      switchScreen('dashboard');
      saveActiveScreen('dashboard');
      const dashboardBtn = navButtons.find(btn => btn.dataset.screen === 'dashboard');
      setActiveNavButton(dashboardBtn || null);
    });
  }

  navButtons.forEach(btn => {
    const target = btn.dataset.screen;
    if(!target) return;
    btn.addEventListener('click', event => {
      event.preventDefault();
      switchScreen(target);
      saveActiveScreen(target);
      setActiveNavButton(btn);
      if(target === 'chat') textarea?.focus();
    });
  });

  // Botão Novo Chat
  const newChatButton = document.getElementById('new-chat-button');
  if(newChatButton){
    newChatButton.addEventListener('click', async (event) => {
      event.preventDefault();
      await startNewChat(true); // true = criar nova sessão mesmo se estiver vazia
    });
  }

  // Botão de exportar chat
  const shareChatButton = document.getElementById('share-chat-button');
  if(shareChatButton){
    shareChatButton.addEventListener('click', async (event) => {
      event.preventDefault();
      if(!currentSession) return;
      
      try{
        const response = await fetch(`/api/sessions/${currentSession}/history`);
        const data = await response.json();
        const history = data.history || [];
        
        if(history.length === 0){
          alert('Este chat está vazio, não há nada para exportar.');
          return;
        }
        
        // Formata como Markdown
        let markdown = `# Chat Export\n\n`;
        markdown += `Data: ${new Date().toLocaleString('pt-BR')}\n\n`;
        markdown += `---\n\n`;
        
        history.forEach(msg => {
          const role = msg.role === 'user' ? '👤 Você' : '🤖 Jarvis';
          markdown += `## ${role}\n\n${msg.content}\n\n---\n\n`;
        });
        
        // Usa blob para download (funciona tanto em pywebview quanto navegador)
        const blob = new Blob([markdown], {type: 'text/markdown'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_${currentSession.slice(0, 8)}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }catch(e){
        console.error('Erro ao exportar chat', e);
        alert('Erro ao exportar chat');
      }
    });
  }

  // Botão de menu (3 pontinhos)
  const chatMenuButton = document.getElementById('chat-menu-button');
  if(chatMenuButton){
    chatMenuButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      if(!currentSession) return;
      
      // Cria menu dropdown
      const existingMenu = document.getElementById('chat-dropdown-menu');
      if(existingMenu) existingMenu.remove();
      
      const menu = document.createElement('div');
      menu.id = 'chat-dropdown-menu';
      menu.className = 'fixed bg-surface-container-high border border-white/10 rounded-lg shadow-xl z-[99999] min-w-[160px]';
      menu.style.pointerEvents = 'auto';
      menu.style.cursor = 'default';
      
      // Posiciona o menu
      const rect = chatMenuButton.getBoundingClientRect();
      menu.style.right = (window.innerWidth - rect.right) + 'px';
      menu.style.top = (rect.bottom + 8) + 'px';
      
      menu.innerHTML = `
        <button class="w-full px-4 py-2 text-left text-label-md font-label-md text-error hover:bg-error/10 transition-colors flex items-center gap-2 cursor-pointer" id="delete-chat-btn" style="pointer-events: auto; cursor: pointer;">
          <span class="material-symbols-outlined text-lg">delete</span>
          Excluir chat
        </button>
      `;
      
      document.body.appendChild(menu);
      
      // Deletar chat
      const deleteBtn = document.getElementById('delete-chat-btn');
      deleteBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        menu.remove();
        
        // Shift+click para excluir sem confirmação
        if(e.shiftKey){
          try{
            await fetch(`/api/sessions/${currentSession}`, {method: 'DELETE'});
            await refreshSessionList();
            await startNewChat();
          }catch(err){
            console.error('Erro ao deletar chat', err);
            alert('Erro ao deletar chat');
          }
          return;
        }
        
        // Popup de confirmação bonito
        showDeleteConfirmation();
      });
      
      // Fecha menu ao clicar fora (após um pequeno delay)
      setTimeout(() => {
        const closeMenu = (e) => {
          if(!menu.contains(e.target) && e.target !== chatMenuButton && !chatMenuButton.contains(e.target)){
            menu.remove();
            document.removeEventListener('click', closeMenu);
          }
        };
        document.addEventListener('click', closeMenu);
      }, 100);
    });
  }
  
  function showDeleteConfirmation(){
    // Cria modal de confirmação
    const existingModal = document.getElementById('delete-confirmation-modal');
    if(existingModal) existingModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'delete-confirmation-modal';
    modal.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm z-[99999] flex items-center justify-center';
    modal.style.pointerEvents = 'auto';
    
    modal.innerHTML = `
      <div class="bg-surface-container-high border border-white/10 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
        <div class="flex items-center gap-3 mb-4">
          <span class="material-symbols-outlined text-3xl text-error">warning</span>
          <h3 class="text-headline-md font-headline-md text-xl text-on-surface">Excluir chat</h3>
        </div>
        <p class="text-body-md font-body-md text-on-surface-variant mb-6">
          Tem certeza que deseja excluir este chat? Esta ação não pode ser desfeita.
        </p>
        <div class="flex gap-3 justify-end">
          <button id="cancel-delete-btn" class="px-4 py-2 rounded-lg text-label-md font-label-md text-on-surface-variant hover:bg-white/5 transition-colors">
            Cancelar
          </button>
          <button id="confirm-delete-btn" class="px-4 py-2 rounded-lg text-label-md font-label-md text-error bg-error/10 hover:bg-error/20 transition-colors">
            Excluir
          </button>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Event listeners
    document.getElementById('cancel-delete-btn').addEventListener('click', () => {
      modal.remove();
    });
    
    document.getElementById('confirm-delete-btn').addEventListener('click', async () => {
      modal.remove();
      try{
        await fetch(`/api/sessions/${currentSession}`, {method: 'DELETE'});
        await refreshSessionList();
        await startNewChat();
      }catch(err){
        console.error('Erro ao deletar chat', err);
        alert('Erro ao deletar chat');
      }
    });
    
    // Fecha ao clicar fora
    modal.addEventListener('click', (e) => {
      if(e.target === modal){
        modal.remove();
      }
    });
  }

  // Cliques em sessões com delegação dinâmica
  if(sessionListContainer) {
    sessionListContainer.addEventListener('click', async (event) => {
      const btn = event.target.closest('.session-button[data-session-id]');
      if(!btn) return;
      event.preventDefault();
      
      const sessionId = btn.dataset.sessionId;
      currentSession = sessionId || null;
      switchScreen('chat');
      saveActiveScreen('chat');
      saveActiveSession(currentSession);
      setActiveNavButton(navButtons.find(nav => nav.dataset.screen === 'chat'));
      
      // Atualiza destaque das sessões
      document.querySelectorAll('.session-button').forEach(sb => {
        const isActive = sb.dataset.sessionId === sessionId;
        sb.classList.toggle('bg-surface-container-highest', isActive);
        sb.classList.toggle('border-primary-fixed-dim/30', isActive);
        sb.classList.toggle('border-white/5', !isActive);
        sb.classList.toggle('bg-transparent', !isActive);
        sb.classList.toggle('active-session', isActive);
      });
      
      if(textarea) textarea.focus();
      if(currentSession) await loadSessionHistory(currentSession);
    });
  }

  // --- AUXILIARES E CHAT ENGINE ---
  function escapeHtml(str){
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function createMessageElement(role, html, persist = true, status = null, isError = false){
    const wrapper = document.createElement('div');
    wrapper.dataset.role = role;
    wrapper.dataset.persist = persist ? 'true' : 'false';
    wrapper.className = `chat-bubble-float ${role === 'user' ? 'flex gap-4 justify-end' : 'flex gap-4'}`;
    const content = document.createElement('div');
    if (isError) {
      content.className = 'bg-surface-container border-2 p-5 rounded-2xl rounded-tl-sm text-on-surface';
      content.style.cssText = 'border-color: #ef4444; box-shadow: 0 0 12px rgba(239,68,68,0.25);';
    } else {
      content.className = role === 'user' ? 'bg-surface-container-high border border-white/10 p-5 rounded-2xl rounded-tr-sm text-on-surface' : 'bg-surface-container border border-primary-fixed-dim/20 p-5 rounded-2xl rounded-tl-sm text-on-surface';
    }
    content.innerHTML = html;
    if(role === 'user' && status){
      const state = document.createElement('div');
      state.className = 'chat-sent-state';
      state.innerHTML = `<span class="material-symbols-outlined">check_circle</span><span>${status}</span>`;
      content.appendChild(state);
    }
    const avatar = document.createElement('div');
    avatar.className = 'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-6';
    if (isError) {
      avatar.innerHTML = `<span class="material-symbols-outlined" style="color:#ef4444; font-variation-settings: 'FILL' 1;">error</span>`;
    } else {
      avatar.innerHTML = `<span class="material-symbols-outlined ${role === 'user' ? 'text-secondary-fixed-dim' : 'text-primary-fixed-dim'}" style="font-variation-settings: 'FILL' 1;">${role === 'user' ? 'person' : 'smart_toy'}</span>`;
    }
    if(role === 'user'){
      wrapper.appendChild(content);
      wrapper.appendChild(avatar);
    } else {
      wrapper.appendChild(avatar);
      wrapper.appendChild(content);
    }
    return wrapper;
  }

  // Efeito suave de scroll
  function scrollMessagesToBottom(){
    if(!messagesContainer) return;
    const targetScroll = messagesContainer.scrollHeight;
    const startScroll = messagesContainer.scrollTop;
    const distance = targetScroll - startScroll;
    if(Math.abs(distance) < 2) return;
    const startTime = performance.now();
    const duration = 320;
    const step = (now) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      messagesContainer.scrollTop = startScroll + distance * eased;
      if(progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function appendMessage(role, html, persist = true, status = null){
    if(!messagesContainer) return;
    messagesContainer.appendChild(createMessageElement(role, html, persist, status));
    scrollMessagesToBottom();
  }

  function createPendingMessage(text){
    const wrapper = document.createElement('div');
    wrapper.className = 'flex gap-4 justify-end chat-bubble-float';
    wrapper.dataset.role = 'user';
    wrapper.dataset.persist = 'false';
    const content = document.createElement('div');
    content.className = 'bg-surface-container-high border border-white/10 p-5 rounded-2xl rounded-tr-sm text-on-surface';
    content.innerHTML = `<p class="text-body-md font-body-md">${escapeHtml(text)}</p><div class="mt-2 flex items-center gap-2 text-label-sm text-on-surface-variant"><span class="w-2 h-2 rounded-full bg-primary-fixed-dim chat-bubble-pulse"></span> Enviando…</div>`;
    const avatar = document.createElement('div');
    avatar.className = 'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-6';
    avatar.innerHTML = '<span class="material-symbols-outlined text-secondary-fixed-dim" style="font-variation-settings: \"FILL\" 1;">person</span>';
    wrapper.appendChild(content);
    wrapper.appendChild(avatar);
    return wrapper;
  }

  // Mensagem "Pensando" da IA - apenas 3 pontos animados
  function createThinkingMessage(progress = 0){
    const wrapper = document.createElement('div');
    wrapper.className = 'flex gap-4 chat-bubble-float';
    wrapper.dataset.role = 'assistant';
    wrapper.dataset.persist = 'false';
    const avatar = document.createElement('div');
    avatar.className = 'w-8 h-8 rounded-full bg-primary-fixed-dim/20 border border-primary-fixed-dim flex items-center justify-center flex-shrink-0 mt-6 shadow-[0_0_10px_rgba(0,218,248,0.2)]';
    avatar.innerHTML = '<span class="material-symbols-outlined text-primary-fixed-dim text-sm" style="font-variation-settings: \"FILL\" 1;">smart_toy</span>';
    const bubble = document.createElement('div');
    bubble.className = 'bg-surface-container border border-primary-fixed-dim/20 p-5 rounded-2xl rounded-tl-sm text-on-surface relative overflow-hidden';
    bubble.innerHTML = `
      <div class="chat-loader-dots" aria-label="Loading">
        <span class="chat-loader-dot"></span>
        <span class="chat-loader-dot"></span>
        <span class="chat-loader-dot"></span>
      </div>
    `;
    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    return wrapper;
  }

  function updateThinkingProgress(progress){
    // Não usado mais, mantido para compatibilidade
  }

  // Função para novo chat
  async function startNewChat(forceCreate = false){
    // Se não for forçado e a sessão atual estiver vazia, não cria nova
    if(!forceCreate && currentSession){
      try{
        const response = await fetch(`/api/sessions/${currentSession}/history`);
        const data = await response.json();
        const history = data.history || [];
        if(history.length === 0){
          // Sessão atual está vazia, não cria nova
          return;
        }
      }catch(e){
        console.error('Erro ao verificar histórico', e);
      }
    }
    
    currentSession = await createSession('Nova conversa');
    if(currentSession){
      saveActiveSession(currentSession);
      await refreshSessionList();
      
      // Limpa mensagens
      if(messagesContainer){
        messagesContainer.innerHTML = '';
        const emptyState = document.createElement('div');
        emptyState.className = 'text-center text-on-surface-variant py-10';
        emptyState.innerHTML = '<p class="text-body-md font-body-md">Nova conversa iniciada. Digite sua mensagem abaixo.</p>';
        messagesContainer.appendChild(emptyState);
      }
      
      // Atualiza destaque das sessões
      document.querySelectorAll('.session-button').forEach(sb => {
        const isActive = sb.dataset.sessionId === currentSession;
        sb.classList.toggle('bg-surface-container-highest', isActive);
        sb.classList.toggle('border-primary-fixed-dim/30', isActive);
        sb.classList.toggle('border-white/5', !isActive);
        sb.classList.toggle('bg-transparent', !isActive);
        sb.classList.toggle('active-session', isActive);
      });
      
      if(textarea) textarea.focus();
    }
  }

  function createDemoResponse(html, isError = false){
    return createMessageElement('assistant', html, true, null, isError);
  }

  async function createSession(title){
    try{
      const r = await fetch('/api/sessions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title})});
      const j = await r.json();
      return j.id;
    }catch(e){ console.error('failed create session', e); }
    return null;
  }

  async function saveHistory(){
    if(!currentSession || !messagesContainer) return;
    const msgs = [];
    const bubbles = messagesContainer.querySelectorAll('[data-role]');
    bubbles.forEach(b=>{
      if(b.dataset.persist === 'false') return;
      // Extrair apenas o texto da mensagem, removendo elementos de UI
      const textContent = b.textContent || b.innerText;
      // Remover elementos de UI como "Enviado", "Processamento concluído", etc.
      const cleanText = textContent
        .replace(/Enviado/g, '')
        .replace(/Processamento concluído/g, '')
        .replace(/\d+%/g, '')
        .replace(/Ver Ações/g, '')
        .replace(/Ver Ações \(\d+\)/g, '')
        .replace(/\(\d+\)/g, '')
        .replace(/check_circle/g, '')
        .replace(/person/g, '')
        .replace(/smart_toy/g, '')
        .replace(/✓/g, '')
        .replace(/C/g, '')
        .trim();
      if(cleanText){
        msgs.push({ role: b.dataset.role, content: cleanText });
      }
    });
    saveHistoryToLocal(currentSession, msgs);
    try{
      await fetch(`/api/sessions/${currentSession}/history`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({history: msgs})});
    }catch(e){ console.error('failed save history', e); }
  }

  // WebSocket connection for real-time streaming
  let chatSocket = null;
  let _wsRetryDelay = 3000;
  let _wsRetryTimer = null;
  function connectWebSocket() {
    if (chatSocket && chatSocket.readyState <= 1) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // WS server always runs on port 8001 (HTTP port 8000 + 1)
    // In pywebview mode window.location.port can be empty — so we hardcode 8001
    const wsHost = window.location.hostname || '127.0.0.1';
    const httpPort = parseInt(window.location.port || '8000', 10);
    const wsPort = httpPort > 0 ? httpPort + 1 : 8001;
    const wsUrl = `${protocol}//${wsHost}:${wsPort}/ws/chat`;
    chatSocket = new WebSocket(wsUrl);
    
    chatSocket.onopen = () => {
      console.log('Chat WebSocket connected');
      _wsRetryDelay = 3000; // reset backoff on success

    };
    
    chatSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };
    
    chatSocket.onclose = () => {
      console.log(`Chat WebSocket disconnected, retrying in ${_wsRetryDelay/1000}s...`);
      if (_wsRetryTimer) clearTimeout(_wsRetryTimer);
      _wsRetryTimer = setTimeout(() => {
        _wsRetryDelay = Math.min(_wsRetryDelay * 2, 30000); // max 30s backoff
        connectWebSocket();
      }, _wsRetryDelay);
    };
    
    chatSocket.onerror = () => {
      // silent — onclose will handle retry
    };
  }
  
  // Connect once on load
  connectWebSocket();

  function handleWebSocketMessage(j) {
    if(!messagesContainer) return;

    if(j.type === 'status' && j.status === 'thinking') {
      if (window.JarvisOrb) window.JarvisOrb.setState('thinking');
      return;
    }

    // Fase 6: Wake Word detectada — abre microfone automaticamente
    if(j.type === 'wake_word') {
      if (window.JarvisOrb) window.JarvisOrb.setState('listening');
      window.JarvisToast?.show('🎤 "Ei Jarvis" detectado — ouvindo…', 'info');
      // Aciona o botão de microfone se disponível
      const micBtnEl = document.getElementById('chat-mic-button');
      if (micBtnEl && !micBtnEl.classList.contains('recording-active')) {
        micBtnEl.click();
      }
      return;
    }

    if(j.type === 'chunk') {
      const thinking = messagesContainer.querySelector('[data-role="assistant"][data-persist="false"]');
      if (thinking) {
        // Find or create the text container
        let markdownBody = thinking.querySelector('.markdown-body');
        if (!markdownBody) {
          // Replace loader dots with text container
          const bubble = thinking.querySelector('.bg-surface-container');
          if (bubble) {
            bubble.innerHTML = '<div class="markdown-body text-body-md font-body-md"></div>';
            markdownBody = bubble.querySelector('.markdown-body');
          }
        }
        
        if (markdownBody) {
          // Store raw chunks, parse markdown safely if completed
          // To keep it simple, just accumulate plain text during stream then marked on complete
          // Wait, doing marked on every chunk is safe but can be jittery. Let's do it on every chunk for nice UI.
          if (!thinking.dataset.rawContent) thinking.dataset.rawContent = '';
          thinking.dataset.rawContent += j.text;
          
          if (typeof marked !== 'undefined') {
            markdownBody.innerHTML = marked.parse(thinking.dataset.rawContent);
          } else {
            markdownBody.innerHTML = escapeHtml(thinking.dataset.rawContent).replace(/\n/g, '<br>');
          }
        }
      }
      scrollMessagesToBottom();
      return;
    }

    if(j.type === 'complete' || j.type === 'error') {
      const pending = messagesContainer.querySelector('[data-role="user"][data-persist="false"]');
      const thinking = messagesContainer.querySelector('[data-role="assistant"][data-persist="false"]');
      if(pending) pending.dataset.persist = "true";
      if(thinking) thinking.remove();
      
      let responseHtml;
      const summaryText = j.summary || j.intent || '';

      // Detecta solicitação de execução de script (Fase 5)
      const SCRIPT_MARKER = '__SCRIPT_CONFIRM__';
      if (summaryText.includes(SCRIPT_MARKER)) {
        const jsonStart = summaryText.indexOf(SCRIPT_MARKER) + SCRIPT_MARKER.length;
        const jsonStr = summaryText.slice(jsonStart).trim();
        try {
          const scriptPayload = JSON.parse(jsonStr);
          if (window.JarvisScriptRunner) {
            window.JarvisScriptRunner.openModal(scriptPayload);
          }
          const confirmHtml = `<p class="text-body-md font-body-md text-on-surface-variant">🔐 Aguardando sua confirmação para executar o script…</p>`;
          messagesContainer.appendChild(createDemoResponse(confirmHtml, false));
          scrollMessagesToBottom();
          return;
        } catch(e) { /* parse failed — cai para o comportamento normal */ }
      }

      // ── Jarvis Cinema: Detecta contexto de tool_results vindo do backend ou marcador __CINEMA_PLAY__ ──
      const CINEMA_MARKER = '__CINEMA_PLAY__';

      // Primeiro, verifica se o backend retornou o player via context.tool_results.cinema
      let handledCinema = false;
      try {
        const cinemaCtx = (j.context && j.context.tool_results && j.context.tool_results.cinema) || (j.context && j.context.tool_results && j.context.tool_results['cinema']);
        const cinemaData = cinemaCtx && cinemaCtx.data ? cinemaCtx.data : null;
        if (cinemaData) {
          const isValidCinema = (cinemaData.imdb_id || cinemaData.detect_url || Array.isArray(cinemaData.discovery_results) || Array.isArray(cinemaData.catalog_results)) && cinemaData.ok !== false;
          if (isValidCinema) {
            if (window.JarvisCinema?.play) {
              if (cinemaData.detect_url && window.JarvisCinema.detectUrl) {
                window.JarvisCinema.detectUrl(cinemaData.detect_url, cinemaData.title);
              } else {
                window.JarvisCinema.play(cinemaData);
              }
              handledCinema = true;
            }
          } else {
            console.warn('Cinema context recebido sem dados válidos, ignorando', cinemaData);
          }
        }
      } catch(e) {
        console.warn('Erro ao processar cinema context:', e);
      }

      if (!handledCinema) {
        const cinemaMarkerIndex = summaryText.indexOf(CINEMA_MARKER);
        if (cinemaMarkerIndex >= 0) {
        const jsonStart = cinemaMarkerIndex + CINEMA_MARKER.length;
        const jsonStr = summaryText.slice(jsonStart).trim();
        try {
          const cinemaPayload = JSON.parse(jsonStr);
          const isValidCinema = (cinemaPayload.imdb_id || cinemaPayload.detect_url || Array.isArray(cinemaPayload.discovery_results) || Array.isArray(cinemaPayload.catalog_results)) && cinemaPayload.ok !== false;
          if (!isValidCinema) {
            console.warn('Payload de cinema recebido sem dados válidos, ignorando', cinemaPayload);
          } else {
            if (window.JarvisCinema?.play) {
              if (cinemaPayload.detect_url && window.JarvisCinema.detectUrl) {
                window.JarvisCinema.detectUrl(cinemaPayload.detect_url, cinemaPayload.title);
              } else {
                window.JarvisCinema.play(cinemaPayload);
              }
            } else {
              console.warn('JarvisCinema não disponível');
            }
          }
          const isTv = cinemaPayload.type === 'tv';
          const epStr = isTv ? ` (T${cinemaPayload.season || 1}:E${cinemaPayload.episode || 1})` : '';
          const cinemaHtml = `
            <div class="flex items-center gap-3 p-3 rounded-xl border border-primary-fixed-dim/20 bg-primary-fixed-dim/5">
              <span class="material-symbols-outlined text-primary-fixed-dim text-2xl" style="font-variation-settings:'FILL' 1;">movie</span>
              <div>
                <p class="text-sm font-semibold text-white">🎬 Jarvis Cinema</p>
                <p class="text-xs text-on-surface-variant">Selecionado: <span class="text-primary-fixed-dim font-bold">${cinemaPayload.title || ''}${epStr}</span></p>
                <p class="text-[11px] text-on-surface-variant/60 mt-0.5">Trailer e disponibilidade oficial abertos</p>
              </div>
            </div>`;
          messagesContainer.appendChild(createDemoResponse(cinemaHtml, false));
          scrollMessagesToBottom();
          const speakText = `Abrindo ${cinemaPayload.title || 'o conteúdo'}${epStr} no Jarvis Cinema.`;
          if (window.JarvisVoice?.speak) window.JarvisVoice.speak(speakText);
          if (window.JarvisOrb) { window.JarvisOrb.setState('speaking'); setTimeout(() => window.JarvisOrb.setState('idle'), 3000); }
          saveHistory();
          refreshSessionList();
          return;
        } catch(e) {
          console.warn('Falha ao parsear payload de cinema', e);
        }
      }

      }

      // Detecta se o summary é na verdade uma mensagem de erro (vinda do orquestrador)
      const isOrchestratorError = j.type === 'complete' && (
        summaryText.startsWith('Erro ao processar') ||
        summaryText.startsWith('Erro de autenticação') ||
        summaryText.startsWith('Limite de taxa') ||
        summaryText.startsWith('Timeout') ||
        summaryText.startsWith('Falha na conexão') ||
        summaryText.startsWith('Chave') ||
        /Error code:\s*\d+/.test(summaryText)
      );
      if(j.type === 'complete' && !isOrchestratorError){
        const hasActions = j.actions && j.actions.length > 0;
        let contentHtml = '';
        let imageHtml = '';
        let cleanText = summaryText;

        const visionMatch = summaryText.match(/\[Visão Computacional - Captura:\s*([^\]]+)\]/);
        if (visionMatch) {
          const capFile = visionMatch[1].trim();
          imageHtml = `<div class="mb-3 rounded-lg overflow-hidden border border-white/10 max-w-sm shadow-md"><img src="/api/vision/file/${capFile}" alt="Captura Visual" class="w-full h-auto object-cover"/></div>`;
          cleanText = summaryText.replace(visionMatch[0], '').trim();
        }

        if (typeof marked !== 'undefined') {
          contentHtml = imageHtml + '<div class="markdown-body text-body-md font-body-md space-y-2">' + marked.parse(cleanText || 'Resposta do Jarvis pronta.') + '</div>';
        } else {
          contentHtml = imageHtml + '<p class="text-body-md font-body-md">' + escapeHtml(cleanText || 'Resposta do Jarvis pronta.') + '</p>';
        }
        responseHtml = `<div class="space-y-3">${contentHtml}${hasActions ? `<div class="rounded-xl border border-white/10 bg-surface-container-lowest/70 p-3"><div class="flex items-center justify-between text-label-sm font-label-sm text-on-surface-variant mb-2"><span>Processamento concluído</span><span>100%</span></div><div class="chat-progress mt-2"><span style="width: 100%;"></span></div></div><div class="flex gap-2 mt-3"><button class="chat-action-btn px-3 py-1.5 rounded border border-white/10 bg-surface-container-high text-label-md font-label-md text-on-surface">Ver Ações (${j.actions.length})</button></div>` : ''}</div>`;
      } else if(j.type === 'error' || isOrchestratorError){
        const errText = isOrchestratorError ? summaryText : (j.message || 'Erro desconhecido');
        responseHtml = `<p class="text-body-md font-body-md text-error">⚠️ ${escapeHtml(errText)}</p>`;
      }
      
      const isErrorMsg = j.type === 'error' || isOrchestratorError;
      messagesContainer.appendChild(createDemoResponse(responseHtml, isErrorMsg));
      scrollMessagesToBottom();

      if (isErrorMsg) {
        const errText = isOrchestratorError ? summaryText : (j.message || 'Erro desconhecido');
        window.JarvisToast?.show(errText, 'error');
      } else if (j.actions && j.actions.length > 0) {
        window.JarvisToast?.show(`Ação concluída: ${j.actions.join(', ')}`, 'success');
      }
      
      if (window.JarvisOrb) {
        if(!isErrorMsg && j.type === 'complete'){
          window.JarvisOrb.setState('speaking');
          // Strip any [tool:...] markers before speaking
          const speakText = (j.summary || '').replace(/\[tool:[^\]]+\]/g, '').trim();
          // Só fala se não for mensagem de erro (erros não devem ser lidos pela voz)
          if (speakText && window.JarvisVoice?.speak) window.JarvisVoice.speak(speakText);
          setTimeout(() => {
            if (window.JarvisOrb) window.JarvisOrb.setState('idle');
          }, 4000);
        } else if(isErrorMsg){
          // Erros: apenas muda o estado visual da orb — NÃO fala nada
          window.JarvisOrb.setState('error');
          setTimeout(() => {
            if (window.JarvisOrb) window.JarvisOrb.setState('idle');
          }, 3000);
        }
      }

      saveHistory();
      refreshSessionList();
    }
  }

  // Fim do handler de WebSocket / fallback HTTP
  
  async function send(){
    const text = textarea?.value.trim() || '';
    if(!text) return;
    if(textarea) textarea.value = '';
    if(textarea) textarea.style.height = '44px';

    if(!currentSession){
      currentSession = await createSession(text.slice(0,32) || 'Nova sessão');
      if(currentSession){
        saveActiveSession(currentSession);
        await refreshSessionList();
      }
    }

    if(messagesContainer){
      appendMessage('user', '<p>' + escapeHtml(text) + '</p>', true, 'Enviado');
      // No longer need createPendingMessage if we don't want to fake it, 
      // but let's keep the loader message from assistant.
      messagesContainer.appendChild(createThinkingMessage(10));
      scrollMessagesToBottom();
    }

    if (window.JarvisOrb) {
      window.JarvisOrb.setState('thinking');
    }

    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
      // Fallback to fetch if WS is not ready
      console.warn("WebSocket not ready, using HTTP fallback");
      try{
        const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text, session_id: currentSession, mode: 'general'})});
        const j = await r.json();
        handleWebSocketMessage({
          type: j.status === 'error' ? 'error' : 'complete',
          summary: j.summary,
          intent: j.intent,
          actions: j.actions,
          message: j.summary
        });
      }catch(err){
        handleWebSocketMessage({type: 'error', message: err.message});
      }
      return;
    }

    // Send via WebSocket
    chatSocket.send(JSON.stringify({
      message: text,
      session_id: currentSession,
      mode: 'general'
    }));
  }

  sendBtn?.addEventListener('click', send);
  textarea?.addEventListener('keydown', function(e){ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(); } });

  const visionBtn = document.getElementById('chat-vision-button');
  if (visionBtn) {
    visionBtn.addEventListener('click', async () => {
      const promptText = textarea?.value?.trim() || "Analise o conteúdo visual da minha tela em detalhes.";
      if (window.JarvisToast) window.JarvisToast.show("📷 Capturando tela para análise visual...", "info");
      if (window.JarvisOrb) window.JarvisOrb.setState("thinking");

      // Adiciona mensagem do usuário no container
      appendUserMessage(`👁️ [Análise de Tela] ${promptText}`);
      if (textarea) textarea.value = '';

      const assistantEl = createDemoResponse('<p class="text-body-md font-body-md text-on-surface-variant">📷 Capturando e analisando visualmente...</p>', false);
      messagesContainer.appendChild(assistantEl);
      scrollMessagesToBottom();

      try {
        const res = await fetch('/api/vision/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'analyze_screen', prompt: promptText })
        });
        const data = await res.json();
        if (!data.ok) {
          assistantEl.querySelector('.markdown-body').innerHTML = `<p class="text-error">⚠️ ${data.error || 'Falha na captura'}</p>`;
          if (window.JarvisOrb) window.JarvisOrb.setState("idle");
          return;
        }

        let imgTag = '';
        if (data.capture_url) {
          imgTag = `<div class="mb-3 rounded-lg overflow-hidden border border-white/10 max-w-sm shadow-md"><img src="${data.capture_url}" alt="Captura Visual" class="w-full h-auto object-cover"/></div>`;
        }
        let replyHtml = imgTag + (typeof marked !== 'undefined' ? marked.parse(data.reply || '') : escapeHtml(data.reply || ''));
        assistantEl.querySelector('.markdown-body').innerHTML = replyHtml;

        if (window.JarvisOrb) window.JarvisOrb.setState("idle");
        scrollMessagesToBottom();
      } catch (err) {
        assistantEl.querySelector('.markdown-body').innerHTML = `<p class="text-error">⚠️ Erro ao conectar com o serviço de visão: ${err.message}</p>`;
        if (window.JarvisOrb) window.JarvisOrb.setState("idle");
      }
    });
  }

  if (micBtn && window.JarvisVoice) {
    let recordingPromise = null;
    let isRecordingActive = false;
    let pressStartTime = 0;

    const micIcon = micBtn.querySelector('.material-symbols-outlined');

    function setMicRecordingState(active) {
      isRecordingActive = active;
      if (active) {
        micBtn.classList.add('bg-red-500/20', 'text-red-400', 'border', 'border-red-500/40', 'animate-pulse');
        micBtn.classList.remove('text-on-surface-variant');
        micBtn.title = "Gravando... Clique para parar e enviar";
        if (micIcon) micIcon.textContent = 'stop';
      } else {
        micBtn.classList.remove('bg-red-500/20', 'text-red-400', 'border', 'border-red-500/40', 'animate-pulse');
        micBtn.classList.add('text-on-surface-variant');
        micBtn.title = "Falar (Clique para gravar)";
        if (micIcon) micIcon.textContent = 'mic';
      }
    }

    async function stopAndProcessRecording() {
      if (!isRecordingActive) return;
      setMicRecordingState(false);
      window.JarvisVoice.stopRecording();
      if (recordingPromise) {
        const text = await recordingPromise;
        recordingPromise = null;
        if (text && textarea) {
          textarea.value = text;
          await send();
        } else if (window.JarvisOrb) {
          window.JarvisOrb.setState('idle');
        }
      }
    }

    async function startMicRecording() {
      if (isRecordingActive) return;
      setMicRecordingState(true);
      recordingPromise = window.JarvisVoice.startRecording();
    }

    micBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      // Se foi um clique rápido (não um hold longo), alterna o estado
      const heldDuration = Date.now() - pressStartTime;
      if (heldDuration < 300) {
        if (isRecordingActive) {
          await stopAndProcessRecording();
        } else {
          await startMicRecording();
        }
      }
    });

    micBtn.addEventListener('pointerdown', (e) => {
      pressStartTime = Date.now();
    });

    micBtn.addEventListener('pointerup', async () => {
      const heldDuration = Date.now() - pressStartTime;
      // Se segurou por mais de 300ms, soltar o botão encerra e envia a gravação
      if (heldDuration >= 300 && isRecordingActive) {
        await stopAndProcessRecording();
      }
    });
  }

  const speakToggle = document.getElementById('setting-speak-responses');
  if (speakToggle && window.JarvisVoice) {
    speakToggle.checked = window.JarvisVoice.getSpeakEnabled();
    speakToggle.addEventListener('change', () => {
      window.JarvisVoice.setSpeakEnabled(speakToggle.checked);
    });
  }

  const llmProviderSelect = document.getElementById('setting-llm-provider');
  const llmStatusEl = document.getElementById('setting-llm-status');

  function updateLlmStatus(data) {
    if (!llmStatusEl || !data) return;
    const provider = data.llm_provider === 'groq' ? 'Groq (Llama)' : 'Gemini';
    const configured = data.llm_provider === 'groq' ? data.groq_configured : data.gemini_configured;
    llmStatusEl.textContent = configured
      ? `Ativo: ${provider} — chave configurada`
      : `Ativo: ${provider} — configure a chave no .env`;
  }

  async function loadLlmSettings() {
    if (!llmProviderSelect) return;
    try {
      const r = await fetch('/api/settings/llm');
      if (!r.ok) return;
      const data = await r.json();
      llmProviderSelect.value = data.llm_provider || 'gemini';
      updateLlmStatus(data);
    } catch (e) {
      console.warn('Falha ao carregar config LLM', e);
    }
  }

  if (llmProviderSelect) {
    llmProviderSelect.addEventListener('change', async () => {
      try {
        const r = await fetch('/api/settings/llm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ llm_provider: llmProviderSelect.value }),
        });
        const data = await r.json();
        if (!r.ok) {
          alert(data.error || 'Não foi possível alterar o provedor LLM.');
          await loadLlmSettings();
          return;
        }
        updateLlmStatus(data);
      } catch (e) {
        alert('Erro ao salvar provedor LLM.');
        await loadLlmSettings();
      }
    });
    loadLlmSettings();
  }

  // --- FASE 7: MEMÓRIAS SEMÂNTICAS ---
  window.currentMemCollection = 'conversations';
  window.loadMemories = async function(collection) {
    if (collection) window.currentMemCollection = collection;
    const col = window.currentMemCollection;
    const btnConvo = document.getElementById('mem-col-conversations');
    const btnUser = document.getElementById('mem-col-user_memory');
    if (btnConvo && btnUser) {
      if (col === 'conversations') {
        btnConvo.className = "px-3 py-1 rounded-lg text-xs font-medium bg-violet-500/20 border border-violet-500/30 text-violet-300 hover:bg-violet-500/30 transition-all";
        btnUser.className = "px-3 py-1 rounded-lg text-xs font-medium bg-surface-container/60 border border-white/10 text-white/50 hover:bg-white/10 transition-all";
      } else {
        btnUser.className = "px-3 py-1 rounded-lg text-xs font-medium bg-violet-500/20 border border-violet-500/30 text-violet-300 hover:bg-violet-500/30 transition-all";
        btnConvo.className = "px-3 py-1 rounded-lg text-xs font-medium bg-surface-container/60 border border-white/10 text-white/50 hover:bg-white/10 transition-all";
      }
    }
    const container = document.getElementById('memories-container');
    if (!container) return;
    try {
      const res = await fetch(`/api/memories?collection=${col}&limit=25`);
      const data = await res.json();
      if (!data.memories || data.memories.length === 0) {
        container.innerHTML = '<div class="text-on-surface-variant text-center py-6 text-sm">Nenhuma memória encontrada nesta coleção.</div>';
        return;
      }
      container.innerHTML = data.memories.map(m => `
        <div class="p-2.5 rounded-lg border border-white/5 bg-white/[0.02] text-xs text-white/80 space-y-1">
          <div class="font-mono text-green-300/90 whitespace-pre-wrap">${escapeHtml(m.text)}</div>
          ${m.metadata && m.metadata.timestamp ? `<div class="text-[10px] text-white/40">${new Date(m.metadata.timestamp * 1000).toLocaleString('pt-BR')}</div>` : ''}
        </div>
      `).join('');
    } catch(e) {
      container.innerHTML = '<div class="text-error text-center py-6 text-sm">Erro ao carregar memórias.</div>';
    }
  };

  // --- FASE 6: WAKE WORD SETTING ---
  const wakeWordCheckbox = document.getElementById('setting-wake-word');
  const wakeWordStatus = document.getElementById('setting-wake-word-status');

  async function loadWakeWordSetting() {
    if (!wakeWordCheckbox) return;
    try {
      const r = await fetch('/api/wake-word');
      const data = await r.json();
      wakeWordCheckbox.checked = !!data.enabled;
      if (wakeWordStatus) {
        wakeWordStatus.textContent = data.available
          ? (data.enabled ? '🟢 Ativo (ouvindo "Ei Jarvis")' : '⏸️ Pausado')
          : '⚠️ Indisponível (instale: vosk pyaudio)';
      }
    } catch (e) {}
  }

  if (wakeWordCheckbox) {
    wakeWordCheckbox.addEventListener('change', async () => {
      try {
        const r = await fetch('/api/wake-word', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: wakeWordCheckbox.checked })
        });
        const data = await r.json();
        if (wakeWordStatus) {
          wakeWordStatus.textContent = data.enabled ? '🟢 Ativo (ouvindo "Ei Jarvis")' : '⏸️ Pausado';
        }
        window.JarvisToast?.show(data.enabled ? '🎤 Wake Word ativado' : '⏸️ Wake Word pausado', 'info');
      } catch (e) {
        window.JarvisToast?.show('Erro ao alterar Wake Word', 'error');
      }
    });
  }

  // --- INICIALIZAÇÃO ---
  async function initApp() {
    await refreshSessionList();
    loadWakeWordSetting();
    window.loadMemories('conversations');
    
    // Iniciar polling de telemetria de CPU e RAM
    initAutoTheme();
    updateTelemetry();
    setInterval(updateTelemetry, 3000);
    
    // Logs polling & listeners
    fetchLogsAndTelemetry();
    setInterval(fetchLogsAndTelemetry, 4000);

    document.getElementById('log-refresh-btn')?.addEventListener('click', fetchLogsAndTelemetry);
    document.getElementById('log-level-filter')?.addEventListener('change', fetchLogsAndTelemetry);
    document.getElementById('log-search-input')?.addEventListener('input', fetchLogsAndTelemetry);
    
    const restoredSession = loadActiveSession();
    const restoredScreen = loadActiveScreen();
    
    if(restoredSession){
      currentSession = restoredSession;
      const sessionButtons = Array.from(document.querySelectorAll('.session-button'));
      const sessionButton = sessionButtons.find(btn => btn.dataset.sessionId === restoredSession);
      if(sessionButton){
        sessionButton.classList.add('bg-surface-container-highest', 'border-primary-fixed-dim/30', 'active-session');
        if(restoredScreen !== 'settings'){
          switchScreen('chat');
          setActiveNavButton(navButtons.find(b => b.dataset.screen === 'chat'));
          loadSessionHistory(currentSession);
        }
      }
    }

    const defaultNavButton = navButtons.find(b => b.dataset.screen === 'chat') || navButtons[0];
    if(restoredScreen === 'settings'){
      switchScreen('settings');
      setActiveNavButton(null);
    } else if(restoredScreen && restoredScreen !== 'settings'){
      const button = navButtons.find(b => b.dataset.screen === restoredScreen);
      if(button){
        switchScreen(restoredScreen);
        setActiveNavButton(button);
      } else {
        switchScreen('chat');
        setActiveNavButton(defaultNavButton);
      }
    } else {
      switchScreen('chat');
      setActiveNavButton(defaultNavButton);
    }

    textarea?.focus();
  }

  initApp();

  // Exporta API pública para outros scripts (live_call.js, etc.)
  window.JarvisPanel = {
    getSession: () => currentSession,
    appendMessage,
    scrollToBottom: scrollMessagesToBottom,
    sendMessage: async (text) => {
      if (!text || !currentSession) return;
      const pendingMsg = createPendingMessage(text);
      messagesContainer?.appendChild(pendingMsg);
      scrollMessagesToBottom();
      // Envio real via WebSocket — reutiliza o socket existente
      if (chatSocket && chatSocket.readyState === 1) {
        chatSocket.send(JSON.stringify({ message: text, session_id: currentSession, mode: 'general' }));
      }
    },
  };
})();
