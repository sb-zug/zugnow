"""zug.now – Rubrik «Wie sich Zug verändert» (/wandel/).

Bündelt grosse Vorhaben der Stadt Zug als Dossiers: Phase, Meilensteine mit Quellen,
Mitreden-Fenster und automatisch zugeordnete Meldungen (News, Amtsblatt).
Die Dossiers pflegt die Redaktion von Hand in site/data/wandel.json;
die Zuordnung der Meldungen läuft bei jedem Build über Stichworte.
Wird von build.py aufgerufen.
"""
import json
import re
from datetime import date

import build as B
import hubs as H

PHASEN = ["Planung", "Mitwirkung", "Parlament", "Abstimmung", "Bewilligung", "Bau", "Eröffnet"]
MON = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]


def _d(s):
    """Meilenstein-Datum → (date|None, Label). Akzeptiert JJJJ-MM-TT, JJJJ-MM, JJJJ oder Text."""
    s = str(s or "")
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        d = date(*map(int, m.groups()))
        return d, f"{d.day}.{d.month}.{d.year}"
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        y, mo = map(int, m.groups())
        return date(y, mo, 28), f"{MON[mo - 1]} {y}"
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return date(int(s), 12, 31), s
    return None, s


def _state(ms):
    """Status je Meilenstein: done / now / next / later (relativ zu heute)."""
    out, seen_next = [], False
    for m in ms:
        a, _ = _d(m.get("datum"))
        b, _ = _d(m.get("bis")) if m.get("bis") else (a, "")
        if a and b and a <= B.TODAY <= b and m.get("bis"):
            st = "now"
        elif a and (b or a) < B.TODAY:
            st = "done"
        elif not seen_next:
            st, seen_next = "next", True
        else:
            st = "later"
        out.append(st)
    return out


def _when(m):
    _, la = _d(m.get("datum"))
    if m.get("bis"):
        _, lb = _d(m["bis"])
        return f"{la} – {lb}"
    return la


def _next(p):
    st = _state(p["meilensteine"])
    for m, s in zip(p["meilensteine"], st):
        if s in ("now", "next"):
            return m, s
    return None, None


def _phasebar(n, big=False):
    cells = "".join(
        f'<li class="{"on" if i < n else ""}{" cur" if i == n - 1 else ""}"><span>{B.esc(PHASEN[i])}</span></li>'
        for i in range(len(PHASEN)))
    return f'<ol class="phases{" big" if big else ""}" aria-label="Phase: {B.esc(PHASEN[n - 1])}">{cells}</ol>'


def _matches(p, news, amtlich):
    kws = [k.lower() for k in p.get("keywords", [])]
    hit = lambda t: any(k in t.lower() for k in kws)
    rows = [(n["date"], n.get("type") or "News", n["title"], n["url"]) for n in news
            if hit(n["title"] + " " + (n.get("lead") or ""))]
    rows += [(a["date"], "Amtsblatt", a["title"], a["url"]) for a in amtlich if hit(a["title"])]
    return sorted(rows, reverse=True)[:8]


def _wchip(p):
    w = p.get("wohnen") or {}
    if w.get("preisguenstig"):
        return f'<span class="wchip">{w["preisguenstig"]} preisgünstige Wohnungen</span>'
    return ""


def _card(p):
    m, s = _next(p)
    nx = (f'<span class="nx{" live" if s == "now" else ""}"><b>{"Läuft jetzt" if s == "now" else "Als Nächstes"}</b> '
          f'{B.esc(_when(m))} · {B.esc(m["text"])}</span>') if m else ""
    return (f'<a class="wcard" href="wandel/{p["slug"]}/"><span class="eyebrow">{B.esc(p["art"])} · {B.esc(p["quartier"])}</span>'
            f'<strong>{B.esc(p["titel"])}</strong><span class="sub">{B.esc(p["untertitel"])}</span>'
            + _wchip(p) + f'{_phasebar(p["phase"])}<span class="ph-l">Phase {p["phase"]}/7: {B.esc(PHASEN[p["phase"] - 1])}</span>{nx}</a>')


MAP_JS = """<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<script>
(function(){
  var el=document.getElementById('wmap'); if(!el||!window.L) return;
  var dark=matchMedia('(prefers-color-scheme: dark)').matches&&document.documentElement.dataset.theme!=='light';
  var map=L.map(el,{scrollWheelZoom:false,zoomControl:true,attributionControl:true}).setView([47.1770,8.5080],14);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/'+(dark?'dark_all':'light_all')+'/{z}/{x}/{y}{r}.png',
    {maxZoom:18,attribution:'&copy; OpenStreetMap, &copy; CARTO'}).addTo(map);
  var cs=getComputedStyle(document.documentElement), pts=JSON.parse(document.getElementById('wdata').textContent), b=[];
  pts.forEach(function(p){
    var c=p.phase>=6?cs.getPropertyValue('--ok'):p.phase>=4?cs.getPropertyValue('--brand'):cs.getPropertyValue('--red');
    var m=L.circleMarker([p.lat,p.lon],{radius:11,weight:3,color:'#fff',fillColor:c.trim(),fillOpacity:1}).addTo(map);
    m.bindTooltip(p.t,{permanent:true,direction:'right',offset:[10,0],className:'wtip'});
    m.on('click',function(){location.href='wandel/'+p.s+'/';});
    b.push([p.lat,p.lon]);
  });
  if(b.length) map.fitBounds(b,{padding:[40,40]});
})();
</script>"""


def build_wandel(agenda_html, news, amtlich):
    data = B.load("wandel", {})
    projekte = data.get("projekte") or []
    if not projekte:
        return {}
    frame = H._frame(agenda_html)
    stand = B.dlabel(data.get("stand") or B.TODAY.isoformat())
    pages = {}

    # ── Übersicht ──
    upcoming = []
    for p in projekte:
        for m, s in zip(p["meilensteine"], _state(p["meilensteine"])):
            a, _ = _d(m.get("datum"))
            if s in ("now", "next", "later") and a:
                upcoming.append((a, s, p, m))
    upcoming.sort(key=lambda x: (x[0], x[2]["titel"]))
    mitreden = [(p, m) for a, s, p, m in upcoming
                if re.search(r"Auflage|Mitwirkung|Infoanlass|Informationsanlass", m["text"]) and a <= date(B.TODAY.year + 1, B.TODAY.month, 1)]

    body = ('<div class="pagehead"><span class="eyebrow">Stadtentwicklung</span><h1>Wie sich Zug verändert</h1>'
            '<p>Neue Stadtteile, Schulhäuser, ein Hallenbad, neue Regeln fürs Bauen: Hier siehst du die grossen Vorhaben der Stadt Zug '
            'auf einen Blick – wo sie stehen, was als Nächstes passiert und wann du mitreden kannst. Jedes Dossier bündelt '
            'Stadtrat, Parlament, Abstimmungen und Medienmitteilungen an einem Ort.</p>'
            + H._crumb(("Wandel", None)) + "</div>")
    if mitreden:
        body += ('<section class="block"><div class="mitreden"><span class="eyebrow">Jetzt mitreden</span>'
                 + "".join(f'<a href="wandel/{p["slug"]}/"><strong>{B.esc(p["titel"])}</strong>'
                           f'<span>{B.esc(_when(m))} · {B.esc(m["text"])}</span></a>' for p, m in mitreden[:4])
                 + "</div></section>")
    pts = [{"s": p["slug"], "t": p["titel"], "lat": p["lat"], "lon": p["lon"], "phase": p["phase"]} for p in projekte if p.get("lat")]
    body += ('<section class="block"><div class="shead"><h2>Die Stadt im Umbau</h2><span>Ungefähre Lage · antippen für das Dossier</span></div>'
             '<div id="wmap" class="wmap" role="img" aria-label="Karte der Vorhaben in der Stadt Zug"></div>'
             '<p class="wlegend"><span><i class="lg-plan"></i>Planung &amp; Mitwirkung</span><span><i class="lg-pol"></i>Politik &amp; Bewilligung</span>'
             '<span><i class="lg-bau"></i>Im Bau</span></p>'
             f'<script type="application/json" id="wdata">{json.dumps(pts, ensure_ascii=False)}</script></section>')
    body += ('<section class="block"><div class="shead"><h2>Was als Nächstes passiert</h2><span>Kalender der Veränderung</span></div><ol class="wtl">'
             + "".join(f'<li class="{"now" if s == "now" else "next" if i == 0 else "later"}"><a href="wandel/{p["slug"]}/"><span class="d">{B.esc(_when(m))}</span>'
                       f'<span class="c"><b>{B.esc(p["titel"])}</b>{B.esc(m["text"])}</span></a></li>' for i, (a, s, p, m) in enumerate(upcoming[:10]))
             + "</ol></section>")
    body += ('<section class="block"><div class="shead"><h2>Alle Vorhaben</h2>'
             f'<span>{len(projekte)} Dossiers · Stand {stand}</span></div>'
             f'<div class="wgrid">{"".join(_card(p) for p in sorted(projekte, key=lambda p: p["phase"]))}</div></section>')
    body += ('<section class="block"><p class="note">Redaktionell zusammengestellt aus öffentlichen Quellen (Stadt Zug, Baudepartement, Ratsinfo, '
             'Projektwebsites). Meldungen aus News und Amtsblatt werden automatisch zugeordnet. Massgebend sind die amtlichen Publikationen. '
             '<a href="wohnen/">Günstig wohnen →</a> · <a href="baugesuche/">Aktuelle Baugesuche →</a> · <a href="politik/">Politik →</a></p></section>')
    head_extra = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">'
    page = H._page(frame, "wandel/", "Wie sich Zug verändert – Bauprojekte und Planung | zug.now",
                   "LG-Areal, Metalli, Lorzenallmend, Hallenbad, Schulhäuser: alle grossen Vorhaben der Stadt Zug mit Stand, "
                   "nächsten Schritten und Mitwirkung auf einen Blick.", body, nav="wandel/")
    page = page.replace("</head>", head_extra + "\n</head>", 1).replace("</body>", MAP_JS + "\n</body>", 1)
    pages["wandel/index.html"] = page

    # ── Dossiers ──
    for p in projekte:
        st = _state(p["meilensteine"])
        tl = "".join(
            f'<li class="{s}"><span class="d">{B.esc(_when(m))}</span><span class="c">{B.esc(m["text"])}'
            + (f' <a class="src" href="{B.esc(m["quelle"])}">Quelle {B.EXT}</a>' if m.get("quelle") else "") + "</span></li>"
            for m, s in zip(p["meilensteine"], st))
        facts = "".join(f'<div><span>{B.esc(k)}</span><strong>{B.esc(v)}</strong></div>' for k, v in p.get("fakten", []))
        hits = _matches(p, news, amtlich)
        body = (f'<div class="pagehead"><span class="eyebrow">{B.esc(p["art"])} · {B.esc(p["quartier"])}</span>'
                f'<h1>{B.esc(p["titel"])}</h1><p class="lead2">{B.esc(p["untertitel"])}</p><p>{B.esc(p["kurz"])}</p>'
                + H._crumb(("Wandel", "wandel/"), (p["titel"], None)) + "</div>")
        body += (f'<section class="block"><div class="shead"><h2>Wo das Vorhaben steht</h2><span>Phase: {B.esc(PHASEN[p["phase"] - 1])}</span></div>'
                 + _phasebar(p["phase"], big=True) + (f'<div class="wfacts">{facts}</div>' if facts else "") + "</section>")
        if p.get("wohnen"):
            body += (f'<section class="block"><p class="note">Wohnungen: {B.esc(p["wohnen"].get("hinweis"))}. '
                     '<a href="wohnen/">Alle Vorhaben mit günstigen Wohnungen →</a></p></section>')
        if p.get("mitreden"):
            body += f'<section class="block"><div class="mitreden"><span class="eyebrow">Mitreden</span><p>{B.esc(p["mitreden"])}</p></div></section>'
        body += f'<section class="block"><div class="shead"><h2>Der Weg bisher – und weiter</h2></div><ol class="wtl dossier">{tl}</ol></section>'
        body += ('<section class="block"><div class="shead"><h2>Aktuelle Meldungen</h2><span>Automatisch aus News und Amtsblatt</span></div>'
                 + (('<div class="amtlist">' + "".join(
                     f'<a href="{B.esc(u)}"><span class="d">{B.dlabel(d)}</span><span class="t"><span class="lbl" style="display:block;margin-bottom:2px">{B.esc(l)}</span>{B.esc(t)}</span></a>'
                     for d, l, t, u in hits) + "</div>") if hits else
                    '<p class="note">Zurzeit keine neuen Meldungen. Sobald die Stadt oder das Amtsblatt etwas publiziert, erscheint es hier.</p>')
                 + "</section>")
        if p.get("links"):
            body += ('<section class="block"><div class="shead"><h2>Mehr dazu</h2></div><div class="polparties">'
                     + "".join(f'<a href="{B.esc(u)}"><strong>{B.esc(t)}</strong><span>Website {B.EXT}</span></a>' for t, u in p["links"])
                     + "</div></section>")
        body += (f'<section class="block"><p class="note">Stand {stand}, redaktionell aus öffentlichen Quellen. Massgebend sind die amtlichen Publikationen.</p>'
                 '<p><a href="wandel/">Alle Vorhaben →</a></p></section>')
        m, _ = _next(p)
        desc = f'{p["titel"]} in Zug: {p["untertitel"]}. Stand: {PHASEN[p["phase"] - 1]}' + (f', als Nächstes {_when(m)}: {m["text"]}.' if m else ".")
        pages[f'wandel/{p["slug"]}/index.html'] = H._page(
            frame, f'wandel/{p["slug"]}/', f'{p["titel"]} – Stand und nächste Schritte | zug.now', desc, body)
    print(f"Wandel: {len(projekte)} Dossiers, {len(upcoming)} kommende Meilensteine")
    return pages
