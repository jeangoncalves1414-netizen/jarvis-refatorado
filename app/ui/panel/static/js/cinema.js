(function () {
  const overlay = document.getElementById('cinema-modal-overlay');
  const closeBtn = document.getElementById('cinema-modal-close');
  const openBtn = document.getElementById('cinema-open-button');
  const titleEl = document.getElementById('cinema-modal-title');
  const posterEl = document.getElementById('cinema-modal-poster');
  const badgeEl = document.getElementById('cinema-modal-type-badge');
  const footerImdb = document.getElementById('cinema-footer-imdb');
  const trailerLink = document.getElementById('cinema-trailer-link');
  const watchLink = document.getElementById('cinema-watch-link');
  const imdbLink = document.getElementById('cinema-imdb-link');
  const video = document.getElementById('cinema-video-player');
  const discovery = document.getElementById('cinema-discovery-state');
  const librarySelect = document.getElementById('cinema-library-select');
  const seasonSelect = document.getElementById('cinema-season-select');
  const episodeSelect = document.getElementById('cinema-episode-select');
  const qualitySelect = document.getElementById('cinema-quality-select');
  const playLibraryBtn = document.getElementById('cinema-play-library');
  const nextEpisodeBtn = document.getElementById('cinema-next-episode');
  const discoveryQuery = document.getElementById('cinema-discovery-query');
  const discoverySearchBtn = document.getElementById('cinema-discovery-search');
  const discoveryResults = document.getElementById('cinema-discovery-results');
  const sourceTitle = document.getElementById('cinema-source-title');
  const sourceUrl = document.getElementById('cinema-source-url');
  const sourceType = document.getElementById('cinema-source-type');
  const sourceLabel = document.getElementById('cinema-source-label');
  const sourceEpisodeFields = document.getElementById('cinema-source-episode-fields');
  const sourceSeason = document.getElementById('cinema-source-season');
  const sourceEpisode = document.getElementById('cinema-source-episode');
  const saveSourceBtn = document.getElementById('cinema-save-source');

  let libraryItems = [];
  let hlsPlayer = null;

  function toast(message, kind = 'info') {
    window.JarvisToast?.show(message, kind);
  }

  function clearOptions(select, placeholder) {
    if (!select) return;
    select.innerHTML = '';
    const option = document.createElement('option');
    option.value = '';
    option.textContent = placeholder;
    select.appendChild(option);
  }

  function setTitle(data) {
    const isTv = data.type === 'tv';
    if (titleEl) titleEl.textContent = data.title || 'Jarvis Cinema';
    if (badgeEl) badgeEl.textContent = isTv ? 'SÉRIE DE TV' : 'FILME';
    if (posterEl) {
      posterEl.classList.toggle('hidden', !data.poster);
      if (data.poster) posterEl.src = data.poster;
    }
    if (trailerLink) trailerLink.href = data.trailer_url || 'https://www.youtube.com/';
    if (watchLink) watchLink.href = data.watch_url || 'https://www.justwatch.com/br';
    if (imdbLink) imdbLink.href = data.imdb_url || (data.imdb_id ? `https://www.imdb.com/title/${data.imdb_id}/` : 'https://www.imdb.com/');
    if (footerImdb) footerImdb.textContent = `IMDb: ${data.imdb_id || '—'}`;
  }

  function destroyPlayer() {
    if (hlsPlayer) {
      hlsPlayer.destroy();
      hlsPlayer = null;
    }
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
  }

  function loadHlsScript() {
    if (window.Hls) return Promise.resolve(window.Hls);
    const existing = document.querySelector('script[data-jarvis-hls]');
    if (existing) {
      return new Promise((resolve, reject) => {
        existing.addEventListener('load', () => resolve(window.Hls), { once: true });
        existing.addEventListener('error', reject, { once: true });
      });
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/hls.js@1.5.18/dist/hls.min.js';
      script.dataset.jarvisHls = 'true';
      script.onload = () => resolve(window.Hls);
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function playUrl(url) {
    if (!video || !url) return;
    destroyPlayer();
    discovery?.classList.add('hidden');
    video.classList.remove('hidden');
    const isHls = /\.m3u8(?:$|[?#])/i.test(url);
    try {
      if (isHls && video.canPlayType('application/vnd.apple.mpegurl') === '') {
        const Hls = await loadHlsScript();
        if (!Hls?.isSupported()) throw new Error('HLS não é suportado neste navegador.');
        hlsPlayer = new Hls({ enableWorker: true });
        hlsPlayer.loadSource(url);
        hlsPlayer.attachMedia(video);
        hlsPlayer.on(Hls.Events.MANIFEST_PARSED, (_, details) => populateHlsLevels(details.levels));
        hlsPlayer.on(Hls.Events.ERROR, (_, data) => {
          if (data.fatal) toast('A fonte HLS não pôde ser reproduzida.', 'error');
        });
      } else {
        video.src = url;
      }
      await video.play().catch(() => undefined);
    } catch (error) {
      discovery?.classList.remove('hidden');
      video.classList.add('hidden');
      toast(error.message || 'Não foi possível carregar esta mídia.', 'error');
    }
  }

  function populateHlsLevels(levels) {
    if (!qualitySelect) return;
    clearOptions(qualitySelect, 'Automático');
    levels.forEach((level, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = level.height ? `${level.height}p` : `Qualidade ${index + 1}`;
      qualitySelect.appendChild(option);
    });
  }

  function getSelectedItem() {
    return libraryItems.find(item => item.id === librarySelect?.value) || null;
  }

  function getSelectedEpisode(item) {
    return (item.episodes || []).find(entry => entry.season === Number(seasonSelect?.value) && entry.episode === Number(episodeSelect?.value)) || null;
  }

  function populateEpisodeControls() {
    const item = getSelectedItem();
    const isTv = item?.type === 'tv';
    seasonSelect?.classList.toggle('hidden', !isTv);
    episodeSelect?.classList.toggle('hidden', !isTv);
    nextEpisodeBtn?.classList.toggle('hidden', !isTv);
    if (!item) {
      clearOptions(seasonSelect, 'Temporada');
      clearOptions(episodeSelect, 'Episódio');
      clearOptions(qualitySelect, 'Fonte / qualidade');
      return;
    }
    if (isTv) {
      const seasons = [...new Set((item.episodes || []).map(entry => entry.season))];
      clearOptions(seasonSelect, 'Temporada');
      seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = String(season);
        option.textContent = `Temporada ${season}`;
        seasonSelect.appendChild(option);
      });
      if (seasons.length) seasonSelect.value = String(seasons[0]);
      populateEpisodes();
    } else {
      populateSources(item.sources || []);
    }
  }

  function populateEpisodes() {
    const item = getSelectedItem();
    const episodes = (item?.episodes || []).filter(entry => entry.season === Number(seasonSelect?.value));
    clearOptions(episodeSelect, 'Episódio');
    episodes.forEach(entry => {
      const option = document.createElement('option');
      option.value = String(entry.episode);
      option.textContent = `Episódio ${entry.episode}`;
      episodeSelect.appendChild(option);
    });
    if (episodes.length) episodeSelect.value = String(episodes[0].episode);
    populateSources(episodes[0]?.sources || []);
  }

  function populateSources(sources) {
    clearOptions(qualitySelect, 'Fonte / qualidade');
    sources.forEach((source, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = source.label || `Fonte ${index + 1}`;
      qualitySelect.appendChild(option);
    });
    if (sources.length) qualitySelect.value = '0';
  }

  function playSelectedLibraryItem() {
    const item = getSelectedItem();
    if (!item) return toast('Selecione uma mídia da biblioteca.', 'error');
    const episode = item.type === 'tv' ? getSelectedEpisode(item) : null;
    const sources = episode ? episode.sources : item.sources;
    const source = sources?.[Number(qualitySelect?.value) || 0];
    if (!source?.url) return toast('Esta mídia ainda não possui uma fonte válida.', 'error');
    setTitle({ ...item, title: episode ? `${item.title} · T${episode.season} E${episode.episode}` : item.title });
    playUrl(source.url);
  }

  function playNextEpisode() {
    const item = getSelectedItem();
    const current = item?.type === 'tv' ? getSelectedEpisode(item) : null;
    if (!item || !current) return toast('Selecione um episódio para continuar.', 'error');
    const episodes = [...(item.episodes || [])].sort((a, b) => a.season - b.season || a.episode - b.episode);
    const next = episodes[episodes.findIndex(entry => entry.season === current.season && entry.episode === current.episode) + 1];
    if (!next) return toast('Não há próximo episódio salvo na biblioteca.', 'info');
    seasonSelect.value = String(next.season);
    populateEpisodes();
    episodeSelect.value = String(next.episode);
    populateSources(next.sources || []);
    playSelectedLibraryItem();
  }

  async function refreshLibrary(selectedId = '') {
    try {
      const response = await fetch('/api/cinema/library');
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha ao carregar biblioteca.');
      libraryItems = data.items || [];
      clearOptions(librarySelect, 'Selecione uma mídia salva');
      libraryItems.forEach(item => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = `${item.type === 'tv' ? 'Série' : 'Filme'} · ${item.title}`;
        librarySelect.appendChild(option);
      });
      if (selectedId) librarySelect.value = selectedId;
      populateEpisodeControls();
    } catch (error) {
      toast('Não foi possível carregar a biblioteca.', 'error');
    }
  }

  async function saveSource() {
    const payload = {
      title: sourceTitle?.value,
      url: sourceUrl?.value,
      type: sourceType?.value,
      label: sourceLabel?.value,
      season: sourceSeason?.value,
      episode: sourceEpisode?.value,
    };
    try {
      const response = await fetch('/api/cinema/library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha ao salvar fonte.');
      if (sourceUrl) sourceUrl.value = '';
      if (sourceLabel) sourceLabel.value = '';
      await refreshLibrary(data.item.id);
      toast('Fonte salva na biblioteca.', 'success');
    } catch (error) {
      toast(error.message || 'Não foi possível salvar a fonte.', 'error');
    }
  }

  function renderDiscoveryMessage(message) {
    if (!discoveryResults) return;
    discoveryResults.replaceChildren();
    const text = document.createElement('p');
    text.textContent = message;
    discoveryResults.appendChild(text);
  }

  function createDiscoveryButton(label, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'block w-full rounded border border-white/10 bg-white/5 px-2 py-1.5 text-left hover:border-primary-fixed-dim/50 hover:bg-primary-fixed-dim/10';
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
  }

  async function inspectDiscoveryPage(url, title = '') {
    renderDiscoveryMessage('Analisando mídia pública da página…');
    try {
      const response = await fetch('/api/cinema/discovery/probe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível analisar a página.');
      if (!data.media?.length) return renderDiscoveryMessage(data.message || 'Nenhuma mídia pública reproduzível foi encontrada.');
      discoveryResults.replaceChildren();
      const heading = document.createElement('p');
      heading.textContent = 'Mídia detectada — escolha uma fonte:';
      discoveryResults.appendChild(heading);
      data.media.forEach(media => {
        discoveryResults.appendChild(createDiscoveryButton(`Reproduzir ${media.label || 'fonte detectada'}`, () => {
          setTitle({ title: title || 'Mídia detectada', type: 'movie' });
          playUrl(media.url);
        }));
      });
    } catch (error) {
      renderDiscoveryMessage(error.message || 'Falha ao analisar a página.');
    }
  }

  function renderSearchResults(results) {
    if (!results?.length) return renderDiscoveryMessage('Nenhum resultado encontrado nas fontes aprovadas.');
    discoveryResults.replaceChildren();
    results.forEach(result => {
      const label = `${result.title} · ${result.source}`;
      discoveryResults.appendChild(createDiscoveryButton(label, () => inspectDiscoveryPage(result.url, result.title)));
    });
  }

  async function openCatalogResult(item) {
    renderDiscoveryMessage('Preparando título…');
    try {
      const response = await fetch('/api/cinema/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imdb_id: item.id, title: item.title, type: item.type, poster: item.poster }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível preparar o título.');
      openCinema(data);
    } catch (error) {
      renderDiscoveryMessage(error.message || 'Falha ao abrir o título.');
    }
  }

  function renderCatalogResults(results) {
    if (!results?.length) return renderDiscoveryMessage('Nenhum filme ou série foi encontrado.');
    discoveryResults.replaceChildren();
    const heading = document.createElement('p');
    heading.textContent = 'Resultados do catálogo — escolha um título:';
    discoveryResults.appendChild(heading);
    results.forEach(item => {
      const label = `${item.type === 'tv' ? 'Série' : 'Filme'} · ${item.title || 'Sem título'}${item.year ? ` (${item.year})` : ''}`;
      discoveryResults.appendChild(createDiscoveryButton(label, () => openCatalogResult(item)));
    });
  }

  async function searchDiscovery() {
    const query = discoveryQuery?.value.trim();
    if (!query) return toast('Informe um título para pesquisar.', 'error');
    renderDiscoveryMessage('Pesquisando fontes aprovadas…');
    try {
      const response = await fetch(`/api/cinema/discovery/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha ao pesquisar.');
      renderSearchResults(data.results);
    } catch (error) {
      renderDiscoveryMessage(error.message || 'Não foi possível concluir a pesquisa.');
    }
  }

  function openCinema(data = {}) {
    if (!overlay) return;
    setTitle(data);
    destroyPlayer();
    discovery?.classList.remove('hidden');
    video?.classList.add('hidden');
    overlay.classList.remove('hidden');
    refreshLibrary();
    if (data.catalog_results) renderCatalogResults(data.catalog_results);
    else if (data.discovery_results) renderSearchResults(data.discovery_results);
  }

  function closeModal() {
    destroyPlayer();
    overlay?.classList.add('hidden');
  }

  closeBtn?.addEventListener('click', closeModal);
  openBtn?.addEventListener('click', () => openCinema());
  overlay?.addEventListener('click', event => { if (event.target === overlay) closeModal(); });
  librarySelect?.addEventListener('change', populateEpisodeControls);
  seasonSelect?.addEventListener('change', populateEpisodes);
  episodeSelect?.addEventListener('change', () => populateSources(getSelectedEpisode(getSelectedItem())?.sources || []));
  qualitySelect?.addEventListener('change', () => { if (hlsPlayer) hlsPlayer.currentLevel = Number(qualitySelect.value); });
  playLibraryBtn?.addEventListener('click', playSelectedLibraryItem);
  nextEpisodeBtn?.addEventListener('click', playNextEpisode);
  discoverySearchBtn?.addEventListener('click', searchDiscovery);
  discoveryQuery?.addEventListener('keydown', event => { if (event.key === 'Enter') searchDiscovery(); });
  sourceType?.addEventListener('change', () => sourceEpisodeFields?.classList.toggle('hidden', sourceType.value !== 'tv'));
  saveSourceBtn?.addEventListener('click', saveSource);

  window.JarvisCinema = {
    play: openCinema,
    openLibrary: () => openCinema(),
    detectUrl: async (url, title = '') => {
      openCinema({ title: title || 'Mídia detectada', type: 'movie' });
      await inspectDiscoveryPage(url, title);
    },
    close: closeModal,
  };
})();
