/* Design-Varianten: ?v=b aktiviert Variante B (bleibt beim Weiterklicken gespeichert), ?v=a zurück zum Original. */
(function () {
  var VARIANTS = {
    b: { css: 'assets/v-b.css?v=202610301200', label: 'Variante B · Vibrant',
         fonts: 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Righteous&display=swap' },
    c: { css: 'assets/v-c.css?v=202610301155', label: 'Variante C · Apple' }
  };
  var v = null;
  try {
    var q = new URLSearchParams(location.search).get('v');
    if (q !== null) {
      if (VARIANTS[q]) localStorage.setItem('zugnow-v', q); else localStorage.removeItem('zugnow-v');
    }
    v = localStorage.getItem('zugnow-v');
  } catch (e) {
    try { v = new URLSearchParams(location.search).get('v') } catch (e2) {}
  }
  var cfg = VARIANTS[v];
  if (!cfg) return;
  document.documentElement.setAttribute('data-v', v);
  function link(href) { var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l) }
  if (cfg.fonts) link(cfg.fonts);
  link(cfg.css);
  document.addEventListener('DOMContentLoaded', function () {
    var p = document.createElement('div');
    p.className = 'vswitch';
    p.innerHTML = '<span>' + cfg.label + '</span><a href="?v=a">Original anzeigen</a>';
    document.body.appendChild(p);
  });
})();
