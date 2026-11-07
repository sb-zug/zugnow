"""zug.now – Rubrikseiten (Hubs) für Suchmaschinen und Besucher.

Erzeugt statische Seiten unter eigenen Adressen:
  /wochenende/          alle Anlässe am kommenden Wochenende
  /orte/                Übersicht Kulturhäuser und Institutionen
  /orte/<ort>/          Programm pro Haus (Theater Casino, Galvanik, Burg …)
  /baugesuche/          Baugesuche der Stadt Zug aus dem Amtsblatt
Wird von build.py aufgerufen; nutzt dessen Helfer und das Seitengerüst der Agenda.
Seiten mit weniger als MIN_EVENTS Einträgen erhalten noindex und fehlen in der Sitemap.
"""
import re
from collections import Counter

import build as B

SITE = "https://zug.now/"
MIN_EVENTS = 3

# Eigene Kurztexte (bewusst knapp und sachlich; Fakten wie Adresse kommen aus den Daten)
ORTE = [
    ("theater-casino", "theatercasino", "Theater Casino Zug", "https://www.theatercasino.ch",
     "Das Theater Casino Zug am Seeufer ist die Bühne für Theater, Konzerte, Tanz, Comedy und Kinderprogramm. "
     "Hier stehen alle kommenden Vorstellungen aus dem Spielplan, automatisch übernommen und zweimal täglich aktualisiert."),
    ("galvanik", "galvanik", "Galvanik Zug", "https://www.galvanik-zug.ch",
     "Das Kulturzentrum Galvanik an der Chamerstrasse ist Zugs Treffpunkt für Konzerte, Partys, Comedy und Talks. "
     "Hier findest du das ganze kommende Programm auf einen Blick."),
    ("kunsthaus", "kunsthaus", "Kunsthaus Zug", "https://www.kunsthauszug.ch",
     "Das Kunsthaus Zug zeigt moderne und zeitgenössische Kunst. Dazu kommen Führungen, Vermittlungsangebote und "
     "Veranstaltungen – teils auch im Schaudepot an der Oberallmendstrasse."),
    ("burg", "burg", "Museum Burg Zug", "https://www.burgzug.ch",
     "Das Museum Burg Zug in der Altstadt erzählt die Kulturgeschichte von Stadt und Kanton Zug. "
     "Hier stehen Ausstellungen, Führungen und Familienangebote."),
    ("bibliothek", "bibliothek", "Bibliothek Zug", "https://www.bibliothekzug.ch",
     "Die Bibliothek Zug bietet neben Büchern und Medien ein dichtes Programm: Lesungen, Erzählstunden, "
     "Sprachtreffs und Kurse für Kinder und Erwachsene."),
    ("kino", "kino", "Kinos Seehof und Gotthard", "https://kinozug.ch",
     "Die Zuger Kinos Seehof und Gotthard zeigen aktuelle Filme und Spezialvorstellungen. Hier stehen die besonderen "
     "Vorstellungen; das ganze Programm mit Tickets gibt es auf kinozug.ch."),
    ("musikschule", "musikschule", "Musikschule Zug", "",
     "Die Musikschule Zug lädt regelmässig zu Konzerten und Vorspielen ihrer Schülerinnen und Schüler ein."),
]

FOOTER_COL = ('<div class="col"><span style="font-weight:600;color:var(--fg)">Rubriken</span>'
              '<span><a href="/wochenende/">Wochenende in Zug</a> · <a href="/orte/">Orte &amp; Kulturhäuser</a> · '
              '<a href="/baugesuche/">Baugesuche</a> · <a href="/wandel/">Wie sich Zug verändert</a> · <a href="/wohnen/">Günstig wohnen</a> · <a href="/politik/#pDos">Politische Dossiers</a></span>'
              '<span>' + " · ".join(f'<a href="/orte/{o[0]}/">{o[2]}</a>' for o in ORTE[:5]) + '</span></div>')

_index = set()  # Seiten, die in die Sitemap gehören


def _frame(agenda_html):
    head_css = re.search(r'<link rel="stylesheet" href="assets/app\.css[^"]*">', agenda_html).group(0)
    fonts = "\n".join(re.findall(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts[^>]*>', agenda_html))
    hdr = re.search(r'<div id="hdr">.*?</div>\n<main', agenda_html, re.S).group(0)[:-6]
    ftr = re.search(r'<div id="ftr">.*?</footer></div>', agenda_html, re.S).group(0)
    script = re.search(r'<script src="assets/app\.js[^"]*"></script>', agenda_html).group(0)
    hdr = hdr.replace(' aria-current="page"', "")
    return fonts, head_css, hdr, ftr, script


def _page(frame, path, title, desc, body, nav=None, index=True, image=None):
    fonts, css, hdr, ftr, script = frame
    url = SITE + path
    if nav:
        hdr = hdr.replace(f'<a href="{nav}">', f'<a href="{nav}" aria-current="page">', 1)
    if index:
        _index.add(path)
    return f"""<!doctype html>
<html lang="de-CH">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<base href="/">
<title>{B.esc(title)}</title>
<meta name="description" content="{B.esc(desc)}">
{'' if index else '<meta name="robots" content="noindex, follow">'}
<link rel="canonical" href="{url}">
<meta property="og:title" content="{B.esc(title)}">
<meta property="og:description" content="{B.esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="zug.now">
<meta property="og:locale" content="de_CH">
<meta property="og:image" content="{B.esc(image) if image else SITE + 'assets/og-image.png'}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#1F55C4">
{fonts}
{css}
</head>
<body data-page="hub">
{hdr}
<main class="wrap">
{body}
</main>
{ftr}
{script}
</body>
</html>
"""


def _crumb(*items):
    parts = ['<a href="/">zug.now</a>'] + [f'<a href="/{p}">{B.esc(t)}</a>' if p else B.esc(t) for t, p in items]
    return f'<p class="facts" style="margin-top:8px">{" › ".join(parts)}</p>'


def _evlist(evs, empty):
    return f'<div class="agenda">{"".join(B.ev_row(e) for e in evs)}</div>' if evs else f'<p class="note">{empty}</p>'


def _lauf(items):
    seen, out = set(), []
    for e in items:
        k = (e["title"], e.get("place"))
        if k in seen:
            continue
        seen.add(k)
        bis = f'bis {B.dlabel(e["until"])}' if e.get("until") and e["until"] < "2028" else "Dauerangebot"
        out.append(f'<a href="{B.esc(e.get("url"))}"><div class="ph">{B.img(e.get("image"))}</div><span class="eyebrow">{B.esc(e.get("place"))}</span>'
                   f'<strong>{B.esc(e["title"])}</strong><span>{B.esc(e.get("rhythm") or B.time_label(e))} · {bis}</span></a>')
    return '<div class="lauf">' + "".join(out) + "</div>"


def _n(n, one, many):
    return f"{n} {one if n == 1 else many}"


def wochenende(frame, events, ongoing):
    wa, wb = B.weekend()
    evs = [e for e in events if wa <= B.dt(e["start"]).date() <= wb]
    span = f"{B.dshort(wa)} – {B.dshort(wb)}" if wa != wb else B.dshort(wa)
    body = ('<div class="pagehead"><h1>Wochenende in Zug</h1>'
            f'<p>Was läuft am Wochenende in der Stadt Zug? {span}: {_n(len(evs), "Anlass", "Anlässe")} – Konzerte, Theater, '
            'Ausstellungen, Märkte, Sport und Angebote für Familien. Automatisch aus dem offiziellen Veranstaltungskalender '
            'und den Programmen der Kulturhäuser, zweimal täglich aktualisiert.</p>'
            '<p class="wkwx" hidden></p>'  # Wetter fürs Wochenende, füllt app.js
            + _crumb(("Agenda", "agenda/"), ("Wochenende", None)) + "</div>")
    for d in sorted({B.dt(e["start"]).date() for e in evs}):
        day = [e for e in evs if B.dt(e["start"]).date() == d]
        name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][d.weekday()]
        body += (f'<section class="block"><div class="shead"><h2>{name}, {d.day}.{d.month}.</h2>'
                 f'<span>{_n(len(day), "Anlass", "Anlässe")}</span></div>{_evlist(day, "")}</section>')
    if not evs:
        body += '<section class="block"><p class="note">Für dieses Wochenende sind noch keine Anlässe gemeldet.</p></section>'
    if ongoing:
        body += ('<section class="block"><div class="shead"><h2>Ausstellungen und Laufendes</h2>'
                 '<span>Auch am Wochenende offen</span></div>' + _lauf(ongoing) + "</section>")
    body += '<section class="block"><p><a href="agenda/">Ganze Agenda mit Filtern →</a></p></section>'
    return _page(frame, "wochenende/", "Wochenende in Zug – was läuft? | zug.now",
                 f"Was läuft am Wochenende in der Stadt Zug: {_n(len(evs), 'Anlass', 'Anlässe')} am {span} – Konzerte, Theater, Ausstellungen und mehr, täglich aktualisiert.",
                 body, nav="agenda/", index=len(evs) >= MIN_EVENTS)


def orte(frame, events, ongoing):
    pages, cards = {}, []
    for slug, inst, name, web, text in ORTE:
        evs = [e for e in events if e.get("institution") == inst]
        lauf = [e for e in ongoing if e.get("institution") == inst]
        locs = Counter(re.sub(r"\s+", " ", e.get("location") or "") for e in evs + lauf if e.get("location"))
        addr = "; ".join(l for l, _ in locs.most_common(2)) if inst in ("kino", "kunsthaus") else (locs.most_common(1)[0][0] if locs else "")
        idx = len(evs) + len(lauf) >= MIN_EVENTS
        facts = " · ".join(x for x in [B.esc(addr), f'<a href="{B.esc(web)}">Website {B.EXT}</a>' if web else ""] if x)
        body = (f'<div class="pagehead"><h1>{B.esc(name)}</h1><p>{B.esc(text)}</p>'
                f'<p class="facts">{facts}</p>' + _crumb(("Orte", "orte/"), (name, None)) + "</div>")
        body += (f'<section class="block"><div class="shead"><h2>Programm</h2><span>{_n(len(evs), "kommender Anlass", "kommende Anlässe")}</span></div>'
                 + _evlist(evs, "Zurzeit sind keine kommenden Anlässe gemeldet.") + "</section>")
        if lauf:
            body += '<section class="block"><div class="shead"><h2>Ausstellungen und Laufendes</h2></div>' + _lauf(lauf) + "</section>"
        body += '<section class="block"><p><a href="orte/">Alle Orte →</a> · <a href="agenda/">Ganze Agenda →</a></p></section>'
        pages[f"orte/{slug}/index.html"] = _page(
            frame, f"orte/{slug}/", f"{name} – Programm und Veranstaltungen | zug.now",
            f"{name}: alle kommenden Veranstaltungen ({_n(len(evs), 'Anlass', 'Anlässe')}) mit Datum, Zeit und Details. Automatisch aktualisiert.",
            body, nav="agenda/", index=idx)
        nxt = f" · nächster am {B.dshort(B.dt(evs[0]['start']).date())}" if evs else ""
        cards.append(f'<a href="orte/{slug}/"><strong>{B.esc(name)}</strong><span>{_n(len(evs), "Anlass", "Anlässe")}{nxt}</span></a>')
    body = ('<div class="pagehead"><h1>Orte und Kulturhäuser in Zug</h1>'
            '<p>Theater, Konzertlokale, Museen, Bibliothek und Kinos in der Stadt Zug – jedes Haus mit seinem kommenden Programm. '
            'Die Programme werden automatisch übernommen und zweimal täglich aktualisiert.</p>'
            + _crumb(("Orte", None)) + "</div>"
            '<section class="block"><div class="polparties">' + "".join(cards) + "</div></section>")
    pages["orte/index.html"] = _page(frame, "orte/", "Orte und Kulturhäuser in Zug – Programme | zug.now",
                                     "Theater Casino, Galvanik, Kunsthaus, Burg, Bibliothek und Kinos in Zug: alle Programme an einem Ort.",
                                     body, nav="agenda/")
    return pages


def baugesuche(frame, amtlich, news):
    bg = [a for a in amtlich if a.get("label") == "Baugesuch"]
    rows = "".join(
        f'<a href="{B.esc(a["url"])}"><span class="d">{B.dlabel(a["date"])}</span><span class="t">{B.esc(a["title"])}</span>'
        f'<span class="o">Publiziert im Amtsblatt' + (f' · einsehbar bis {B.dlabel(a["expires"])}' if a.get("expires") else "") + "</span></a>"
        for a in bg)
    lists = [n for n in news if re.match(r"(Baugesuche vom|Publikationen von Baugesuchen)", n["title"], re.I)]
    body = ('<div class="pagehead"><h1>Baugesuche Stadt Zug</h1>'
            '<p>Die Stadt Zug publiziert neue Baugesuche im Amtsblatt des Kantons Zug. Während der Auflage können die Pläne '
            'eingesehen werden. Hier stehen die aktuellen Publikationen mit Adresse, automatisch übernommen und zweimal täglich '
            'aktualisiert. Massgebend für Fristen und Auflageort ist die Publikation im Amtsblatt.</p>'
            + _crumb(("Amtlich", "amtlich/"), ("Baugesuche", None)) + "</div>"
            f'<section class="block"><div class="shead"><h2>Aktuelle Baugesuche</h2><span>{_n(len(bg), "Publikation", "Publikationen")}</span></div>'
            + (f'<div class="amtlist">{rows}</div>' if bg else '<p class="note">Zurzeit sind keine Baugesuche publiziert.</p>') + "</section>")
    if lists:
        body += ('<section class="block"><div class="shead"><h2>Wöchentliche Übersichten der Stadt</h2><span>stadtzug.ch</span></div><div class="amtlist">'
                 + "".join(f'<a href="{B.esc(n["url"])}"><span class="d">{B.dlabel(n["date"])}</span><span class="t">{B.esc(n["title"])}</span></a>' for n in lists)
                 + "</div></section>")
    body += '<section class="block"><p><a href="wandel/">Wie sich Zug verändert: alle grossen Vorhaben →</a> · <a href="amtlich/">Alle amtlichen Publikationen →</a></p></section>'
    return _page(frame, "baugesuche/", "Baugesuche Stadt Zug – aktuelle Publikationen | zug.now",
                 f"Aktuelle Baugesuche der Stadt Zug aus dem Amtsblatt: {_n(len(bg), 'Publikation', 'Publikationen')} mit Adresse und Auflagefrist, täglich aktualisiert.",
                 body, nav="amtlich/", index=len(bg) + len(lists) >= 1)


def build_hubs(agenda_html, events, ongoing, amtlich, all_news):
    frame = _frame(agenda_html)
    pages = {"wochenende/index.html": wochenende(frame, events, ongoing),
             "baugesuche/index.html": baugesuche(frame, amtlich, all_news)}
    pages.update(orte(frame, events, ongoing))
    print("Rubriken:", ", ".join(k.replace("index.html", "") + ("" if k.replace("index.html", "") in _index else " (noindex)") for k in pages))
    return pages


def sitemap(pages):
    main = [("", "daily"), ("agenda/", "daily"), ("news/", "daily"), ("amtlich/", "daily"), ("politik/", "weekly")]
    urls = main + [(p, "daily") for p in sorted(_index)]
    today = B.TODAY.isoformat()
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{SITE}{p}</loc><lastmod>{today}</lastmod><changefreq>{f}</changefreq></url>\n" for p, f in urls)
            + "</urlset>\n")
