/* Barra de modos do tutor ENEM */
(function () {
  const studyScreen = document.getElementById('screen-study');
  if (!studyScreen) return;

  const overlays = {};
  let activeMode = 'learn';

  function closeAll() {
    Object.values(overlays).forEach((el) => el?.classList.remove('is-open'));
    document.querySelectorAll('.study-mode-btn').forEach((b) => b.classList.remove('active'));
  }

  function openOverlay(name) {
    closeAll();
    activeMode = name;
    const btn = document.querySelector(`[data-study-mode="${name}"]`);
    if (btn) btn.classList.add('active');
    if (name === 'learn') return;
    overlays[name]?.classList.add('is-open');
  }

  function bindToolbar() {
    document.querySelectorAll('.study-mode-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.studyMode;
        openOverlay(mode);
        if (mode === 'review' && window.JarvisStudyFlashcards) window.JarvisStudyFlashcards.open();
        if (mode === 'questions' && window.JarvisStudyEnem) window.JarvisStudyEnem.open();
        if (mode === 'feynman' && window.JarvisStudyFeynman) window.JarvisStudyFeynman.refresh();
        if (mode === 'quiz' && window.JarvisStudyAssessment) window.JarvisStudyAssessment.refresh();
        if (mode === 'progress' && window.JarvisStudyDashboard) window.JarvisStudyDashboard.refresh();
      });
    });

    document.querySelectorAll('.study-overlay-close').forEach((btn) => {
      btn.addEventListener('click', () => openOverlay('learn'));
    });
  }

  function registerOverlay(name, id) {
    overlays[name] = document.getElementById(id);
  }

  registerOverlay('review', 'study-overlay-flashcards');
  registerOverlay('questions', 'study-overlay-enem');
  registerOverlay('feynman', 'study-overlay-feynman');
  registerOverlay('quiz', 'study-overlay-quiz');
  registerOverlay('progress', 'study-overlay-dashboard');

  bindToolbar();

  window.JarvisStudyToolbar = {
    openOverlay,
    closeAll,
    setDueBadge(count) {
      const badge = document.getElementById('study-due-badge');
      if (!badge) return;
      badge.textContent = String(count);
      badge.style.display = count > 0 ? 'inline' : 'none';
    },
  };
})();
