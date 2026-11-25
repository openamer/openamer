/* Shared shell behaviour for the marketing pages under docs/: theme toggle
   (persisted, honours prefers-color-scheme) and the sticky-nav border. */
(function () {
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('oa-theme'); } catch (e) {}
  var forced = null;
  try { forced = new URLSearchParams(location.search).get('theme'); } catch (e) {}
  var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  var theme = (forced === 'dark' || forced === 'light') ? forced : (stored || (prefersLight ? 'light' : 'dark'));

  function apply(t) {
    root.setAttribute('data-theme', t);
    var sun = document.getElementById('icoSun'), moon = document.getElementById('icoMoon');
    if (sun && moon) { sun.hidden = (t !== 'light'); moon.hidden = (t === 'light'); }
  }
  apply(theme);

  var btn = document.getElementById('themeBtn');
  if (btn) {
    btn.addEventListener('click', function () {
      theme = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      apply(theme);
      try { localStorage.setItem('oa-theme', theme); } catch (e) {}
    });
  }

  var nav = document.getElementById('nav');
  function onScroll() { if (nav) nav.setAttribute('data-stuck', window.scrollY > 8 ? 'true' : 'false'); }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
})();
