"""zug.now – Startseite «Raster» (seit 5.11.2026; /start-c/ leitet auf / um).

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


def _excerpt(e, n=110, field="teaser"):
    """Ein Satz aus dem Teaser/Lead der Quelle, höchstens rund n Zeichen."""
    t = re.sub(r"\s+", " ", e.get(field) or "").split(" · ")[0].strip()
    if len(t) < 15 or t.lower().rstrip(".") in (e["title"] or "").lower():
        return ""
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m and len(m.group(1)) >= 25 else t
    if len(t) > n:
        t = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:–-") + " …"
    return t


def _ev(e, day_label):
    d = B.dt(e["start"]).date()
    t = "ganztags" if e.get("allday") else B.hm(e["start"]).replace(":", ".")
    rel = {0: "Heute", 1: "Morgen"}.get((d - B.TODAY).days)
    when = f'{rel or B.WDL[d.weekday()]} · {t}' 
    return (f'<a class="rc rev" href="{B.esc(e.get("page") or "agenda/#ev-" + e["id"])}"><span class="rk">{B.esc(when)}</span>'
            f'<strong>{B.esc(e["title"])}</strong>' + (f'<span class="rex">{B.esc(x)}</span>' if (x := _excerpt(e)) else "")
            + f'<span class="rs">{B.esc(e.get("place") or "")}</span>{ARR}</a>')


def _agenda(events):
    up = [e for e in events if not e.get("cancelled") and not B.over(e)]

    def best(lst, n=6):
        """Anlässe mit Bild bevorzugen (wie die bisherige Startseite), dann chronologisch."""
        seen, out = set(), []
        for e, dl in [x for x in lst if x[0].get("image")] + [x for x in lst if not x[0].get("image")]:
            if e["title"] not in seen and len(out) < n:
                seen.add(e["title"]); out.append((e, dl))
        return sorted(out, key=lambda x: x[0]["start"])

    today = [e for e in up if B.dt(e["start"]).date() == B.TODAY]
    heute = best([(e, False) for e in today])
    if len(heute) < 6:  # wenig los: mit den nächsten Anlässen auffüllen (mit Tag)
        heute += [(e, True) for e in up if B.dt(e["start"]).date() > B.TODAY][: 6 - len(heute)]
    morgen = [(e, False) for e in up if B.dt(e["start"]).date() == B.TODAY + timedelta(days=1)]
    wa, wb = B.weekend()
    seen, wk = set(), []
    for e in up:  # Wochenende: verschiedene Titel, chronologisch
        if wa <= B.dt(e["start"]).date() <= wb and e["title"] not in seen:
            seen.add(e["title"]); wk.append((e, True))
    tabs = [("heute", "Heute", heute), ("morgen", "Morgen", best(morgen)), ("wochenende", "Wochenende", best(wk))]
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
    rows = SB.mitreden_rows(projekte, pol_news, politik)[:3]
    if not rows:
        return ""
    cells = [f'<a class="rc rmi{" live" if live else ""}" href="{B.esc(u)}"><span class="rk">{B.esc(lbl)}</span>'
             f'<span class="rd">{td.day}.{td.month}.</span><strong>{B.esc(t)}</strong><span class="rs">{B.esc(x)}</span></a>'
             for _, td, live, lbl, t, x, u in rows]
    return ('<section class="rg r4 rblue" aria-labelledby="rMit"><div class="rc rhead"><h2 id="rMit">Jetzt mitreden</h2>'
            '<span class="rs">Auflagen, Infoanlässe, Parlament und Urne – die nächsten Termine</span>'
            '<a class="rmore" href="wandel/">Alle Termine →</a></div>' + "".join(_fill(cells, 3)) + "</section>")


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
        f'<strong>{B.esc(n["title"])}</strong>' + (f'<span class="rex">{B.esc(x)}</span>' if (x := _excerpt(n, field="lead")) else "")
        + f'{ARR}</a>' for n in pool[:4]) + '<div class="rc rx" aria-hidden="true"></div>' * (len(pool[:4]) % 2)
    parl = "".join(
        f'<a href="{B.esc(u)}"><span class="rk">{re.sub(r"<[^>]+>", " ", k).strip()} · {B.dlabel(d)}</span><strong>{B.esc(t)}</strong></a>'
        for d, k, t, st, u in SB.parl_rows(politik)[:3])
    return ('<section class="rg r12 rnews"><div class="rnl" aria-labelledby="rNw"><div class="rc rhead rline"><h2 id="rNw">News</h2>'
            f'<a class="rmore" href="news/">Alle News →</a></div>{news}</div>'
            + (f'<div class="rc rparl" aria-labelledby="rPa"><h2 id="rPa">Aus dem Parlament</h2><div class="rpl">{parl}</div>'
               '<a class="rmore" href="politik/#pGes">Alle Geschäfte →</a></div>' if parl else "")
            + "</section>")


def _hero(slides):
    """Hero: H1 + Slider mit bis zu 3 Meldungen (Bild links, Text rechts, Punkte und Pfeile im Bild)."""
    h1 = ('<div class="rc rh1"><h1>Was läuft<br>in Zug<span class="dot">.</span></h1>'
          '<p>Agenda, News, Amtliches und Politik der Stadt Zug – an einem Ort, zweimal täglich aktualisiert.</p></div>')
    if not slides:
        return f'<section class="rg r12 rhero">{h1}</section>'
    k = len(slides)
    arrow = lambda d, lbl, path: (f'<button type="button" class="rsa" data-go="{d}" aria-label="{lbl}"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" '
                                  f'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{path}"/></svg></button>')

    def ctl(i):
        if k < 2:
            return ""
        return (f'<span class="rcnt" aria-hidden="true">{i + 1} / {k}</span>'
                f'{arrow(-1, "Vorherige Meldung", "M15 6l-6 6 6 6").replace("rsa", "rsa rprev", 1)}'
                f'{arrow(1, "Nächste Meldung", "M9 6l6 6-6 6").replace("rsa", "rsa rnext", 1)}')
    out = []
    for i, n in enumerate(slides):
        u = B.esc(n["url"])
        img = (f'<span class="rim"><a class="rimg" href="{u}" tabindex="-1" aria-hidden="true">{B.img(n["image"])}</a>'
               f'<span class="credit">Bild: Stadt Zug</span>{ctl(i)}</span>') if n.get("image") else ""
        out.append(f'<div class="rslide{"" if n.get("image") else " noimg"}" data-i="{i}"{"" if i == 0 else " hidden"}>{img}'
                   f'<a class="rc rlt" href="{u}"><span class="rk">{B.esc(B.topic_of(n))} · {B.dlabel(n["date"])}</span>'
                   f'<strong>{B.esc(n["title"])}</strong>' + (f'<span class="rs">{B.esc(n["lead"])}</span>' if n.get("lead") else "")
                   + f'<span class="rsrc">Zur Meldung auf stadtzug.ch {B.EXT}</span></a></div>')
    return (f'<section class="rg r12 rhero">{h1}<div class="rlead rslider" role="region" aria-roledescription="Karussell" '
            f'aria-label="Neueste Meldungen">{"".join(out)}<span class="vh rlive" aria-live="polite"></span></div></section>')


TABS_JS = """<script>
(function(){var g=document.querySelector('.ragenda');if(!g)return;g.addEventListener('click',function(ev){var b=ev.target.closest('.rtab');if(!b)return;
g.querySelectorAll('.rtab').forEach(function(x){x.setAttribute('aria-pressed',x===b)});
g.querySelectorAll('.rpanel').forEach(function(p){p.hidden=p.dataset.p!==b.dataset.t});
var m=document.getElementById('rAgMore');if(m)m.setAttribute('href','agenda/#'+b.dataset.t)})})();
(function(){var r=document.querySelector('.rslider');if(!r)return;var S=r.querySelectorAll('.rslide'),n=S.length,c=0;if(n<2)return;
function show(i){c=(i+n)%n;S.forEach(function(s,j){s.hidden=j!==c});var lv=r.querySelector('.rlive');if(lv)lv.textContent='Meldung '+(c+1)+' von '+n}
r.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;e.preventDefault();show(b.dataset.to!=null?+b.dataset.to:c+(+b.dataset.go));
var f=S[c].querySelector('button[data-'+(b.dataset.to!=null?'to="'+c+'"]':'go="'+b.dataset.go+'"]'));if(f)f.focus()});
r.addEventListener('keydown',function(e){if(e.key==='ArrowLeft'||e.key==='ArrowRight'){show(c+(e.key==='ArrowRight'?1:-1));e.preventDefault()}});
var x=null;r.addEventListener('touchstart',function(e){x=e.touches[0].clientX},{passive:true});
r.addEventListener('touchend',function(e){if(x==null)return;var d=e.changedTouches[0].clientX-x;if(Math.abs(d)>40)show(c+(d<0?1:-1));x=null})})();
(function(){var a=document.querySelector('.v3 .ilink[href*="pAbst"] strong'),d=document.body.dataset.vote;if(!a||!d)return;
var t=new Date(),n=Math.round((Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10))-Date.UTC(t.getFullYear(),t.getMonth(),t.getDate()))/864e5);
if(n>0){var s=document.createElement('em');s.className='rcd';s.textContent='in '+n+(n===1?' Tag':' Tagen');a.appendChild(s)}})();
</script>"""


def build_start_c(index_html, events, news, pol_news):
    redirect = ('<!doctype html><html lang="de-CH"><head><meta charset="utf-8"><title>zug.now</title>'
                '<meta name="robots" content="noindex"><link rel="canonical" href="https://zug.now/">'
                '<meta http-equiv="refresh" content="0; url=/"></head><body><a href="/">Zur Startseite</a></body></html>')
    return {"index.html": _page(index_html, events, news, pol_news), "start-c/index.html": redirect}


def _page(index_html, events, news, pol_news):
    politik = B.load("politik", {})
    projekte = B.load("wandel", {}).get("projekte") or []
    pool = [n for n in news if not re.match(r"Baugesuche vom", n["title"], re.I)]
    key = lambda n: re.sub(r"[^a-zäöü]", "", n["title"].lower().replace(", zug", ""))[:50]
    slides = [n for n in pool if n.get("image")][:3] or pool[:1]  # Slider: die 3 neuesten Meldungen mit Bild
    seen, rest = {key(n) for n in slides}, []
    for n in pool:  # fast gleiche Meldungen (z. B. «…, Zug») nur einmal, nichts doppelt zum Slider
        if n not in slides and key(n) not in seen:
            seen.add(key(n)); rest.append(n)
    main = ('<main id="top" class="rwrap">' + _hero(slides) + _agenda(events) + _news_parl(rest, politik)
            + _mitreden(projekte, pol_news, politik) + _wandel(projekte) + "</main>")
    p = index_html
    p = p.replace('class="v2"', f'class="v2 v3 vhome" data-vote="{B.esc(politik.get("nextVoteDate") or "")}"', 1)
    p = p.replace("<head>\n", '<head>\n<base href="/">\n', 1)
    p = re.sub(r'<section class="intro".*?</section>\s*', "", p, count=1, flags=re.S)
    p = re.sub(r"<main\b.*?</main>", lambda m: main, p, count=1, flags=re.S)
    p = p.replace("</body>", TABS_JS + "\n</body>", 1)
    return p
