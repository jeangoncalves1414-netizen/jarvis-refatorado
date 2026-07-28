/* Captura de microfone, STT/TTS no browser */
(function () {
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let speakEnabled = true;

  function showVoiceError(message) {
    console.warn('[JarvisVoice]', message);
    if (window.JarvisOrb) window.JarvisOrb.setState('error');
    alert(message);
    setTimeout(() => {
      if (window.JarvisOrb) window.JarvisOrb.setState('idle');
    }, 2500);
  }

  function getSpeakEnabled() {
    try {
      const stored = localStorage.getItem('jarvis_speak_responses');
      if (stored !== null) speakEnabled = stored === '1';
    } catch (_) {}
    return speakEnabled;
  }

  function setSpeakEnabled(value) {
    speakEnabled = !!value;
    try {
      localStorage.setItem('jarvis_speak_responses', speakEnabled ? '1' : '0');
    } catch (_) {}
  }

  async function speak(text) {
    if (!getSpeakEnabled() || !text) return;
    try {
      const r = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: String(text).slice(0, 800) }),
      });
      if (!r.ok) {
        let message = 'Não foi possível reproduzir a resposta em voz.';
        try {
          const j = await r.json();
          if (j.error) message = j.error;
        } catch (_) {}
        console.warn('TTS falhou:', message);
        if (window.JarvisOrb) window.JarvisOrb.setState('idle');
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      if (window.JarvisOrb) {
        window.JarvisOrb.setState('speaking');
        window.dispatchEvent(new CustomEvent('jarvis:speaking', { detail: { speaking: true } }));
        audio.onended = () => {
          window.JarvisOrb?.setState('idle');
          window.dispatchEvent(new CustomEvent('jarvis:speaking', { detail: { speaking: false } }));
        };
        audio.onerror = () => {
          console.warn('TTS: falha ao reproduzir áudio.');
          window.JarvisOrb?.setState('idle');
          window.dispatchEvent(new CustomEvent('jarvis:speaking', { detail: { speaking: false } }));
        };
      }
      await audio.play();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      console.warn('TTS falhou', e);
      if (window.JarvisOrb) window.JarvisOrb.setState('idle');
      window.dispatchEvent(new CustomEvent('jarvis:speaking', { detail: { speaking: false } }));
    }

  }

  async function startRecording() {
    if (isRecording) return '';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : {};
      mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      return new Promise((resolve) => {
        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          isRecording = false;
          if (window.JarvisOrb) window.JarvisOrb.setState('thinking');
          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          if (!blob.size) {
            showVoiceError('Nenhum áudio capturado. Segure o botão do microfone enquanto fala.');
            resolve('');
            return;
          }
          try {
            const r = await fetch('/api/voice/stt', {
              method: 'POST',
              headers: { 'Content-Type': 'audio/webm' },
              body: blob,
            });
            const j = await r.json();
            if (!r.ok) {
              showVoiceError(j.error || 'Erro ao transcrever áudio.');
              resolve('');
              return;
            }
            if (!j.ok) {
              showVoiceError(j.error || 'Não foi possível entender o que você disse. Tente novamente.');
              resolve('');
              return;
            }
            resolve(j.text || '');
          } catch (e) {
            console.error('STT falhou', e);
            showVoiceError('Falha de conexão ao transcrever áudio. Verifique se o Jarvis está rodando.');
            resolve('');
          }
        };
        mediaRecorder.start();
        isRecording = true;
        if (window.JarvisOrb) window.JarvisOrb.setState('listening');
      });
    } catch (e) {
      console.error('Microfone indisponível', e);
      const denied = e && (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError');
      showVoiceError(
        denied
          ? 'Permita o acesso ao microfone nas configurações do navegador para usar o comando de voz.'
          : 'Microfone indisponível. Verifique se há um dispositivo de áudio conectado.'
      );
      return '';
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) mediaRecorder.stop();
  }

  window.JarvisVoice = {
    speak,
    startRecording,
    stopRecording,
    getSpeakEnabled,
    setSpeakEnabled,
  };
})();
