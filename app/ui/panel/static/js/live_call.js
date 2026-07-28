// ─────────────────────────────────────────────────────────────────────────────
// JarvisLiveCall — Modo Ligação / Hands-Free Voice Call
// Detecta fala via Web Audio API, transcreve via Groq Whisper (STT),
// envia ao Jarvis e sintetiza a resposta com TTS — tudo em loop automático.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
  const overlay       = document.getElementById('live-call-overlay');
  const callStatus    = document.getElementById('live-call-status');
  const callOrb       = document.getElementById('live-call-orb');
  const endButton     = document.getElementById('live-call-end-button');
  const liveCallBtn   = document.getElementById('chat-live-call-button');
  const bars          = document.querySelectorAll('.live-call-bar');

  const headerLiveCallBtn = document.getElementById('header-live-call-button');

  if (!overlay) return;

  let _running = false;
  let _audioCtx = null;
  let _analyser = null;
  let _animFrame = null;
  let _mediaRecorder = null;
  let _stream = null;
  let _silenceTimer = null;
  let _chunks = [];
  let _currentAudio = null;
  let _hasSpeechActivity = false;

  // ── Estado visual ──────────────────────────────────────────────────────────
  const STATES = {
    listening: {
      status: 'Ouvindo...',
      orbColor: 'rgba(0,218,248,0.3)',
      orbBorder: 'rgba(0,218,248,0.5)',
      orbShadow: '0 0 40px rgba(0,218,248,0.3), 0 0 80px rgba(0,218,248,0.1)',
    },
    processing: {
      status: 'Processando...',
      orbColor: 'rgba(163,147,255,0.3)',
      orbBorder: 'rgba(163,147,255,0.5)',
      orbShadow: '0 0 40px rgba(163,147,255,0.4), 0 0 80px rgba(163,147,255,0.15)',
    },
    speaking: {
      status: 'Jarvis falando...',
      orbColor: 'rgba(0,255,163,0.3)',
      orbBorder: 'rgba(0,255,163,0.6)',
      orbShadow: '0 0 50px rgba(0,255,163,0.4), 0 0 100px rgba(0,255,163,0.2)',
    },
  };

  function setCallState(state) {
    const s = STATES[state] || STATES.listening;
    if (callStatus) callStatus.textContent = s.status;
    if (callOrb) {
      callOrb.style.background =
        `radial-gradient(circle at 35% 35%, ${s.orbColor}, rgba(0,0,0,0.05))`;
      callOrb.style.borderColor = s.orbBorder;
      callOrb.style.boxShadow = s.orbShadow;
    }
  }

  // ── Animação de forma de onda ──────────────────────────────────────────────
  function animateBars(analyser) {
    if (!analyser || !_running) return;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    function loop() {
      if (!_running) { bars.forEach(b => (b.style.height = '4px')); return; }
      analyser.getByteFrequencyData(buf);
      const step = Math.floor(buf.length / bars.length);
      bars.forEach((bar, i) => {
        const val = buf[i * step] || 0;
        const h = Math.max(4, Math.round((val / 255) * 36));
        bar.style.height = h + 'px';
      });
      _animFrame = requestAnimationFrame(loop);
    }
    loop();
  }

  function stopCurrentAudio() {
    if (_currentAudio) {
      try {
        _currentAudio.pause();
        _currentAudio.currentTime = 0;
      } catch (_) {}
      _currentAudio = null;
    }
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }
  }

  // ── Enviar mensagem ao chat e esperar resposta ─────────────────────────────
  async function sendMessageAndSpeak(text) {
    if (!text || !_running) return startListening();

    // Valida se o texto contém letras reais (ignora ruídos como ".", "hmm", "...")
    const cleanInputLetters = (text || '').replace(/[^a-zA-ZáàâãéèêíïóôõöúçñÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ0-9]/g, '');
    if (cleanInputLetters.length < 2) {
      if (_running) startListening();
      return;
    }

    setCallState('processing');

    // Injeta visualmente no painel de chat (se disponível)
    if (window.JarvisPanel?.sendMessage) {
      window.JarvisPanel.sendMessage(text);
    }

    let reply = '';
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: window.JarvisPanel?.getSession?.() }),
      });
      if (res.ok) {
        const j = await res.json();
        reply = j.summary || j.reply || j.intent || '';
      }
    } catch (err) {
      console.error('[LiveCall] Erro na comunicação com Jarvis:', err);
    }

    // Remove marcadores como [tool:...] antes da voz
    const cleanReply = reply.replace(/\[tool:[^\]]+\]/g, '').trim();

    if (!cleanReply || !_running) {
      if (_running) startListening();
      return;
    }

    setCallState('speaking');

    // Síntese e reprodução da resposta via TTS
    try {
      const r = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanReply }),
      });
      if (r.ok && _running) {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        stopCurrentAudio();

        _currentAudio = new Audio(url);
        _currentAudio.onended = () => {
          URL.revokeObjectURL(url);
          _currentAudio = null;
          if (_running) startListening();
        };
        _currentAudio.onerror = () => {
          _currentAudio = null;
          if (_running) startListening();
        };
        await _currentAudio.play();
        return;
      }
    } catch (e) {
      console.error('[LiveCall] Erro no TTS:', e);
    }

    if (_running) startListening();
  }

  // ── Ciclo de escuta ────────────────────────────────────────────────────────
  function startListening() {
    if (!_running || !_stream) return;

    setCallState('listening');
    _chunks = [];
    _hasSpeechActivity = false;

    const options = MediaRecorder.isTypeSupported('audio/webm')
      ? { mimeType: 'audio/webm' } : {};
    _mediaRecorder = new MediaRecorder(_stream, options);

    _mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) _chunks.push(e.data);
    };

    _mediaRecorder.onstop = async () => {
      if (!_running) return;
      const blob = new Blob(_chunks, { type: 'audio/webm' });
      
      // Se não houve atividade de fala humana sustentada ou o arquivo é pequeno/ruído, ignora
      if (blob.size < 5000 || !_hasSpeechActivity) {
        if (_running) startListening();
        return;
      }

      setCallState('processing');
      try {
        const r = await fetch('/api/voice/stt', {
          method: 'POST',
          headers: { 'Content-Type': 'audio/webm' },
          body: blob,
        });
        const j = await r.json();
        const text = (j.ok && j.text) ? j.text.trim() : '';
        await sendMessageAndSpeak(text);
      } catch {
        if (_running) startListening();
      }
    };

    _mediaRecorder.start();

    // VAD avançado: exige energia de fala sustentada por múltiplos quadros consecutivos (descarta toques no mic)
    const bufData = new Uint8Array(_analyser.frequencyBinCount);
    let silenceStart = null;
    let consecutiveSpeechFrames = 0;
    const SPEECH_THRESHOLD = 24;      // Limiar de volume para fala humana
    const MIN_CONSECUTIVE_FRAMES = 5;  // Mínimo de ~400ms ininterruptos de áudio alto para considerar fala
    const SILENCE_THRESHOLD = 14;
    const SILENCE_DELAY_MS = 1400;
    const MIN_RECORD_MS = 900;
    const recordStart = Date.now();

    function checkSilence() {
      if (!_running || !_mediaRecorder || _mediaRecorder.state !== 'recording') return;
      _analyser.getByteFrequencyData(bufData);
      const avg = bufData.reduce((s, v) => s + v, 0) / bufData.length;

      if (avg >= SPEECH_THRESHOLD) {
        consecutiveSpeechFrames++;
        if (consecutiveSpeechFrames >= MIN_CONSECUTIVE_FRAMES) {
          _hasSpeechActivity = true;
        }
      } else {
        consecutiveSpeechFrames = 0;
      }

      if (avg < SILENCE_THRESHOLD) {
        if (!silenceStart) silenceStart = Date.now();
        const elapsed = Date.now() - recordStart;
        if (silenceStart && (Date.now() - silenceStart) >= SILENCE_DELAY_MS && elapsed >= MIN_RECORD_MS) {
          _mediaRecorder.stop();
          return;
        }
      } else {
        silenceStart = null;
      }
      _silenceTimer = setTimeout(checkSilence, 80);
    }

    checkSilence();
  }

  // ── Iniciar / Encerrar ligação ─────────────────────────────────────────────
  async function startCall() {
    if (_running) return;
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      alert('Permissão de microfone necessária para o Modo Ligação.');
      return;
    }

    _running = true;
    overlay.style.display = 'flex';
    overlay.setAttribute('aria-hidden', 'false');

    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    _analyser = _audioCtx.createAnalyser();
    _analyser.fftSize = 256;
    _audioCtx.createMediaStreamSource(_stream).connect(_analyser);

    animateBars(_analyser);
    startListening();
  }

  function stopCall() {
    _running = false;
    stopCurrentAudio();

    if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
    if (_silenceTimer) { clearTimeout(_silenceTimer); _silenceTimer = null; }
    if (_mediaRecorder && _mediaRecorder.state === 'recording') {
      _mediaRecorder.stop();
    }
    if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
    if (_audioCtx) { _audioCtx.close().catch(() => {}); _audioCtx = null; }

    bars.forEach(b => (b.style.height = '4px'));
    overlay.style.display = 'none';
    overlay.setAttribute('aria-hidden', 'true');
  }

  if (liveCallBtn) liveCallBtn.addEventListener('click', (e) => { e.preventDefault(); startCall(); });
  if (headerLiveCallBtn) headerLiveCallBtn.addEventListener('click', (e) => { e.preventDefault(); startCall(); });
  if (endButton) endButton.addEventListener('click', (e) => { e.preventDefault(); stopCall(); });

  // Expõe globalmente
  window.JarvisLiveCall = { start: startCall, stop: stopCall };
})();
