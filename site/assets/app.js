/* zug.now – gemeinsames Skript für alle Seiten.
   Jede Seite setzt <body data-page="start|agenda|news|amtlich|politik"> und hat Platzhalter mit IDs. */
(function () {
  var TZ = 'Europe/Zurich';
  var WD = ['SO', 'MO', 'DI', 'MI', 'DO', 'FR', 'SA'], MO = ['JAN', 'FEB', 'MÄR', 'APR', 'MAI', 'JUN', 'JUL', 'AUG', 'SEP', 'OKT', 'NOV', 'DEZ'];
  var WDL = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  var CATS = [['alle', 'Alle'], ['kinder', 'Kinder & Familie'], ['kultur', 'Kultur & Musik'], ['maerkte', 'Märkte & Feste'], ['treff', 'Treffpunkte'], ['sport', 'Sport & Natur'], ['weitere', 'Weitere']];
  var TIMES = [['alle', 'Alle Termine'], ['heute', 'Heute'], ['morgen', 'Morgen'], ['wochenende', 'Wochenende'], ['woche', 'Diese Woche']];
  var PLACES = [['alle', 'Alle Orte'], ['bibliothek', 'Bibliothek Zug'], ['kunsthaus', 'Kunsthaus Zug'], ['burg', 'Museum Burg Zug'], ['musikschule', 'Musikschule'], ['theatercasino', 'Theater Casino'], ['galvanik', 'Galvanik'], ['kino', 'Kino']];
  var PAGES = [['/', 'start', 'Start'], ['agenda/', 'agenda', 'Agenda'], ['news/', 'news', 'News'], ['amtlich/', 'amtlich', 'Amtlich'], ['politik/', 'politik', 'Politik'], ['wandel/', 'wandel', 'Wandel']];
  var page = document.body.dataset.page || 'start';
  var D = {};

  // ---------- Helfer
  function $(id) { return document.getElementById(id) }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] }) }
  function parts(iso) {
    var f = new Intl.DateTimeFormat('de-CH', { timeZone: TZ, year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date(iso));
    var o = {}; f.forEach(function (p) { o[p.type] = p.value });
    var key = o.year + '-' + String(o.month).padStart(2, '0') + '-' + String(o.day).padStart(2, '0');
    return { m: +o.month, d: +o.day, hm: o.hour + ':' + o.minute, dow: dowOf(key), key: key };
  }
  function todayKey() { return parts(new Date().toISOString()).key }
  function dowOf(key) { var p = key.split('-'); return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).getUTCDay() }
  function addDays(key, n) { var p = key.split('-'); return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n)).toISOString().slice(0, 10) }
  function dLabel(key) { var p = key.split('-'); return +p[2] + '.' + (+p[1]) + '.' + p[0] }
  function dShort(key) { var p = key.split('-'); return WDL[dowOf(key)] + ' ' + (+p[2]) + '.' + (+p[1]) + '.' }
  function timeLabel(e) { if (e.allday) return 'ganztags'; var a = parts(e.start).hm; return e.end ? a + '–' + parts(e.end).hm : a }
  // Eigene Seite pro Anlass (vom Build vergeben), sonst Anker in der Agenda
  function evHref(e) { return e.page || 'agenda/#ev-' + e.id }
  function img(src) { return src ? '<img src="' + esc(src) + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">' : '' }
  function get(n) { return fetch('data/' + n + '.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json() }).catch(function () { return null }) }

  // ---------- Zeitraum
  function range(t) {
    var tk = todayKey(), dw = dowOf(tk);
    if (t === 'heute') return [tk, tk];
    if (t === 'morgen') return [addDays(tk, 1), addDays(tk, 1)];
    if (t === 'woche') return [tk, addDays(tk, (7 - dw) % 7)];
    if (t === 'wochenende') {
      if (dw === 0) return [tk, tk];
      if (dw === 6) return [tk, addDays(tk, 1)];
      var sa = addDays(tk, 6 - dw); return [sa, addDays(sa, 1)];
    }
    return ['0000', '9999'];
  }
  // Vorbei: Ende (oder Beginn, falls ohne Ende) liegt in der Vergangenheit; ganztägige bleiben bis Tagesende
  function over(e) { if (e.allday) return false; return new Date(e.end || e.start) < new Date() }
  function inTime(e, t) { var k = parts(e.start).key, r = range(t); return k >= r[0] && k <= r[1] }

  // ---------- Rahmen: Kopf, Leiste, Fuss
  function frame() {
    if ($('sBtn')) return; // Kopf und Fuss stehen bereits im HTML
    $('hdr').innerHTML =
      '<header><div class="wrap"><a class="logo" href="/" aria-label="zug.now Startseite">zug<span class="dot">.</span><span class="now">now</span></a>' +
      '<nav aria-label="Hauptnavigation">' + PAGES.map(function (p) { return '<a href="' + p[0] + '"' + (p[1] === page ? ' aria-current="page"' : '') + '>' + p[2] + '</a>' }).join('') + '</nav>' +
      '<button type="button" class="sbtn" id="sBtn" aria-expanded="false" aria-controls="sPanel" aria-label="Suchen">' + LUPE + '</button></div></header>' +
      '<div class="search" id="sPanel" role="search" hidden><div class="wrap"><label class="vh" for="sIn">Suche in News, Agenda und Amtlichem</label>' +
      '<div class="sfield">' + LUPE + '<input id="sIn" type="search" placeholder="News, Anlässe, Amtliches durchsuchen" autocomplete="off" enterkeyhint="search">' +
      '<button type="button" class="sclose" id="sClose">Schliessen</button></div>' +
      '<p class="scount" id="sCount" aria-live="polite"></p><div class="sres" id="sRes"></div></div></div>' +
      '<div class="infobar"><div class="wrap"><div class="ibox">' +
      '<a class="iitem ilink" href="agenda/#heute"><span class="iic cal">' + IC.cal + '</span><span class="itx"><strong id="cntN">–</strong><span>heute</span></span>' +
      '<svg class="ichev" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></a>' +
      '</div></div></div>';
    var intro = $('intro'); if (intro) $('hdr').insertBefore(intro, $('hdr').querySelector('.infobar'));
    $('ftr').innerHTML =
      '<footer><div class="wrap"><div class="col"><span style="font-family:var(--display);font-weight:800;font-size:22px;color:var(--fg)">zug<span style="color:var(--red)">.</span>now</span>' +
      '<span>Unabhängig. Automatisch aktualisiert. Jede Meldung mit Quelle und Link zum Original.</span>' +
      '</div>' +
      '<div class="col"><span style="font-weight:600;color:var(--fg)">Quellen</span><span>stadtzug.ch · veranstaltungen.zug.ch · amtsblatt.zg.ch · Kulturhäuser · kinozug.ch · eventfrog.ch · Open-Meteo</span><span id="srcState"></span></div></div></footer>';
  }

  function band() {
    var tk = todayKey(), n = D.events.filter(function (e) { return parts(e.start).key === tk && !e.cancelled && !over(e) }).length;
    var st = D.meta.sources || {}, bad = Object.keys(st).filter(function (k) { return !st[k].ok });
    $('srcState').innerHTML = bad.length ? '<span class="err">Quelle gestört: ' + esc(bad.join(', ')) + ' (letzter Stand wird angezeigt)</span>' : '';
    wkWx();
    if (!$('cntN')) return; // Infoleiste nur auf der Startseite
    $('cntN').textContent = n + (n === 1 ? ' Anlass' : ' Anlässe');
  }

  // Wetter nur dort, wo es bei der Entscheidung hilft: im Wochenend-Reiter und auf /wochenende/ (seit 7.11.2026)
  function wkWx() {
    var els = document.querySelectorAll('.wkwx'); if (!els.length) return;
    var r = range('wochenende');
    fetch('https://api.open-meteo.com/v1/forecast?latitude=47.166&longitude=8.516&daily=weather_code,temperature_2m_max,temperature_2m_min&forecast_days=8&timezone=Europe%2FZurich')
      .then(function (x) { return x.json() }).then(function (j) {
        var d = j && j.daily; if (!d || !d.time) return;
        var h = d.time.map(function (t, i) { return [t, t, i] }).filter(function (x) { return x[0] >= r[0] && x[0] <= r[1] }).map(function (x) {
          var i = x[2], w = wxOf(d.weather_code[i], 1), dw = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'][new Date(x[1] + 'T12:00:00').getDay()];
          return '<span class="wkd" title="' + esc(w[1]) + '"><b>' + dw + '</b>' + IC[w[0]] + '<span>' + esc(w[1]) + '</span><span>' +
            Math.round(d.temperature_2m_max[i]) + '° / ' + Math.round(d.temperature_2m_min[i]) + '°</span></span>';
        }).join('');
        if (!h) return;
        els.forEach(function (el) { el.innerHTML = h; el.hidden = false });
      }).catch(function () { });
  }

  // ---------- Bausteine
  function leadNews() { return D.news.filter(function (x) { return x.image })[0] || D.news[0] }

  function renderLead() {
    var n = leadNews(), el = $('lead'); if (!el) return;
    if (!n) { el.innerHTML = '<h2>Keine Meldungen</h2>'; return }
    el.innerHTML = '<div class="ph" style="aspect-ratio:16/9;position:relative">' + img(n.image) + (n.image ? '<span class="credit">Bild: Stadt Zug</span>' : '') + '</div>' +
      '<span class="eyebrow">Stadt Zug · ' + esc(n.type || 'News') + ' · ' + dLabel(n.date) + '</span>' +
      '<h2><a href="' + esc(n.url) + '">' + esc(n.title) + '</a></h2><p>' + esc(n.lead) + '</p>' +
      '<a href="' + esc(n.url) + '" style="font-weight:600;font-size:15px">Zur Meldung auf stadtzug.ch →</a>';
  }

  var hDay = 'heute';
  var HDAYS = [['heute', 'Heute'], ['morgen', 'Morgen'], ['wochenende', 'Wochenende']];
  var CATICON = {"kultur": "<path d='M9 18V5l12-2v13'/><circle cx='6' cy='18' r='3'/><circle cx='18' cy='16' r='3'/>", "kinder": "<circle cx='12' cy='7' r='3'/><path d='M5 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2'/>", "sport": "<path d='M3 20l6-10 4 6 3-4 5 8z'/><circle cx='17' cy='6' r='2'/>", "treff": "<path d='M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z'/>", "maerkte": "<path d='M3 9l2-5h14l2 5'/><path d='M4 9h16v11H4z'/><path d='M9 20v-6h6v6'/>", "weitere": "<rect x='3' y='5' width='18' height='16' rx='2'/><path d='M16 3v4M8 3v4M3 11h18'/>"};
  function catTile(e) { var c = CATICON[e.cat] ? e.cat : 'weitere'; return '<div class="tim nob c-' + c + '"><svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + CATICON[c] + '</svg><span>' + esc(e.catLabel) + '</span></div>' }
  function renderToday() {
    var el = $('todayList'); if (!el) return;
    var seg = $('hSeg');
    if (seg && !seg.children.length) {
      seg.innerHTML = HDAYS.map(function (d) { return '<button type="button" class="segb" data-d="' + d[0] + '">' + d[1] + '</button>' }).join('');
      seg.onclick = function (ev) { var b = ev.target.closest('.segb'); if (!b) return; hDay = b.dataset.d; renderToday(); el.scrollLeft = 0 };
    }
    if (seg) [].forEach.call(seg.children, function (b) { b.setAttribute('aria-pressed', b.dataset.d === hDay) });
    var tk = todayKey(), src = D.events.filter(function (e) { return !e.cancelled && parts(e.start).key >= tk && !over(e) });
    var sel = src.filter(function (e) { return inTime(e, hDay) });
    var list = sel.slice(0, hDay === 'heute' ? 12 : 18), filled = false;
    // Wenig los heute: mit den nächsten Anlässen auffüllen (mit Tag angeschrieben)
    if (hDay === 'heute' && list.length < 6) { list = list.concat(src.filter(function (e) { return parts(e.start).key > tk }).slice(0, 6 - list.length + (list.length ? 0 : 3))); filled = !sel.length }
    // Anlässe mit Bild zuerst, innerhalb chronologisch
    list = list.filter(function (e) { return e.image }).concat(list.filter(function (e) { return !e.image }));
    $('hTitle').textContent = 'Agenda';
    if ($('hMore')) $('hMore').href = 'agenda/#' + hDay;
    el.setAttribute('aria-label', 'Anlässe ' + { heute: 'heute', morgen: 'morgen', wochenende: 'am Wochenende' }[hDay]);
    var oneDay = hDay !== 'wochenende';
    el.innerHTML = list.map(function (e) {
      var p = parts(e.start), t = e.allday ? 'ganztags' : p.hm;
      return '<a class="tcard" href="' + esc(evHref(e)) + '">' + (e.image ? '<div class="tim">' + img(e.image) + '</div>' : catTile(e)) +
        '<div class="tb"><span class="tm">' + (oneDay && inTime(e, hDay) ? t : dShort(p.key) + ' · ' + t) + '</span><strong>' + esc(e.title) + '</strong>' +
        '<span class="ts"><span>' + esc(e.place) + ' · ' + esc(e.catLabel) + '</span><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></span></div></a>';
    }).join('') || '<p style="color:var(--soft)">Noch keine Anlässe gemeldet.</p>';
    swiper(el, $('tPrev'), $('tNext'));
  }
  // Pfeile für wischbare Leisten
  function swiper(el, prev, next) {
    if (!prev || !next) return;
    function step() { var c = el.querySelector('.tcard'); return c ? c.getBoundingClientRect().width + 20 : el.clientWidth }
    function upd() { prev.disabled = el.scrollLeft < 4; next.disabled = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4 }
    prev.onclick = function () { el.scrollBy({ left: -step(), behavior: 'smooth' }) };
    next.onclick = function () { el.scrollBy({ left: step(), behavior: 'smooth' }) };
    if (!el._sw) { el._sw = 1; el.addEventListener('scroll', function () { el._upd() }, { passive: true }); window.addEventListener('resize', function () { el._upd() }) }
    el._upd = upd; upd();
  }

  function renderWeekend() {
    var el = $('wkCards'); if (!el) return;
    var list = D.events.filter(function (e) { return inTime(e, 'wochenende') && !e.cancelled });
    // Bilder zuerst, pro Titel nur einmal
    var seen = {}, pick = [];
    list.filter(function (e) { return e.image }).concat(list.filter(function (e) { return !e.image })).forEach(function (e) { if (!seen[e.title] && pick.length < 6) { seen[e.title] = 1; pick.push(e) } });
    pick.sort(function (a, b) { return a.start < b.start ? -1 : 1 });
    if ($('wkBadgeN')) $('wkBadgeN').textContent = list.length + (list.length === 1 ? ' Anlass →' : ' Anlässe →');
    var r = range('wochenende'); $('wkTitle').textContent = r[0] === todayKey() && dowOf(r[0]) === 0 ? 'Heute, Sonntag' : 'Dieses Wochenende';
    el.innerHTML = pick.map(function (e) {
      var p = parts(e.start);
      return '<a href="' + esc(evHref(e)) + '"><div class="ph">' + img(e.image) + '<span class="when">' + dShort(p.key) + ' · ' + (e.allday ? 'ganztags' : p.hm) + '</span></div><span class="eyebrow">' + esc(e.catLabel) + '</span><strong>' + esc(e.title) + '</strong><span class="s">' + esc(e.place) + '</span></a>'
    }).join('') || '<p style="color:var(--soft)">Für dieses Wochenende sind noch keine Anlässe gemeldet.</p>';
  }

  function newsRow(n) {
    var mm = /Medien/.test(n.type || '');
    return '<a href="' + esc(n.url) + '" class="' + (n.image ? 'img' : '') + '"><span class="d"><b class="' + (mm ? 'mm' : '') + '">' + esc(n.type || 'News') + '</b>' + dLabel(n.date) + (n.topicLabel ? '<i class="ntop">' + esc(n.topicLabel) + '</i>' : '') + '</span>' +
      '<span class="c"><span class="t">' + esc(n.title) + '</span><span class="l">' + esc(n.lead) + '</span></span>' +
      (n.image ? '<span class="i">' + img(n.image) + '</span>' : '') + '</a>';
  }
  var CHEVR = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
  var EXT = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg>';
  function dMini(key) { var p = key.split('-'); return +p[2] + '.' + (+p[1]) + '.' }
  function topicOf(n) { return !n.topicLabel || n.topic === 'weitere' ? 'Stadtleben' : n.topicLabel }
  function renderNewsTeaser() {
    var el = $('newsGrid'); if (!el) return;
    // «Das bewegt die Stadt Zug»: neueste Meldung mit Bild gross links, daneben die nächsten Meldungen (ohne Baugesuch-Listen)
    var pool = D.news.filter(function (n) { return !/^Baugesuche vom/i.test(n.title) });
    var lead = pool.filter(function (n) { return n.image })[0] || pool[0];
    if (!lead) { el.innerHTML = '<p style="color:var(--soft)">Keine Meldungen.</p>'; return }
    var rest = pool.filter(function (n) { return n !== lead }).slice(0, 3);
    el.innerHTML = '<a class="blead" href="' + esc(lead.url) + '">' + (lead.image ? '<div class="bim">' + img(lead.image) + '</div>' : '') +
      '<div class="bb"><span class="beye">' + esc(topicOf(lead)) + ' · ' + dLabel(lead.date) + '</span><strong>' + esc(lead.title) + '</strong>' +
      (lead.lead ? '<span class="bl">' + esc(lead.lead) + '</span>' : '') +
      '<span class="bsrc">' + esc(lead.type || 'News') + ' · Stadt Zug ' + EXT + '</span></div></a>' +
      '<div class="blist">' + rest.map(function (n) {
        return '<a href="' + esc(n.url) + '"><span class="bc"><span class="beye">' + esc(topicOf(n)) + ' · ' + dMini(n.date) + '</span><strong>' + esc(n.title) + '</strong>' +
          (n.lead ? '<span class="bl">' + esc(n.lead) + '</span>' : '') + '<span class="bsrc">Stadt Zug ' + EXT + '</span></span>' +
          (n.image ? '<span class="bth">' + img(n.image) + '</span>' : '') + '</a>';
      }).join('') + '</div>';
  }
  var NTOPICS = [['alle', 'Alle'], ['politik', 'Politik & Verwaltung'], ['bauen', 'Bauen & Planung'], ['mobilitaet', 'Mobilität & Verkehr'], ['bildung', 'Bildung & Schule'], ['kultur', 'Kultur & Freizeit'], ['umwelt', 'Umwelt & Energie'], ['soziales', 'Soziales & Gesundheit'], ['weitere', 'Weitere']];
  // Themen-Kacheln (Startseite) → News-Seite mit Filter
  var TICON = {
    politik: '<path d="M4 20h16M5 17h14M6 17V10M10 17V10M14 17V10M18 17V10M3.5 9.5L12 4l8.5 5.5z"/>',
    bauen: '<path d="M4 21V9l6-3v15M10 21V11h8v10M3 21h18M13 14h2M13 17h2M6.5 12h1M6.5 15h1"/>',
    mobilitaet: '<circle cx="6" cy="16" r="3.5"/><circle cx="18" cy="16" r="3.5"/><path d="M6 16l4-7h5l3 7M10 9l2 7h-6M14 6h2.5"/>',
    bildung: '<path d="M2.5 9L12 4.5 21.5 9 12 13.5z"/><path d="M6.5 11v4.5c0 1.5 2.5 3 5.5 3s5.5-1.5 5.5-3V11M21.5 9v5"/>',
    kultur: '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    umwelt: '<path d="M5 19c0-8 5-13 15-14-1 10-6 15-14 15M5 19l8-8"/>',
    soziales: '<circle cx="9" cy="8" r="3.2"/><circle cx="17" cy="9" r="2.6"/><path d="M3 19c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5M15.5 13.6c2.7.1 4.8 2 5.3 5.4"/>'
  };
  function renderThemes() {
    var el = $('themes'); if (!el) return;
    el.innerHTML = NTOPICS.filter(function (t) { return TICON[t[0]] }).map(function (t) {
      var n = D.news.filter(function (x) { return x.topic === t[0] }).length;
      return '<a class="theme th-' + t[0] + '" href="news/#' + t[0] + '"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + TICON[t[0]] + '</svg>' +
        '<span class="tn">' + t[1] + '</span><span class="tc">' + (n ? n + (n === 1 ? ' Meldung' : ' Meldungen') : 'aktuell keine') + '</span></a>';
    }).join('');
  }
  function renderNewsPage() {
    var el = $('newsList'); if (!el) return;
    var h = location.hash.slice(1); if (NTOPICS.some(function (t) { return t[0] === h })) st.ntopic = h;
    st.ntopic = st.ntopic || 'alle';
    function cnt(v) { return D.news.filter(function (n) { return v === 'alle' || n.topic === v }).length }
    var ch = $('topicChips');
    if (ch) {
      ch.innerHTML = NTOPICS.filter(function (d) { return d[0] === 'alle' || cnt(d[0]) }).map(function (d) {
        return '<button type="button" class="chip" data-v="' + d[0] + '" aria-pressed="' + (st.ntopic === d[0]) + '">' + d[1] + '<span class="n">' + cnt(d[0]) + '</span></button>'
      }).join('');
      ch.onclick = function (ev) { var b = ev.target.closest('.chip'); if (!b) return; st.ntopic = b.dataset.v; history.replaceState(null, '', location.pathname + (st.ntopic === 'alle' ? '' : '#' + st.ntopic)); renderNewsPage() };
    }
    el.innerHTML = D.news.filter(function (n) { return st.ntopic === 'alle' || n.topic === st.ntopic }).map(newsRow).join('') || '<p style="color:var(--soft);padding:18px 0">Keine Meldungen in dieser Kategorie.</p>';
  }

  function laufItems() {
    var seen = {}, items = [];
    D.ongoing.forEach(function (e) {
      var k = e.title + '|' + e.place;
      if (seen[k]) { seen[k].rh.push(e.rhythm); if (!seen[k].image && e.image) seen[k].image = e.image; if ((e.until || '') > (seen[k].until || '')) seen[k].until = e.until; return }
      seen[k] = { e: e, rh: [e.rhythm], image: e.image, until: e.until }; items.push(seen[k]);
    });
    return items;
  }
  function renderLauf(max) {
    var el = $('laufGrid'); if (!el) return;
    var items = laufItems(); if (!items.length) { $('laufend').hidden = true; return }
    el.innerHTML = items.slice(0, max || 99).map(function (x) {
      var e = x.e, rh = x.rh.filter(Boolean).join(' · ') || timeLabel(e), bis = x.until && x.until < '2028' ? 'bis ' + dLabel(x.until) : 'Dauerangebot';
      return '<a href="' + esc(e.url) + '"><div class="ph">' + img(x.image) + '</div><span class="eyebrow">' + esc(e.place) + '</span><strong>' + esc(e.title) + '</strong><span>' + esc(rh) + ' · ' + bis + '</span></a>';
    }).join('');
  }

  function amtItem(a) { return '<a href="' + esc(a.url) + '"><span class="lbl' + (a.label === 'Abstimmung' ? ' red' : '') + '">' + esc(a.label) + ' · ' + dLabel(a.date) + '</span><span>' + esc(a.title) + '</span></a>' }
  function renderAmtTeaser() { var el = $('amtRow'); if (el) el.innerHTML = D.amtlich.slice(0, 3).map(amtItem).join('') || '<p style="color:var(--soft)">Keine aktuellen Publikationen.</p>' }
  function renderAmtPage() {
    var el = $('amtList'); if (!el) return;
    el.innerHTML = D.amtlich.map(function (a) {
      return '<a href="' + esc(a.url) + '"><span class="d">' + dLabel(a.date) + '</span><span class="t"><span class="lbl" style="display:block;margin-bottom:2px">' + esc(a.label) + '</span>' + esc(a.title) + '</span><span class="o">' + esc(a.office) + (a.expires ? ' · einsehbar bis ' + dLabel(a.expires) : '') + '</span></a>';
    }).join('') || '<p style="color:var(--soft)">Keine aktuellen Publikationen.</p>';
  }

  // ---------- Agenda-Seite
  var st = { time: 'alle', cat: 'alle', place: 'alle', days: 14, open: {} };
  function filtered() { return D.events.filter(function (e) { return inTime(e, st.time) && (st.cat === 'alle' || e.cat === st.cat) && (st.place === 'alle' || e.institution === st.place) }) }
  function chipRow(id, defs, key, count) {
    var el = $(id);
    el.innerHTML = defs.filter(function (d) { return d[0] === 'alle' || count(d[0]) || st[key] === d[0] }).map(function (d) {
      return '<button type="button" class="chip" data-v="' + d[0] + '" aria-pressed="' + (st[key] === d[0]) + '">' + d[1] + '<span class="n">' + count(d[0]) + '</span></button>'
    }).join('');
    el.onclick = function (ev) { var b = ev.target.closest('.chip'); if (!b) return; st[key] = b.dataset.v; st.days = DAYS; st.open = {}; renderFilters(); renderList() };
  }
  function renderFilters() {
    chipRow('timeChips', TIMES, 'time', function (v) { return D.events.filter(function (e) { return inTime(e, v) && (st.cat === 'alle' || e.cat === st.cat) && (st.place === 'alle' || e.institution === st.place) }).length });
    chipRow('catChips', CATS, 'cat', function (v) { return D.events.filter(function (e) { return inTime(e, st.time) && (v === 'alle' || e.cat === v) && (st.place === 'alle' || e.institution === st.place) }).length });
    chipRow('placeChips', PLACES, 'place', function (v) { return D.events.filter(function (e) { return inTime(e, st.time) && (st.cat === 'alle' || e.cat === st.cat) && (v === 'alle' || e.institution === v) }).length });
  }

  function icsDate(iso) { return new Date(iso).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '') }
  function icsEsc(s) { return String(s || '').replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;') }
  function icsHref(e) {
    var end = e.end || new Date(new Date(e.start).getTime() + 36e5).toISOString();
    var L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//zug.now//DE', 'BEGIN:VEVENT', 'UID:' + e.id + '@zug.now', 'DTSTAMP:' + icsDate(new Date().toISOString()),
      'DTSTART:' + icsDate(e.start), 'DTEND:' + icsDate(end), 'SUMMARY:' + icsEsc(e.title), 'LOCATION:' + icsEsc(e.location), 'DESCRIPTION:' + icsEsc((e.teaser || '') + '\n\n' + e.url), 'URL:' + e.url, 'END:VEVENT', 'END:VCALENDAR'];
    return 'data:text/calendar;charset=utf-8,' + encodeURIComponent(L.join('\r\n'));
  }
  var CAL = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M3 10h18M8 3v4M16 3v4"></path></svg>';
  var LUPE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="M15.5 15.5L20 20"></path></svg>';
  // Wetter-Codes von Open-Meteo (WMO) → Symbol und Text
  function wxOf(c, day) {
    if (c === 0) return day ? ['sun', 'Sonnig'] : ['moon', 'Klar'];
    if (c === 1 || c === 2) return [day ? 'part' : 'moon', c === 1 ? 'Meist sonnig' : 'Teilweise bewölkt'];
    if (c === 3) return ['cloud', 'Bewölkt'];
    if (c === 45 || c === 48) return ['fog', 'Nebel'];
    if (c >= 51 && c <= 57) return ['rain', 'Nieselregen'];
    if ((c >= 61 && c <= 67) || (c >= 80 && c <= 82)) return ['rain', c >= 80 ? 'Regenschauer' : 'Regen'];
    if ((c >= 71 && c <= 77) || c === 85 || c === 86) return ['snow', 'Schnee'];
    if (c >= 95) return ['storm', 'Gewitter'];
    return ['cloud', 'Bewölkt'];
  }
  var SUN = '<g stroke="#F2B134" stroke-width="2.4" stroke-linecap="round"><path d="M24 4v5M24 39v5M4 24h5M39 24h5M9.9 9.9l3.5 3.5M34.6 34.6l3.5 3.5M9.9 38.1l3.5-3.5M34.6 13.4l3.5-3.5"/></g><circle cx="24" cy="24" r="9" fill="#F2B134"/>';
  var CLOUD = '<path d="M15 38h20a8 8 0 0 0 .6-16A11 11 0 0 0 14.4 25 6.5 6.5 0 0 0 15 38z" fill="#B7C3D0"/>';
  function svg(inner) { return '<svg viewBox="0 0 48 48" width="44" height="44" aria-hidden="true">' + inner + '</svg>' }
  var IC = {
    sun: svg(SUN),
    moon: svg('<path d="M30 8a16 16 0 1 0 10 26A13 13 0 0 1 30 8z" fill="#F2C55C"/>'),
    part: svg('<g transform="translate(-6 -6) scale(.8)">' + SUN + '</g><path d="M17 40h18a7 7 0 0 0 .5-14A9.5 9.5 0 0 0 17.3 28.6 5.8 5.8 0 0 0 17 40z" fill="#B7C3D0"/>'),
    cloud: svg(CLOUD),
    fog: svg('<g stroke="#9DAAB8" stroke-width="3" stroke-linecap="round"><path d="M8 18h32M12 26h28M8 34h26"/></g>'),
    rain: svg('<g transform="translate(0 -6)">' + CLOUD + '</g><g stroke="#4F8FE0" stroke-width="2.6" stroke-linecap="round"><path d="M17 37l-2 5M25 37l-2 5M33 37l-2 5"/></g>'),
    snow: svg('<g transform="translate(0 -6)">' + CLOUD + '</g><g fill="#8FB6EA"><circle cx="16" cy="40" r="2"/><circle cx="24" cy="43" r="2"/><circle cx="32" cy="40" r="2"/></g>'),
    storm: svg('<g transform="translate(0 -6)">' + CLOUD + '</g><path d="M25 32l-5 8h5l-2 6 7-9h-5l3-5z" fill="#F2B134"/>'),
    cal: '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4M8.5 14v3M12 14v3M15.5 14v3"/></svg>'
  };
  var CHEV = '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>';

  function evRow(e) {
    var p = parts(e.start), slug = (e.title || 'anlass').toLowerCase().replace(/[^a-z0-9äöü]+/g, '-').slice(0, 40);
    return '<details class="ev" id="ev-' + esc(e.id) + '"><summary><div class="date" aria-label="' + dLabel(p.key) + '"><span class="wd">' + WD[p.dow] + '</span><span class="d">' + p.d + '</span><span class="mo">' + MO[p.m - 1] + '</span></div>' +
      (e.image ? '<div class="thumb">' + img(e.image) + '</div>' : '') +
      '<div class="evmain"><span class="ttl">' + esc(e.title) + '</span><span class="meta">' + timeLabel(e) + (e.rhythm ? ' · ' + esc(e.rhythm) : '') + ' · ' + esc(e.place) + '</span></div>' +
      '<div class="evside">' + (e.cancelled ? '<span class="tag off">Abgesagt</span>' : '<span class="tag">' + esc(e.catLabel) + '</span>') + '<small>Quelle: ' + esc(e.source) + '</small></div>' + CHEV + '</summary>' +
      '<div class="panel' + (e.image ? ' withimg' : '') + '"><div style="display:flex;flex-direction:column;gap:14px;min-width:0">' +
      '<p>' + esc(e.text || e.teaser || 'Keine Beschreibung vorhanden.') + '</p><span class="facts">' + esc(e.location) + '</span>' +
      '<div class="actions">' + (e.page ? '<a class="btn primary" href="' + esc(e.page) + '">Details →</a><a class="btn" href="' + esc(e.url) + '">Zur Quelle ↗</a>' : '<a class="btn primary" href="' + esc(e.url) + '">Zum Anlass →</a>') + (e.cancelled ? '' : '<a class="btn" href="' + icsHref(e) + '" download="' + esc(slug) + '.ics">' + CAL + 'In Kalender</a>') + '</div>' +
      '</div>' + (e.image ? '<div class="pimg">' + img(e.image) + '</div>' : '') + '</div></details>';
  }

  // Agenda nach Tagen gruppiert, Tage auf- und zuklappbar (7.11.2026)
  var DAYS = 14, WDF = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'], MOF = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  function dayOpen(k, i, n) { return k in st.open ? st.open[k] : (i === 0 || n <= 2) }
  function dayGroup(k, evs, i, n) {
    var p = k.split('-'), tk = todayKey(), rel = k === tk ? 'Heute' : k === addDays(tk, 1) ? 'Morgen' : '';
    var pv = evs.slice(0, 4).map(function (e) { return '<span class="pv">' + esc(e.title) + '</span>' }).join('');
    return '<details class="aday" data-day="' + k + '"' + (dayOpen(k, i, n) ? ' open' : '') + '><summary><div class="date" aria-label="' + dLabel(k) + '"><span class="wd">' + WD[dowOf(k)] + '</span><span class="d">' + (+p[2]) + '</span><span class="mo">' + MO[+p[1] - 1] + '</span></div>' +
      '<div class="dpv"><span class="dfull">' + WDF[dowOf(k)] + ', ' + (+p[2]) + '. ' + MOF[+p[1] - 1] + ' ' + p[0] + '</span><span class="pvs">' + pv + '</span></div><div class="dn">' + (rel ? '<span class="rel">' + rel + '</span>' : '') + '<strong>' + evs.length + (evs.length === 1 ? ' Anlass' : ' Anlässe') + '</strong></div>' + CHEV + '</summary>' +
      '<div class="dbody">' + evs.map(evRow).join('').replace(/<details class="ev"/g, '<details class="ev same"') + '</div></details>';
  }
  function byDay(list) { var g = [], m = {}; list.forEach(function (e) { var k = parts(e.start).key; if (!m[k]) { m[k] = []; g.push([k, m[k]]) } m[k].push(e) }); return g }
  function renderList() {
    var list = filtered(), lbl = { alle: 'in den nächsten 60 Tagen', heute: 'heute', morgen: 'morgen', wochenende: 'am Wochenende', woche: 'diese Woche' }[st.time];
    $('agCount').textContent = list.length + (list.length === 1 ? ' Anlass ' : ' Anlässe ') + lbl;
    var g = byDay(list), el = $('agList');
    el.innerHTML = g.slice(0, st.days).map(function (x, i) { return dayGroup(x[0], x[1], i, g.length) }).join('') || '<p style="color:var(--soft);padding:18px 40px">Keine Anlässe für diese Auswahl.</p>';
    if (!el._tg) { el._tg = 1; el.addEventListener('toggle', function (ev) { var d = ev.target; if (d.classList && d.classList.contains('aday')) st.open[d.dataset.day] = d.open }, true) }
    var m = $('more'), rest = g.length - st.days; m.hidden = rest <= 0; m.textContent = 'Weitere ' + Math.min(DAYS, rest) + ' Tage anzeigen';
    m.onclick = function () { st.days += DAYS; renderList() };
  }

  function agendaFromHash() {
    var h = location.hash.slice(1);
    if (TIMES.some(function (t) { return t[0] === h })) { st.time = h; return null }
    if (h.indexOf('ev-') === 0) return h.slice(3);
    return null;
  }
  function openEvent(id) {
    var ev = filtered().filter(function (e) { return e.id === id })[0]; if (!ev) return;
    var k = parts(ev.start).key, i = byDay(filtered()).findIndex(function (x) { return x[0] === k });
    st.days = Math.max(st.days, Math.ceil((i + 1) / DAYS) * DAYS); st.open[k] = true; renderList();
    var el = $('ev-' + id); if (el) { el.open = true; el.scrollIntoView({ block: 'start' }) }
  }


  // ---------- Politik
  var MON = { januar: 1, februar: 2, märz: 3, maerz: 3, april: 4, mai: 5, juni: 6, juli: 7, august: 8, september: 9, oktober: 10, november: 11, dezember: 12 };
  var DOM = { federation: 'Bund', canton: 'Kanton', region: 'Region', municipality: 'Stadt Zug' };
  function pad(n) { return String(n).padStart(2, '0') }
  function sessionDate(t) { // «… GGR vom 12.11.2026» oder «… vom 20. Oktober 2026»
    var m = /vom (\d{1,2})\.(\d{1,2})\.(\d{4})/.exec(t); if (m) return m[3] + '-' + pad(m[2]) + '-' + pad(m[1]);
    m = /vom (\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})/.exec(t); if (m && MON[m[2].toLowerCase()]) return m[3] + '-' + pad(MON[m[2].toLowerCase()]) + '-' + pad(m[1]);
    return null;
  }
  function dLong(key) { var p = key.split('-'); return WDL[dowOf(key)] + ', ' + (+p[2]) + '.' + (+p[1]) + '.' + p[0] }
  function polRow(r) {
    return '<a href="' + esc(r.url) + '"><span class="d"><b class="' + (r.red ? 'mm' : '') + '">' + esc(r.lbl) + '</b>' + dLabel(r.date) + '</span>' +
      '<span class="c"><span class="t">' + esc(r.title) + '</span>' + (r.sub ? '<span class="l">' + esc(r.sub) + '</span>' : '') + '</span></a>';
  }
  function bar(label, pct, ans) {
    if (pct == null) return '<div class="vbar"><span class="vl">' + label + '</span><span class="vt muted">noch offen</span></div>';
    return '<div class="vbar"><span class="vl">' + label + '</span><span class="vtrack" role="img" aria-label="' + label + ': ' + pct.toLocaleString('de-CH') + ' % Ja"><span style="width:' + pct + '%"></span></span>' +
      '<span class="vt"><b class="' + (ans === 'accepted' ? 'yes' : 'no') + '">' + (ans === 'accepted' ? 'Ja' : 'Nein') + '</b> ' + pct.toLocaleString('de-CH') + ' %</span></div>';
  }
  function renderPolitik(P) {
    var L = P.links || {}, tk = todayKey();
    // Nächste GGR-Sitzung aus den Meldungen der Stadt
    var sess = D.pol.news.map(function (n) { return { d: sessionDate(n.title), n: n } }).filter(function (x) { return x.d && x.d >= tk && /Sitzung/.test(x.n.title) })
      .sort(function (a, b) { return a.d < b.d ? -1 : 1 })[0];
    var nv = P.nextVoteDate, up = (P.upcoming || []).filter(function (v) { return v.date === nv });
    $('polTiles').innerHTML =
      '<a class="ptile dark" href="' + esc(sess ? sess.n.url : L.livestream) + '"><span class="pk">Nächste GGR-Sitzung</span><strong>' + (sess ? dLong(sess.d) : 'Termin folgt') + '</strong>' +
        '<span>Kantonsratssaal · öffentlich mit Livestream</span><em>' + (sess ? 'Traktanden ansehen →' : 'Zum Livestream →') + '</em></a>' +
      '<a class="ptile" href="politik/#pAbst"><span class="pk">Nächste Abstimmung</span><strong>' + (nv ? dLong(nv) : 'Termin folgt') + '</strong>' +
        '<span>' + (up.length ? up.length + (up.length === 1 ? ' Vorlage' : ' Vorlagen') : 'Vorlagen werden aufgeschaltet') + '</span><em>Zu den Abstimmungen →</em></a>' +
      '<a class="ptile" href="' + esc(L.wahlen) + '"><span class="pk">Neue Legislatur</span><strong>' + esc((P.ggr || {}).legislatur || '2027–2030') + '</strong>' +
        '<span>Gewählt am 4. Oktober 2026</span><em>Wahlresultate →</em></a>';
    // Aus dem Parlament: Meldungen der Stadt + Publikationen im Amtsblatt
    var rows = D.pol.news.map(function (n) { return { date: n.date, lbl: n.type || 'News', red: /Medien/.test(n.type || ''), title: n.title, sub: n.lead, url: n.url } })
      .concat(D.pol.amt.map(function (a) { return { date: a.date, lbl: 'Amtsblatt · ' + a.label, title: a.title, sub: '', url: a.url } }))
      .sort(function (a, b) { return a.date < b.date ? 1 : -1 });
    $('polParl').innerHTML = rows.slice(0, 8).map(polRow).join('') || '<p class="note">Zurzeit keine Meldungen.</p>';
    $('pRis').href = L.ris || '#';
    $('polLinks').innerHTML = [[L.ris, 'Geschäfte & Vorstösse (Ratsinfo)'], [L.vorstoesse, 'Hängige Vorstösse'], [L.personen, 'Ratsmitglieder'], [L.livestream, 'Livestream & Archiv']]
      .filter(function (x) { return x[0] }).map(function (x) { return '<a class="btn" href="' + esc(x[0]) + '">' + x[1] + ' ' + EXT + '</a>' }).join('');
    // Sitzverteilung als Halbkreis; Klick auf Partei hebt Sitze hervor und filtert «Aus den Parteien»
    var g = P.ggr || { parteien: [] }, ORD = ['ALG-CSP', 'SP', 'GLP', 'Die Mitte', 'FDP', 'SVP'];
    var PCODE = { 'ALG-CSP': ['ALG', 'CSP'], 'Die Mitte': ['Mitte'] };
    var parts = g.parteien.slice().sort(function (a, b) { var i = ORD.indexOf(a[0]), j = ORD.indexOf(b[0]); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j) });
    function hemi(sel) {
      var n = parts.reduce(function (s, p) { return s + p[1] }, 0), R = [0.48, 0.65, 0.82, 1], tot = R.reduce(function (a, b) { return a + b }, 0), seats = [], left = n;
      R.forEach(function (r, i) {
        var k = i === R.length - 1 ? left : Math.round(n * r / tot); left -= k;
        for (var j = 0; j < k; j++) { var a = Math.PI * (1 - (k === 1 ? .5 : j / (k - 1))); seats.push({ a: a, x: 150 + 132 * r * Math.cos(a), y: 146 - 132 * r * Math.sin(a) }) }
      });
      seats.sort(function (a, b) { return b.a - a.a });
      var out = '', idx = 0;
      parts.forEach(function (p) {
        var on = !sel || sel === p[0];
        for (var j = 0; j < p[1]; j++, idx++) { var s = seats[idx]; out += '<circle cx="' + s.x.toFixed(1) + '" cy="' + s.y.toFixed(1) + '" r="8.6" fill="' + p[3] + '" opacity="' + (on ? 1 : .18) + '"><title>' + esc(p[0]) + '</title></circle>' }
      });
      var cur = sel ? parts.filter(function (p) { return p[0] === sel })[0] : null;
      out += '<text x="150" y="128" text-anchor="middle" class="hnum">' + (cur ? cur[1] : n) + '</text><text x="150" y="146" text-anchor="middle" class="hlbl">' + esc(cur ? cur[0] : 'Sitze') + '</text>';
      return out;
    }
    var seatSel = null;
    function seatsRender() {
      $('polSeats').innerHTML = '<p class="psub">Legislatur ' + esc(g.legislatur) + ' · ' + g.sitze + ' Sitze · Partei antippen</p>' +
        '<svg class="hemi" viewBox="0 0 300 156" role="img" aria-label="Sitzverteilung: ' + esc(parts.map(function (p) { return p[0] + ' ' + p[1] }).join(', ')) + '">' + hemi(seatSel) + '</svg>' +
        '<ul class="seatl">' + parts.map(function (p) {
          return '<li><button type="button" data-p="' + esc(p[0]) + '" aria-pressed="' + (seatSel === p[0]) + '"><i style="background:' + p[3] + '"></i>' + esc(p[0]) + '<b>' + p[1] + '</b><span>' + (p[2] > 0 ? '+' + p[2] : p[2] < 0 ? '−' + (-p[2]) : '±0') + '</span></button></li>' }).join('') + '</ul>' +
        '<p class="psrc">' + esc(g.hinweis || '') + ' · Veränderung zu 2023–2026 · <a href="' + esc(g.quelle) + '">Quelle</a></p>';
    }
    $('polSeats').onclick = function (ev) {
      var b = ev.target.closest('button[data-p]'); if (!b) return;
      seatSel = seatSel === b.dataset.p ? null : b.dataset.p; seatsRender();
      pf = seatSel ? (PCODE[seatSel] || [seatSel]).join('|') : 'alle'; postsRender();
      if (typeof gesRender === 'function') { gTab = 'vorstoesse'; gMax = 10; gesRender() }
      if (seatSel) $('pGes').scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    seatsRender();
    $('polSr').innerHTML = '<ul class="srl">' + (P.stadtrat || []).map(function (r) {
      return '<li><span><b>' + esc(r[0]) + '</b>' + (r[2] ? ' · ' + esc(r[2]) : '') + '</span><span>' + esc(r[1]) + '</span></li>' }).join('') + '</ul>';
    // Abstimmungen
    $('pAbstA').href = L.abstimmungen || '#';
    var V = P.votes || [], html = '';
    if (nv) html += '<div class="vcard next"><span class="pk">Als Nächstes · ' + dLong(nv) + '</span>' +
      (up.length ? up.map(function (v) { return '<a href="' + esc(v.url) + '"><span class="vdom">' + (DOM[v.domain] || '') + '</span>' + esc(v.title) + '</a>' }).join('') : '<p>Die Vorlagen werden aufgeschaltet, sobald der Kanton sie publiziert.</p>') +
      '<p class="muted">Am Abstimmungssonntag erscheint hier das Resultat der Stadt Zug.</p></div>';
    html += V.map(function (v) {
      return '<div class="vcard"><span class="pk">' + (DOM[v.domain] || '') + ' · ' + dLabel(v.date) + '</span><a class="vt2" href="' + esc(v.url) + '">' + esc(v.title) + '</a>' +
        (v.city ? bar('Stadt Zug', v.city.yeas, v.city.answer) : '') + bar('Kanton Zug', v.yeas, v.answer) + '</div>' }).join('');
    $('polVotes').innerHTML = html ? '<div class="votes">' + html + '</div>' : '<p class="note">Resultate werden geladen, sobald wab.zug.ch erreichbar ist.</p>';
    // Parteien: Meldungen (RSS der Partei-Websites), chronologisch, alle gleich behandelt
    var posts = P.posts || [], pf = 'alle', LV = { Kanton: 'Kantonalpartei', Schweiz: 'Schweiz', Stadt: '' };
    function postsRender() {
      var with_ = (P.parteien || []).filter(function (p) { return posts.some(function (x) { return x.party === p[2] }) });
      $('polPChips').innerHTML = posts.length ? [['alle', 'Alle']].concat(with_.map(function (p) { return [p[2], p[2]] })).map(function (c) {
        return '<button type="button" class="chip" data-v="' + esc(c[0]) + '" aria-pressed="' + (pf === c[0] || (pf !== 'alle' && pf.split('|').indexOf(c[0]) >= 0)) + '">' + esc(c[1]) + '</button>' }).join('') : '';
      $('polPosts').innerHTML = posts.filter(function (x) { return pf === 'alle' || pf.split('|').indexOf(x.party) >= 0 }).slice(0, pf === 'alle' ? 12 : 99).map(function (x) {
        return '<a href="' + esc(x.url) + '"><span class="d"><b>' + esc(x.party) + '</b>' + dLabel(x.date) + (LV[x.level] ? '<i class="ntop">' + LV[x.level] + '</i>' : '') + '</span>' +
          '<span class="c"><span class="t">' + esc(x.title) + '</span>' + (x.lead ? '<span class="l">' + esc(x.lead) + '</span>' : '') + '<span class="psrc2">' + esc(x.partyName) + ' ' + EXT + '</span></span></a>' }).join('') ||
        '<p class="note">Noch keine Meldungen der Parteien gesammelt.</p>';
    }
    var miss = (P.parteien || []).filter(function (p) { return !posts.some(function (x) { return x.party === p[2] }) }).map(function (p) { return p[2] });
    $('polMiss').textContent = miss.length ? 'Zurzeit ohne Meldungen (nur nationale Website oder nichts Neues in den letzten 4 Monaten): ' + miss.join(', ') + '.' : '';
    $('polPChips').onclick = function (ev) { var b = ev.target.closest('.chip'); if (!b) return; pf = b.dataset.v; seatSel = null; seatsRender(); postsRender() };
    postsRender();
    // Geschäfte & Vorstösse (Ratsinfo)
    var G = P.geschaefte || { vorlagen: [], vorstoesse: [] }, gTab = 'vorstoesse', gMax = 10;
    var PORD = ['ALG-CSP', 'SP', 'GLP', 'Die Mitte', 'FDP', 'SVP'], PCOL = {};
    g.parteien.forEach(function (p) { PCOL[p[0]] = p[3] });
    function pBadge(p) { return '<span class="pbadge"><i style="background:' + (PCOL[p] || 'var(--soft)') + '"></i>' + esc(p) + '</span>' }
    function gesRender() {
      if (!G.vorlagen.length && !G.vorstoesse.length) { $('gesList').innerHTML = '<p class="note">Geschäfte werden beim nächsten Abgleich mit dem Ratsinfo geladen.</p>'; return }
      $('gesTabs').innerHTML = [['vorstoesse', 'Vorstösse', G.vorstoesse.length], ['vorlagen', 'Vorlagen des Stadtrats', G.vorlagen.length]].map(function (t) {
        return '<button type="button" class="chip" data-v="' + t[0] + '" aria-pressed="' + (gTab === t[0]) + '">' + t[1] + '<span class="n">' + t[2] + '</span></button>' }).join('');
      $('gesParty').hidden = gTab !== 'vorstoesse';
      $('gesParty').innerHTML = [['', 'Alle Parteien']].concat(PORD.map(function (p) { return [p, p] })).map(function (c) {
        return '<button type="button" class="chip" data-p="' + esc(c[0]) + '" aria-pressed="' + ((seatSel || '') === c[0]) + '">' + esc(c[1]) + '</button>' }).join('');
      var rows, html;
      if (gTab === 'vorstoesse') {
        rows = G.vorstoesse.filter(function (v) { return !seatSel || v.parteien.indexOf(seatSel) >= 0 || v.parteien.indexOf('Alle Fraktionen') >= 0 });
        html = rows.slice(0, gMax).map(function (v) {
          return '<a class="gr" href="' + esc(v.answer ? v.answer.url : v.url) + '"><span class="d">' + dLabel(v.touched || v.date) + '</span><span class="c">' +
            '<span class="gk"><b>' + esc(v.art) + '</b>' + v.parteien.map(pBadge).join('') + '</span><span class="t">' + esc(v.title) + '</span>' +
            '<span class="gs ' + v.tone + '">' + esc(v.status) + '</span></span></a>' }).join('');
      } else {
        rows = G.vorlagen;
        html = rows.slice(0, gMax).map(function (v) {
          var st = v.steps.map(function (s) { return '<li class="on">' + esc(s.label) + '</li>' }).join('') + '<li>Parlament</li>';
          return '<a class="gr" href="' + esc(v.url) + '"><span class="d">' + dLabel(v.date) + '</span><span class="c"><span class="gk"><b>' + esc(v.bereich || 'Vorlage') + '</b><span class="muted">Nr. ' + esc(v.nr) + '</span></span>' +
            '<span class="t">' + esc(v.title) + '</span><ol class="gway">' + st + '</ol></span></a>' }).join('');
      }
      $('gesList').innerHTML = (html || '<p class="note">Keine Geschäfte für diese Auswahl.</p>') +
        (rows.length > gMax ? '<button type="button" class="btn gmore">Weitere ' + Math.min(10, rows.length - gMax) + ' anzeigen</button>' : '');
      $('gesCount').textContent = rows.length + (gTab === 'vorstoesse' ? ' Vorstösse' : ' Vorlagen') + (seatSel && gTab === 'vorstoesse' ? ' · ' + seatSel : '') + ' · Ratsinfo';
    }
    $('gesTabs').onclick = function (ev) { var b = ev.target.closest('.chip'); if (!b) return; gTab = b.dataset.v; gMax = 10; gesRender() };
    $('gesParty').onclick = function (ev) { var b = ev.target.closest('.chip'); if (!b) return; seatSel = b.dataset.p || null; gMax = 10; seatsRender(); gesRender() };
    $('gesList').onclick = function (ev) { if (ev.target.closest('.gmore')) { gMax += 10; gesRender() } };
    gesRender();
    $('polParties').innerHTML = (P.parteien || []).map(function (p) { return '<a href="' + esc(p[1]) + '"><strong>' + esc(p[0]) + '</strong><span>Website ' + EXT + '</span></a>' }).join('');
  }

  // ---------- Kino (kinozug.ch): heute noch kommende Vorstellungen, sonst nächster Spieltag
  function niceTitle(t) { return t === t.toUpperCase() ? t.toLowerCase().replace(/(^|[\s\-–(:"„/&])(\p{L})/gu, function (m, a, b) { return a + b.toUpperCase() }) : t }
  function renderKino(K) {
    var sec = $('kinoSec'), el = $('kinoList'); if (!sec || !K || !K.length) return;
    var now = new Date(), tk = todayKey();
    var up = K.filter(function (s) { return new Date(s.start) > now });
    if (!up.length) return;
    var day = up.some(function (s) { return parts(s.start).key === tk }) ? tk : parts(up[0].start).key;
    var shows = up.filter(function (s) { return parts(s.start).key === day });
    $('kTitle').textContent = day === tk ? 'Heute im Kino' : day === addDays(tk, 1) ? 'Morgen im Kino' : 'Im Kino am ' + dShort(day);
    var films = [], by = {};
    shows.forEach(function (s) { if (!by[s.film]) { by[s.film] = { f: s, shows: [] }; films.push(by[s.film]) } by[s.film].shows.push(s) });
    var MAX = 6;
    el.innerHTML = films.slice(0, MAX).map(function (x) {
      var f = x.f, meta = [f.duration, f.age].filter(Boolean).join(' · ');
      var labels = x.shows.map(function (s) { return s.special ? s.label : '' }).filter(function (v, i, a) { return v && a.indexOf(v) === i });
      return '<div class="kf"><div class="kh"><a class="kt" href="' + esc(f.url) + '">' + esc(niceTitle(f.title)) + '</a>' +
        labels.map(function (l) { return '<span class="ktag">' + esc(l) + '</span>' }).join('') + '</div>' +
        '<div class="ktimes">' + x.shows.map(function (s) {
          return '<a href="' + esc(s.ticket || s.url) + '" title="' + esc([s.hall, s.langText].concat(s.notes || []).filter(Boolean).join(' · ')) + '">' + parts(s.start).hm + '<small>' + esc(s.lang) + '</small></a>' }).join('') +
        (meta ? '<span class="km">' + esc(meta) + '</span>' : '') + '</div></div>' }).join('');
    var more = films.length - MAX;
    $('kNote').innerHTML = (more > 0 ? '<a href="https://kinozug.ch/de/programm/spielzeiten">+ ' + more + ' weitere Filme</a> · ' : '') + 'Kino Seehof und Gotthard · Tickets auf kinozug.ch';
    sec.hidden = false;
  }

  // ---------- Suche (News, Agenda, Amtlich; alles im Browser)
  function norm(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '') }
  function searchInit() {
    var btn = $('sBtn'), pan = $('sPanel'), inp = $('sIn'), res = $('sRes'), cnt = $('sCount'), timer;
    function open() { pan.hidden = false; btn.setAttribute('aria-expanded', 'true'); inp.focus(); run() }
    function close() { pan.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.focus() }
    btn.onclick = function () { pan.hidden ? open() : close() };
    $('sClose').onclick = close;
    res.addEventListener('click', function (ev) { if (ev.target.closest('a')) { pan.hidden = true; btn.setAttribute('aria-expanded', 'false') } });
    pan.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') close() });
    inp.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 120) });
    function hit(q, title, rest) {
      var t = norm(title), all = t + ' ' + norm(rest);
      if (!q.every(function (w) { return all.indexOf(w) >= 0 })) return -1;
      return q.filter(function (w) { return t.indexOf(w) >= 0 }).length;
    }
    function group(name, items, more) {
      return items.length ? '<section><h3>' + name + '</h3>' + items.join('') + (more ? '<a class="sall" href="' + more[0] + '">' + more[1] + '</a>' : '') + '</section>' : '';
    }
    function row(href, lbl, title, sub) { return '<a class="srow" href="' + esc(href) + '"><span class="sl">' + lbl + '</span><span class="st">' + esc(title) + '</span>' + (sub ? '<span class="ss">' + esc(sub) + '</span>' : '') + '</a>' }
    function run() {
      var q = norm(inp.value).trim().split(/\s+/).filter(Boolean);
      if (!D.news) { cnt.textContent = 'Daten werden geladen …'; res.innerHTML = ''; return }
      if (!q.length || q.join('').length < 2) { cnt.textContent = ''; res.innerHTML = ''; return }
      var today = todayKey();
      function sort(a, b) { return b.s - a.s || (a.k < b.k ? -1 : 1) }
      var ev = D.agenda.map(function (e) { return { e: e, s: hit(q, e.title, [e.teaser, e.place, e.location, e.catLabel, e.institution].join(' ')), k: e.ongoing ? '0' : e.start } })
        .filter(function (x) { return x.s >= 0 && (x.e.ongoing || parts(x.e.start).key >= today) }).sort(sort);
      var nw = D.news.map(function (n) { return { e: n, s: hit(q, n.title, n.lead + ' ' + n.type), k: '~' + n.date } }).filter(function (x) { return x.s >= 0 })
        .sort(function (a, b) { return b.s - a.s || (a.e.date < b.e.date ? 1 : -1) });
      var am = D.amtlich.map(function (a) { return { e: a, s: hit(q, a.title, a.label + ' ' + a.office), k: a.date } }).filter(function (x) { return x.s >= 0 })
        .sort(function (a, b) { return b.s - a.s || (a.e.date < b.e.date ? 1 : -1) });
      var n = ev.length + nw.length + am.length;
      cnt.textContent = n ? n + (n === 1 ? ' Treffer' : ' Treffer') + ' für «' + inp.value.trim() + '»' : 'Keine Treffer für «' + inp.value.trim() + '». Versuche einen anderen Begriff.';
      res.innerHTML =
        group('Agenda', ev.slice(0, 6).map(function (x) { var e = x.e, p = parts(e.start);
          return row(e.ongoing ? 'agenda/#laufend' : evHref(e), e.ongoing ? 'Laufend' : dShort(p.key) + ' ' + (e.allday ? '' : p.hm), e.title, e.place) }), ev.length > 6 ? ['agenda/', 'Ganze Agenda →'] : null) +
        group('News', nw.slice(0, 5).map(function (x) { return row(x.e.url, esc(x.e.type) + ' · ' + dLabel(x.e.date), x.e.title, '') }), nw.length > 5 ? ['news/', 'Alle News →'] : null) +
        group('Amtlich', am.slice(0, 5).map(function (x) { return row(x.e.url, esc(x.e.label) + ' · ' + dLabel(x.e.date), x.e.title, '') }), am.length > 5 ? ['amtlich/', 'Alle Publikationen →'] : null);
    }
    searchInit.run = run;
  }

  // ---------- Start
  // Vorgerenderte Anlässe (Rubrikseiten), die inzwischen vorbei sind, ausblenden
  [].forEach.call(document.querySelectorAll('[data-end]'), function (el) { if (new Date(el.dataset.end) < new Date()) el.hidden = true });

  // ---------- Englisch (/en/): Texte, die app.js nachlädt, mit demselben Wörterbuch wie der Build übersetzen
  var EN = document.documentElement.lang === 'en', I18 = null;
  var JWD = { Mo: 'Mon', Di: 'Tue', Mi: 'Wed', Do: 'Thu', Fr: 'Fri', Sa: 'Sat', So: 'Sun' };
  var JMON = { 'Januar': 'January', 'Februar': 'February', 'März': 'March', 'April': 'April', 'Mai': 'May', 'Juni': 'June', 'Juli': 'July', 'August': 'August', 'September': 'September', 'Oktober': 'October', 'November': 'November', 'Dezember': 'December', 'Jan.': 'Jan.', 'Feb.': 'Feb.', 'Aug.': 'Aug.', 'Sept.': 'Sept.', 'Okt.': 'Oct.', 'Nov.': 'Nov.', 'Dez.': 'Dec.' };
  var RMON = new RegExp('(^|[^\\wÄÖÜäöü.])(' + Object.keys(JMON).map(function (k) { return k.replace('.', '\\.') }).join('|') + ')(?= \\d{4}\\b)', 'g');
  function trDates(s) { return s.replace(/\b(Mo|Di|Mi|Do|Fr|Sa|So)(?=,? \d{1,2}\.)/g, function (m, a) { return JWD[a] }).replace(RMON, function (m, a, b) { return a + JMON[b] }) }
  function trOne(c) {
    if (Object.prototype.hasOwnProperty.call(I18.t, c)) return I18.t[c];
    if (c.indexOf(' · ') >= 0) return c.split(' · ').map(trOne).join(' · ');
    for (var i = 0; i < I18.p.length; i++) { var m = I18.p[i][0].exec(c); if (m) return trDates(c.replace(I18.p[i][0], I18.p[i][1]).replace(/\{\{(.*?)\}\}/g, function (x, y) { return trOne(y) })) }
    return c.length <= 30 ? trDates(c) : c;
  }
  function tr(s) { var c = s.trim(); if (!c || !/[A-Za-zÄÖÜäöü]/.test(c)) return s; var o = trOne(c); return o === c ? s : s.replace(c, o) }
  function enHref(a) {
    if (a.classList.contains('lang')) return;
    var h = a.getAttribute('href'); if (!h || /^(mailto:|tel:|javascript:|#)/.test(h)) return;
    var u; try { u = new URL(h, document.baseURI) } catch (e) { return }
    if (u.origin !== location.origin || u.pathname.indexOf('/en/') === 0) return;
    if (I18.pages.indexOf(u.pathname) >= 0) a.setAttribute('href', '/en' + u.pathname + u.search + u.hash);
  }
  function trEl(root) {
    if (root.nodeType === 3) { var v = tr(root.nodeValue); if (v !== root.nodeValue) root.nodeValue = v; return }
    if (root.nodeType !== 1 || /^(SCRIPT|STYLE)$/.test(root.tagName)) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: function (n) { return n.parentNode && /^(SCRIPT|STYLE)$/.test(n.parentNode.tagName) ? 2 : 1 } }), n;
    while ((n = w.nextNode())) { var v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v }
    [root].concat([].slice.call(root.querySelectorAll('[title],[aria-label],[placeholder],[alt],a[href]'))).forEach(function (el) {
      if (!el.getAttribute) return;
      ['title', 'aria-label', 'placeholder', 'alt'].forEach(function (k) { var v = el.getAttribute(k); if (v) { var t = tr(v); if (t !== v) el.setAttribute(k, t) } });
      if (el.tagName === 'A') enHref(el);
    });
  }
  var i18nReady = !EN ? Promise.resolve() : fetch('/assets/i18n-en.json').then(function (r) { return r.json() }).then(function (d) {
    I18 = { t: d.t, p: d.p.map(function (x) { return [new RegExp('^' + x[0] + '$'), x[1]] }), pages: d.pages };
    new MutationObserver(function (ms) { ms.forEach(function (m) { [].forEach.call(m.addedNodes, trEl) }) }).observe(document.body, { childList: true, subtree: true });
  }).catch(function () { EN = false });
  frame();
  searchInit();
  Promise.all(['news', 'agenda', 'amtlich', 'meta'].map(get).concat([i18nReady])).then(function (r) {
    D = { news: r[0] || [], agenda: r[1] || [], amtlich: r[2] || [], meta: r[3] || {} };
    // GGR-Meldungen erscheinen nur unter «Politik», nicht auf den anderen Seiten
    var GGR = /Grosse[nr]? Gemeinderat|\bGGR\b/i, noGgr = function (x) { return !GGR.test(x.title || '') };
    D.pol = { news: D.news.filter(function (x) { return x.topic === 'politik' || GGR.test(x.title || '') }),
      amt: D.amtlich.filter(function (x) { return !/Sitzung des Grossen Gemeinderat/i.test(x.title || '') && (GGR.test(x.title || '') || /Abstimmung|Wahlen/.test(x.label || '')) }) }; // Sitzungen kommen schon als Meldung der Stadt
    D.news = D.news.filter(noGgr); D.amtlich = D.amtlich.filter(noGgr); D.agenda = D.agenda.filter(noGgr);
    D.events = D.agenda.filter(function (e) { return !e.ongoing });
    D.ongoing = D.agenda.filter(function (e) { return e.ongoing });
    band();
    if (!$('sPanel').hidden) searchInit.run();
    if (page === 'start') { renderToday(); renderNewsTeaser(); renderThemes(); get('kino').then(renderKino) }
    if (page === 'agenda') {
      var open = agendaFromHash(); renderFilters(); renderList(); renderWeekend(); renderLauf(); if (open) openEvent(open);
      window.addEventListener('hashchange', function () { var o = agendaFromHash(); renderFilters(); renderList(); if (o) openEvent(o) });
    }
    if (page === 'news') renderNewsPage();
    if (page === 'amtlich') renderAmtPage();
    if (page === 'politik') get('politik').then(function (p) { renderPolitik(p || {}) });
  });
})();
