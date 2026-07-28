(function () {
  const overlay = document.getElementById('cinema-modal-overlay');
  const closeBtn = document.getElementById('cinema-modal-close');
  const titleEl = document.getElementById('cinema-modal-title');
  const posterEl = document.getElementById('cinema-modal-poster');
  const badgeEl = document.getElementById('cinema-modal-type-badge');
  const iframeEl = document.getElementById('cinema-player-iframe');
  const providerSelect = document.getElementById('cinema-provider-select');
  const tvControls = document.getElementById('cinema-tv-controls');
  const seasonSelect = document.getElementById('cinema-season-select');
  const episodeSelect = document.getElementById('cinema-episode-select');
  const fullscreenBtn = document.getElementById('cinema-fullscreen-btn');

  let currentMedia = null;

  function closeModal() {
    if (!overlay) return;
    overlay.classList.add('hidden');
    if (iframeEl) iframeEl.src = 'about:blank'; // interrompe reprodução de áudio ao fechar
  }

  function renderSeasonEpisodeOptions() {
    if (!seasonSelect || !episodeSelect) return;
    seasonSelect.innerHTML = '';
    episodeSelect.innerHTML = '';

    for (let s = 1; s <= 20; s++) {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = `Temporada ${s}`;
      if (s === (currentMedia?.season || 1)) opt.selected = true;
      seasonSelect.appendChild(opt);
    }

    for (let e = 1; e <= 30; e++) {
      const opt = document.createElement('option');
      opt.value = e;
      opt.textContent = `Episódio ${e}`;
      if (e === (currentMedia?.episode || 1)) opt.selected = true;
      episodeSelect.appendChild(opt);
    }
  }

  function updatePlayerUrl() {
    if (!currentMedia || !iframeEl) return;
    const isTv = currentMedia.type === 'tv';
    const imdbId = currentMedia.imdb_id;
    const season = seasonSelect ? parseInt(seasonSelect.value, 10) : (currentMedia.season || 1);
    const episode = episodeSelect ? parseInt(episodeSelect.value, 10) : (currentMedia.episode || 1);
    const selectedProvider = providerSelect ? providerSelect.value : 'VidSrc CC';

    let url = currentMedia.default_url;
    if (isTv) {
      const tvMap = {
        'VidSrc CC': `https://vidsrc.cc/v2/embed/tv/${imdbId}/${season}/${episode}`,
        'EmbedSu': `https://embed.su/embed/tv/${imdbId}/${season}/${episode}`,
        'AutoEmbed': `https://autoembed.co/tv/imdb/${imdbId}-${season}-${episode}`,
        'VidSrc Me': `https://vidsrc.me/embed/tv?imdb=${imdbId}&season=${season}&episode=${episode}`,
        '2Embed': `https://www.2embed.cc/embedtv/${imdbId}&s=${season}&e=${episode}`,
      };
      url = tvMap[selectedProvider] || tvMap['VidSrc CC'];
    } else {
      const movieMap = {
        'VidSrc CC': `https://vidsrc.cc/v2/embed/movie/${imdbId}`,
        'EmbedSu': `https://embed.su/embed/movie/${imdbId}`,
        'AutoEmbed': `https://autoembed.co/movie/imdb/${imdbId}`,
        'VidSrc Me': `https://vidsrc.me/embed/movie?imdb=${imdbId}`,
        '2Embed': `https://www.2embed.cc/embed/${imdbId}`,
      };
      url = movieMap[selectedProvider] || movieMap['VidSrc CC'];
    }

    iframeEl.src = url;
  }

  function openPlayer(data) {
    if (!overlay || !data) return;
    currentMedia = data;

    if (titleEl) titleEl.textContent = data.title || 'Jarvis Cinema';
    if (posterEl && data.poster) {
      posterEl.src = data.poster;
      posterEl.classList.remove('hidden');
    } else if (posterEl) {
      posterEl.classList.add('hidden');
    }

    const isTv = data.type === 'tv';
    if (badgeEl) {
      badgeEl.textContent = isTv ? 'SÉRIE DE TV' : 'FILME';
      badgeEl.className = isTv
        ? 'text-[11px] font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 px-2.5 py-0.5 rounded-full uppercase'
        : 'text-[11px] font-mono font-bold bg-primary-fixed-dim/20 text-primary-fixed-dim border border-primary-fixed-dim/40 px-2.5 py-0.5 rounded-full uppercase';
    }

    if (tvControls) {
      if (isTv) {
        tvControls.classList.remove('hidden');
        renderSeasonEpisodeOptions();
      } else {
        tvControls.classList.add('hidden');
      }
    }

    updatePlayerUrl();
    overlay.classList.remove('hidden');

    // Update IMDb footer
    const footerImdb = document.getElementById('cinema-footer-imdb');
    if (footerImdb) footerImdb.textContent = `IMDb: ${data.imdb_id || '—'}`;

    if (window.JarvisToast) {
      window.JarvisToast.show(`🍿 Jarvis Cinema: Carregando ${data.title}...`, 'info');
    }
  }

  // Event Listeners
  closeBtn?.addEventListener('click', closeModal);
  overlay?.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  providerSelect?.addEventListener('change', updatePlayerUrl);
  seasonSelect?.addEventListener('change', updatePlayerUrl);
  episodeSelect?.addEventListener('change', updatePlayerUrl);

  fullscreenBtn?.addEventListener('click', () => {
    if (!iframeEl) return;
    if (iframeEl.requestFullscreen) {
      iframeEl.requestFullscreen();
    } else if (iframeEl.webkitRequestFullscreen) {
      iframeEl.webkitRequestFullscreen();
    }
  });

  window.JarvisCinema = {
    play: openPlayer,
    close: closeModal,
  };
})();
