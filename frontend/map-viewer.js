(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'map-viewer';
  dialog.setAttribute('aria-labelledby', 'map-viewer-title');
  const header = document.createElement('header');
  header.className = 'map-viewer-header';
  const title = document.createElement('h2');
  title.id = 'map-viewer-title';
  title.textContent = '카카오맵 · 이동시간과 경로 확인';
  const close = document.createElement('button');
  close.type = 'button'; close.className = 'map-viewer-close';
  close.textContent = '×'; close.title = '지도 닫기 · 부산Flow로 돌아가기';
  close.setAttribute('aria-label', '지도 닫기 · 부산Flow로 돌아가기');
  close.autofocus = true;
  header.append(title, close);
  const help = document.createElement('div'); help.className = 'map-viewer-help';
  const note = document.createElement('span');
  note.textContent = '확인 후 오른쪽 위 × 또는 Esc로 닫으세요. 지도가 보이지 않으면 새 탭에서 열어 주세요.';
  const fallback = document.createElement('a'); fallback.textContent = '새 탭에서 열기';
  fallback.target = '_blank'; fallback.rel = 'noopener noreferrer';
  help.append(note, fallback);
  const content = document.createElement('div'); content.className = 'map-viewer-content';
  dialog.append(header, help, content); document.body.append(dialog);
  let trigger, previousOverflow;
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    // Destroy the embedded document so its loading/media stops when dismissed.
    content.replaceChildren(); fallback.removeAttribute('href');
    document.body.style.overflow = previousOverflow ?? '';
    if (trigger?.isConnected) trigger.focus();
    trigger = null;
  });
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[data-map-viewer]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== 'https://map.kakao.com' || !/^\/link\/by\/(car|traffic)\//.test(url.pathname)) return;
    if (typeof dialog.showModal !== 'function') return; // Keep ordinary link behavior on older browsers.
    event.preventDefault();
    trigger = link; previousOverflow = document.body.style.overflow;
    fallback.href = url.href;
    const frame = document.createElement('iframe');
    frame.title = '카카오맵 길찾기'; frame.referrerPolicy = 'no-referrer';
    // Keep the host page and close control independent from the external site.
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox');
    frame.src = url.href;
    content.replaceChildren(frame);
    dialog.showModal(); document.body.style.overflow = 'hidden'; close.focus();
  });
})();
