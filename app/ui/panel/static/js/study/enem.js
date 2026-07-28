/* Banco ENEM — colar questão, carregar do banco, enviar ao tutor */
(function () {
  const overlay = document.getElementById('study-overlay-enem');
  if (!overlay) return;

  const textEl = document.getElementById('study-enem-text');
  const subjectEl = document.getElementById('study-enem-subject');
  const yearEl = document.getElementById('study-enem-year');
  const imageDrop = document.getElementById('study-enem-image-drop');
  const imagePreview = document.getElementById('study-enem-image-preview');
  const imageClearBtn = document.getElementById('study-enem-image-clear');
  const saveBtn = document.getElementById('study-enem-save');
  const studyPasteBtn = document.getElementById('study-enem-study-paste');
  const selectEl = document.getElementById('study-enem-select');
  const bankPreview = document.getElementById('study-enem-bank-preview');
  const studyBankBtn = document.getElementById('study-enem-study-bank');

  let pastedImageBase64 = null;

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function subjectLabel(code) {
    const map = {
      linguagens: 'Linguagens',
      matematica: 'Matemática',
      ciencias_natureza: 'Ciências da Natureza',
      ciencias_humanas: 'Ciências Humanas',
      redacao: 'Redação',
    };
    return map[code] || code || 'ENEM';
  }

  function readForm() {
    return {
      text: (textEl?.value || '').trim(),
      subject: subjectEl?.value || '',
      year: yearEl?.value ? parseInt(yearEl.value, 10) : null,
      image_base64: pastedImageBase64,
    };
  }

  function setImagePreview(dataUrl) {
    pastedImageBase64 = dataUrl;
    if (!imagePreview || !imageDrop) return;
    if (dataUrl) {
      imagePreview.src = dataUrl;
      imagePreview.hidden = false;
      imageClearBtn.hidden = false;
      imageDrop.classList.add('has-image');
    } else {
      imagePreview.src = '';
      imagePreview.hidden = true;
      imageClearBtn.hidden = true;
      imageDrop.classList.remove('has-image');
    }
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function bindImagePaste() {
    imageDrop?.addEventListener('paste', async (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) setImagePreview(await fileToDataUrl(file));
          return;
        }
      }
    });

    imageDrop?.addEventListener('dragover', (e) => {
      e.preventDefault();
      imageDrop.classList.add('is-dragover');
    });
    imageDrop?.addEventListener('dragleave', () => imageDrop.classList.remove('is-dragover'));
    imageDrop?.addEventListener('drop', async (e) => {
      e.preventDefault();
      imageDrop.classList.remove('is-dragover');
      const file = e.dataTransfer?.files?.[0];
      if (file && file.type.startsWith('image/')) {
        setImagePreview(await fileToDataUrl(file));
      }
    });

    imageClearBtn?.addEventListener('click', () => setImagePreview(null));
  }

  const WB_MAX_WIDTH = 480;
  const WB_LINE_HEIGHT = 1.5;

  function estimateTextHeight(text, fontSize = 15, maxWidth = WB_MAX_WIDTH) {
    const avgCharWidth = fontSize * 0.55;
    const charsPerLine = Math.max(1, Math.floor(maxWidth / avgCharWidth));
    const lines = String(text || '').split('\n');
    let totalLines = 0;
    for (const line of lines) {
      const len = line.length || 1;
      totalLines += Math.max(1, Math.ceil(len / charsPerLine));
    }
    return Math.ceil(totalLines * fontSize * WB_LINE_HEIGHT) + 8;
  }

  function elementBottom(el) {
    const y = el.y || 0;
    if (el.type === 'image') return y + (el.height || 300);
    return y + estimateTextHeight(el.content || '', el.size || 16);
  }

  function splitQuestionText(text) {
    const lines = String(text || '').split('\n');
    const stem = [];
    const options = [];
    let inOptions = false;
    const optionRe = /^(\(?[A-Ea-e]\)?[\).:\-]\s*|\(?[A-Ea-e]\)\s*)/;
    for (const line of lines) {
      const trimmed = line.trim();
      if (optionRe.test(trimmed)) {
        inOptions = true;
        options.push(line);
      } else if (inOptions && trimmed === '') {
        options.push(line);
      } else if (!inOptions) {
        stem.push(line);
      } else {
        options.push(line);
      }
    }
    return {
      stem: stem.join('\n').trim(),
      options: options.join('\n').trim(),
    };
  }

  function buildWhiteboardElements(question, offsetY = 0) {
    const elements = [];
    const x = 40;
    let y = 40 + offsetY;
    const label = subjectLabel(question.subject || question.area || '');
    const year = question.year ? ` · ${question.year}` : '';

    elements.push({
      id: crypto.randomUUID(),
      type: 'text',
      content: `[Questão ENEM — ${label}${year}]`,
      x,
      y,
      size: 14,
      color: '#00daf8',
    });
    y += 36;

    const { stem, options } = splitQuestionText(question.text || '');
    const bodyText = stem || question.text || '';

    if (bodyText) {
      elements.push({
        id: crypto.randomUUID(),
        type: 'text',
        content: bodyText,
        x,
        y,
        size: 15,
        color: '#ffffff',
        role: 'stem',
      });
      y += estimateTextHeight(bodyText, 15) + 20;
    }

    if (question.image_base64) {
      const src = String(question.image_base64).startsWith('data:')
        ? question.image_base64
        : `data:image/png;base64,${question.image_base64}`;
      elements.push({
        id: crypto.randomUUID(),
        type: 'image',
        content: src,
        x,
        y,
        width: 420,
        height: 300,
      });
      y += 324;
    }

    if (options) {
      elements.push({
        id: crypto.randomUUID(),
        type: 'text',
        content: options,
        x,
        y,
        size: 14,
        color: '#bac9cd',
        role: 'options',
      });
    }

    return elements;
  }

  async function pushQuestionToWhiteboard(sessionId, question) {
    let existing = [];
    try {
      const prev = await fetch(`/api/sessions/${sessionId}/whiteboard`);
      if (prev.ok) {
        const j = await prev.json();
        existing = j.whiteboard || [];
      }
    } catch (_) {}
    const offsetY = existing.reduce((max, el) => Math.max(max, elementBottom(el)), 0);
    const gap = existing.length ? 48 : 0;
    const elements = [...existing, ...buildWhiteboardElements(question, offsetY + gap)];
    const r = await fetch(`/api/sessions/${sessionId}/whiteboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ whiteboard: elements }),
    });
    if (!r.ok) throw new Error('Falha ao atualizar o quadro.');
    return elements;
  }

  async function refreshBankList() {
    if (!selectEl) return;
    try {
      const r = await fetch('/api/enem/questions');
      if (!r.ok) return;
      const j = await r.json();
      const questions = j.questions || [];
      selectEl.innerHTML = '<option value="">— Selecione uma questão —</option>';
      questions.forEach((q) => {
        const opt = document.createElement('option');
        opt.value = q.id;
        const year = q.year ? ` (${q.year})` : '';
        opt.textContent = `${subjectLabel(q.subject)}${year} — ${q.preview || q.id}`;
        selectEl.appendChild(opt);
      });
    } catch (e) {
      console.warn('Falha ao listar questões ENEM', e);
    }
  }

  function renderBankPreview(question) {
    if (!bankPreview) return;
    if (!question) {
      bankPreview.innerHTML = '<p class="study-enem-preview-empty">Selecione uma questão para ver o enunciado.</p>';
      return;
    }
    const label = subjectLabel(question.subject || question.area || '');
    const year = question.year ? ` · ${question.year}` : '';
    let html = `<div class="study-enem-preview-meta">${escapeHtml(label)}${escapeHtml(year)}</div>`;
    html += `<pre class="study-enem-preview-text">${escapeHtml(question.text || '')}</pre>`;
    if (question.image_base64) {
      const src = String(question.image_base64).startsWith('data:')
        ? question.image_base64
        : `data:image/png;base64,${question.image_base64}`;
      html += `<img class="study-enem-preview-img" src="${src}" alt="Imagem da questão"/>`;
    }
    bankPreview.innerHTML = html;
  }

  async function loadSelectedQuestion() {
    const id = selectEl?.value;
    if (!id) {
      renderBankPreview(null);
      return null;
    }
    const r = await fetch(`/api/enem/questions/${encodeURIComponent(id)}`);
    if (!r.ok) return null;
    const j = await r.json();
    return j.question || null;
  }

  async function saveQuestion(form) {
    if (!form.text) {
      alert('Cole o enunciado da questão antes de salvar.');
      return null;
    }
    const r = await fetch('/api/enem/questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      alert(j.error || 'Não foi possível salvar a questão.');
      return null;
    }
    await refreshBankList();
    if (selectEl && j.question?.id) selectEl.value = j.question.id;
    return j.question;
  }

  async function startStudy(question, opts = {}) {
    if (!question?.text) {
      alert('A questão precisa ter um enunciado em texto.');
      return;
    }

    const study = window.JarvisStudy;
    if (!study?.ensureSession) {
      alert('Modo estudos não inicializado.');
      return;
    }

    const title = `${subjectLabel(question.subject)}${question.year ? ' ' + question.year : ''}`.trim();
    const sessionId = await study.ensureSession(title.slice(0, 40) || 'Questão ENEM');
    if (!sessionId) return;

    try {
      await pushQuestionToWhiteboard(sessionId, question);
      await study.loadWhiteboard?.(sessionId);

      const tutorMsg = opts.message
        || 'Vamos resolver esta questão juntos. Me guie passo a passo, uma pergunta de cada vez, sem dar a resposta direto.';

      await study.sendTutorMessage(tutorMsg, {
        enem_question_id: question.id || undefined,
        enem_context: question.id ? undefined : {
          text: question.text,
          subject: question.subject,
          year: question.year,
          image_base64: question.image_base64,
        },
      });

      window.JarvisStudyToolbar?.openOverlay('learn');
    } catch (e) {
      alert(e.message || 'Erro ao iniciar estudo da questão.');
    }
  }

  saveBtn?.addEventListener('click', async () => {
    const saved = await saveQuestion(readForm());
    if (saved) alert('Questão salva no banco local.');
  });

  studyPasteBtn?.addEventListener('click', async () => {
    const form = readForm();
    if (!form.text && !form.image_base64) {
      alert('Cole o enunciado (texto ou imagem) antes de estudar.');
      return;
    }
    if (!form.text && form.image_base64) {
      form.text = '[Questão com imagem — veja o quadro]';
    }
    await startStudy(form);
  });

  studyBankBtn?.addEventListener('click', async () => {
    const question = await loadSelectedQuestion();
    if (!question) {
      alert('Selecione uma questão do banco.');
      return;
    }
    await startStudy(question);
  });

  selectEl?.addEventListener('change', async () => {
    const question = await loadSelectedQuestion();
    renderBankPreview(question);
  });

  bindImagePaste();

  window.JarvisStudyEnem = {
    open() {
      refreshBankList();
      renderBankPreview(null);
    },
    refresh: refreshBankList,
  };
})();
