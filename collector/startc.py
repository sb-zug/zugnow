"""zug.now – Startseite Variante C «Raster» (Entwurf 5.11.2026), Vorschau unter /start-c/.

Strenges Kachelraster mit durchgezogenen Linien (CSS-Block «Startseite Raster (body.v3)» in app.css).
Baut auf der fertigen Startseite (Variante B) auf: Kopf, Infoleiste (inkl. Abstimmung) und Fuss bleiben,
der Inhalt wird neu gesetzt: Hero (H1 + Top-Meldung), Agenda (Heute/Morgen/Wochenende), Jetzt mitreden,
Wie sich Zug verändert (+ Wohnband), News, Aus dem Parlament. Alles beim Build (2× täglich) vorgerendert;
Wetter, Sonnenuntergang und Anlässe heute füllt app.js wie gewohnt.
Wird von build.py aufgerufen. Übernahme als Startseite: Ausgabe in build.py auf "index.html" umstellen.
"""
import re
from datetime import timedelta

import build as B
import startb as SB
import wandel as W

ARR = '<span class="ra" aria-hidden="true">→</span>'


def _fill(cells, n):
    """Raster auffüllen, damit die Linien aufgehen."""
    return cells + ['<div class="rc rx" aria-hidden="true"></div>'] * (-len(cells) % n)


def _ev(e, day_label):
    d = B.dt(e["start"]).date()
    t = "ganztags" if e.get("allday") else B.hm(e["start"]).replace(":", ".")
    when = f'{B.dshort(d)} · {t}' if day_label else t
    return (f'<a class="rc rev" href="{B.esc(e.get("page") or "agenda/#ev-" + e["id"])}"><span class="rk">{B.esc(when)}</span>'
            f'<strong>{B.esc(e["title"])}</strong><span class="rs">{B.esc(e.get("place") or "")}'
            + (f' · {B.esc(e["catLabel"])}' if e.get("catLabel") else "") + f'</span>{ARR}</a>')


def _agenda(events):
    up = [e for e in events if not e.get("cancelled") and not B.over(e)]
    today = [e for e in up if B.dt(e["start"]).date() == B.TODAY]
    heute = [(e, False) for e in today[:6]]
    if len(heute) < 6:  # wenig los: mit den nächsten Anlässen auffüllen (mit Tag)
        heute += [(e, True) for e in up if B.dt(e["start"]).date() > B.TODAY][: 6 - len(heute)]
    morgen = [(e, False) for e in up if B.dt(e["start"]).date() == B.TODAY + timedelta(days=1)]
    wa, wb = B.weekend()
    seen, wk = set(), []
    for e in up:  # Wochenende: verschiedene Titel, chronologisch
        if wa <= B.dt(e["start"]).date() <= wb and e["title"] not in seen:
            seen.add(e["title"]); wk.append((e, True))
    tabs = [("heute", "Heute", heute), ("morgen", "Morgen", morgen[:6]), ("wochenende", "Wochenende", wk[:6])]
    btn = "".join(f'<button type="button" class="rtab" data-t="{k}" aria-pressed="{"true" if i == 0 else "false"}">{lbl}</button>'
                  for i, (k, lbl, _) in enumerate(tabs))
    panels = "".join(
        f'<div class="rpanel" data-p="{k}"{"" if i == 0 else " hidden"}>'
        + "".join(_fill([_ev(e, dl) for e, dl in lst] or ['<div class="rc rev"><span class="rs">Noch keine Anlässe gemeldet.</span></div>'], 3))
        + "</div>" for i, (k, _, lst) in enumerate(tabs))
    return (f'<section class="rg r4 ragenda" aria-labelledby="rAg"><div class="rc rhead rtall"><h2 id="rAg">Agenda</h2>'
            f'<div class="rtabs" role="group" aria-label="Zeitraum">{btn}</div>'
            f'<a class="rmore" id="rAgMore" href="agenda/#heute">Alle {len(events)} Anlässe →</a></div>'
            f'<div class="rpanels">{panels}</div></section>')


def _mitreden(projekte, pol_news, politik):
    rows = SB.mitreden_rows(projekte, pol_news, politik)[:4]
    if not rows:
        return ""
    cells = [f'<a class="rc rmi{" live" if live else ""}" href="{B.esc(u)}"><span class="rk">{B.esc(lbl)}</span>'
             f'<span class="rd">{td.day}.{td.month}.</span><strong>{B.esc(t)}</strong><span class="rs">{B.esc(x)}</span></a>'
             for _, td, live, lbl, t, x, u in rows]
    return ('<section class="rg r4 rblue" aria-labelledby="rMit"><div class="rc rbar"><h2 id="rMit">Jetzt mitreden</h2>'
            '<span>Auflagen, Infoanlässe, Parlament und Urne – die nächsten Termine</span>'
            '<a href="wandel/">Alle Termine →</a></div>' + "".join(_fill(cells, 4)) + "</section>")


def _phases(n):
    return ('<span class="rph" aria-hidden="true">' + "".join(f'<i class="{"on" if i < n else ""}"></i>' for i in range(7)) + "</span>")


def _wandel(projekte):
    if not projekte:
        return ""
    cells = []
    for p in sorted(projekte, key=SB.soon)[:3]:
        n = int(p["phase"])
        m, _ = W._next(p)
        nx = (f'<span class="rs"><b>{B.esc(W._when(m))}</b> {B.esc(m["text"])}</span>') if m else ""
        cells.append(f'<a class="rc rwv ph{n}" href="wandel/{B.esc(p["slug"])}/"><span class="rk">Phase {n} von 7 · {B.esc(W.PHASEN[n - 1])}</span>'
                     f'{_phases(n)}<strong>{B.esc(p["titel"])}</strong>{nx}</a>')
    wp = [p for p in projekte if p.get("wohnen")]
    pg = sum(p["wohnen"].get("preisguenstig") or 0 for p in wp)
    ziel = (B.load("wohnen", {}).get("ziel") or {})
    band = ""
    if pg:
        pct = min(100, round(pg / ziel["zahl"] * 100)) if ziel.get("zahl") else 0
        band = (f'<a class="rc rwohn" href="wohnen/"><strong>{B.esc(f"{pg:,}".replace(",", "’"))}</strong>'
                '<span class="rt">preisgünstige Wohnungen fest geplant oder im Bau</span>'
                + (f'<span class="rbarw" role="img" aria-label="{pct} Prozent des Ziels"><i style="width:{pct}%"></i></span>'
                   f'<span class="rs">Ziel Initiative: {ziel["zahl"]:,} bis {ziel.get("jahr", "")} →</span>'.replace(",", "’") if pct else '<span class="rs">Günstig wohnen →</span>')
                + "</a>")
    return ('<section class="rg r4" aria-labelledby="rWa"><div class="rc rhead"><h2 id="rWa">Wie sich Zug verändert</h2>'
            f'<a class="rmore" href="wandel/">Alle {len(projekte)} Vorhaben →</a></div>' + "".join(cells) + band + "</section>")


def _news_parl(pool, politik):
    news = "".join(
        f'<a class="rc rnw" href="{B.esc(n["url"])}"><span class="rk">{B.esc(B.topic_of(n))} · {int(n["date"][8:10])}.{int(n["date"][5:7])}.</span>'
        f'<strong>{B.esc(n["title"])}</strong>{ARR}</a>' for n in pool[:4])
    parl = "".join(
        f'<a href="{B.esc(u)}"><span class="rk">{re.sub(r"<[^>]+>", " ", k).strip()} · {B.dlabel(d)}</span><strong>{B.esc(t)}</strong></a>'
        for d, k, t, st, u in SB.parl_rows(politik)[:3])
    return ('<section class="rg r12 rnews"><div class="rnl" aria-labelledby="rNw"><div class="rc rhead rline"><h2 id="rNw">News</h2>'
            f'<a class="rmore" href="news/">Alle News →</a></div>{news}</div>'
            + (f'<div class="rc rparl" aria-labelledby="rPa"><h2 id="rPa">Aus dem Parlament</h2><div class="rpl">{parl}</div>'
               '<a class="rmore" href="politik/#pGes">Alle Geschäfte →</a></div>' if parl else "")
            + "</section>")


def _hero(lead):
    h1 = ('<div class="rc rh1"><h1>Was läuft<br>in Zug<span class="dot">.</span></h1>'
          '<p>Agenda, News, Amtliches und Politik der Stadt Zug – an einem Ort, zweimal täglich aktualisiert.</p></div>')
    if not lead:
        return f'<section class="rg r12 rhero">{h1}</section>'
    return (f'<section class="rg r12 rhero">{h1}<a class="rlead{" noimg" if not lead.get("image") else ""}" href="{B.esc(lead["url"])}">'
            + (f'<span class="rim">{B.img(lead["image"])}<span class="credit">Bild: Stadt Zug</span></span>' if lead.get("image") else "")
            + f'<span class="rc rlt"><span class="rk">{B.esc(B.topic_of(lead))} · {B.dlabel(lead["date"])}</span>'
              f'<strong>{B.esc(lead["title"])}</strong>' + (f'<span class="rs">{B.esc(lead["lead"])}</span>' if lead.get("lead") else "")
            + f'<span class="rsrc">Zur Meldung auf stadtzug.ch {B.EXT}</span></span></a></section>')


TABS_JS = """<script>
(function(){var g=document.querySelector('.ragenda');if(!g)return;g.addEventListener('click',function(ev){var b=ev.target.closest('.rtab');if(!b)return;
g.querySelectorAll('.rtab').forEach(function(x){x.setAttribute('aria-pressed',x===b)});
g.querySelectorAll('.rpanel').forEach(function(p){p.hidden=p.dataset.p!==b.dataset.t});
var m=document.getElementById('rAgMore');if(m)m.setAttribute('href','agenda/#'+b.dataset.t)})})();
</script>"""


def build_start_c(index_html, events, news, pol_news):
    politik = B.load("politik", {})
    projekte = B.load("wandel", {}).get("projekte") or []
    pool = [n for n in news if not re.match(r"Baugesuche vom", n["title"], re.I)]
    lead = next((n for n in pool if n.get("image")), pool[0] if pool else None)
    rest = [n for n in pool if n is not lead]
    main = ('<main id="top" class="rwrap">' + _hero(lead) + _agenda(events) + _mitreden(projekte, pol_news, politik)
            + _wandel(projekte) + _news_parl(rest, politik) + "</main>")
    p = index_html
    p = p.replace('class="v2"', 'class="v2 v3"', 1)
    p = p.replace("<head>\n", '<head>\n<base href="/">\n', 1)
    p = re.sub(r'<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', p, count=1)
    p = p.replace("family=Archivo:", "family=Inter+Tight:wght@600;700;800&family=Archivo:", 1)
    p = re.sub(r'<section class="intro".*?</section>\s*', "", p, count=1, flags=re.S)
    p = re.sub(r"<main\b.*?</main>", lambda m: main, p, count=1, flags=re.S)
    p = p.replace("</body>", TABS_JS + "\n</body>", 1)
    return {"start-c/index.html": p}
