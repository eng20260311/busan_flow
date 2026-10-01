(() => {
  const video = document.getElementById('hero-video');
  if (!video) return;
  const play = document.getElementById('hero-play');
  const sound = document.getElementById('hero-sound');
  const status = document.getElementById('hero-media-status');
  const controls = document.querySelector('.hero-media-controls');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let failed = false;
  video.muted = true;
  controls.hidden = false;
  function sync() {
    play.textContent = video.paused ? '영상 재생' : '영상 일시정지';
    sound.textContent = video.muted ? '바닷가 소리 켜기' : '바닷가 소리 끄기';
    sound.setAttribute('aria-pressed', String(!video.muted));
  }
  async function start() {
    if (failed) return;
    if (!video.getAttribute('src')) video.src = video.dataset.src;
    try { await video.play(); }
    catch { if (!failed) status.textContent = '영상 재생 버튼을 눌러 감상하세요'; }
    sync();
  }
  play.addEventListener('click', () => video.paused ? start() : video.pause());
  sound.addEventListener('click', () => {
    video.muted = !video.muted;
    if (!video.muted && video.paused) start();
    sync();
  });
  video.addEventListener('playing', () => {
    video.classList.add('is-playing');
    status.textContent = '여행 분위기 영상 · 실시간 현장 영상이 아닙니다';
    sync();
  });
  video.addEventListener('pause', sync);
  video.addEventListener('volumechange', sync);
  video.addEventListener('error', () => {
    failed = true;
    video.classList.remove('is-playing');
    video.pause();
    controls.hidden = true;
    status.textContent = '영상 연결 불가 · 부산 항구 AI 일러스트';
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause(); });
  reduced.addEventListener('change', e => { if (e.matches) video.pause(); });
  // Reduced-motion and data-saving preferences keep the poster until explicit play.
  if (!reduced.matches && !navigator.connection?.saveData) start();
  sync();
})();
