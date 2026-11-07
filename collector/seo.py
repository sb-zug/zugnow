"""zug.now – technischer SEO-Feinschliff, läuft am Ende von build.py (7.11.2026).

  - Strukturierte Daten: WebSite + Organization auf der Startseite, BreadcrumbList aus dem Navigationspfad
  - Sitemap: echtes Änderungsdatum pro Seite (Hash des Hauptinhalts, site/data/lastmod.json)
  - IndexNow: Liste geänderter Adressen → _site/indexnow.json (gesendet von collector/indexnow.py nach dem Veröffentlichen)
  - Eigene Fehlerseite _site/404.html
"""
import hashlib
import json
import re

import build as B
import hubs as H

SITE = "https://zug.now"
LASTMOD = B.SRC / "data" / "lastmod.json"
CRUMB = re.compile(r'<p class="facts" style="margin-top:8px">(.*?)</p>', re.S)


def _ld(data):
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def _text(s):
    return B.html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def breadcrumb(doc):
    m = CRUMB.search(doc)
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', doc)
    if not m or not canon:
        return None
    items = []
    for part in m.group(1).split(" › "):
        a = re.search(r'href="([^"]+)"', part)
        name = _text(part)
        if not name:
            continue
        url = (SITE + a.group(1)) if a and a.group(1).startswith("/") else (a.group(1) if a else canon.group(1))
        items.append({"@type": "ListItem", "position": len(items) + 1, "name": name, "item": url})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items} if len(items) > 1 else None


def home_ld(en=False):
    org = {"@type": "Organization", "@id": SITE + "/#org", "name": "zug.now", "url": SITE + "/",
           "logo": SITE + "/apple-touch-icon.png"}
    site = {"@type": "WebSite", "@id": SITE + "/#site", "name": "zug.now", "url": SITE + ("/en/" if en else "/"),
            "inLanguage": "en" if en else "de-CH", "publisher": {"@id": SITE + "/#org"},
            "description": "What's on in the City of Zug: events, news, official notices, politics and urban development."
            if en else "Was läuft in der Stadt Zug: Agenda, News, Amtliches, Politik und Stadtentwicklung."}
    return {"@context": "https://schema.org", "@graph": [org, site]}


def main_hash(doc):
    m = re.search(r"<main.*?</main>", doc, re.S)
    return hashlib.sha1((m.group(0) if m else doc).encode()).hexdigest()[:16]


def page404(frame):
    body = ('<div class="pagehead"><h1>Seite nicht gefunden</h1>'
            '<p id="nf">Diese Seite gibt es nicht (mehr). Anlässe verschwinden einige Wochen nach ihrem Datum – '
            'hier geht es zu dem, was jetzt in Zug läuft.</p>'
            '<p lang="en">Page not found – <a href="/en/">zug.now in English</a>.</p></div>'
            '<section class="block"><p><a href="/agenda/">Agenda →</a> · <a href="/wochenende/">Wochenende in Zug →</a> · '
            '<a href="/news/">News →</a> · <a href="/wandel/">Wie sich Zug verändert →</a> · <a href="/">Startseite →</a></p></section>'
            '<script>if(/^\\/(en\\/)?agenda\\/\\d{4}-\\d{2}-\\d{2}-/.test(location.pathname))'
            'document.getElementById("nf").textContent="Dieser Anlass ist vorbei und wurde entfernt. Was jetzt in Zug läuft:";</script>')
    doc = H._page(frame, "404.html", "Seite nicht gefunden | zug.now", "Diese Seite gibt es auf zug.now nicht (mehr).", body, index=False)
    doc = re.sub(r'<link rel="canonical"[^>]*>\n|<meta property="og:url"[^>]*>\n', "", doc)
    return B.raster(doc.replace("</div></div></footer>", "</div>" + H.FOOTER_COL + "</div></footer>", 1))


def finish(agenda_html):
    files = {p: p.read_text(encoding="utf-8") for p in B.OUT.rglob("*.html")}
    n_bc = 0
    for path, doc in files.items():
        if 'http-equiv="refresh"' in doc or "<head>" not in doc:
            continue
        add = []
        bc = breadcrumb(doc)
        if bc:
            add.append(_ld(bc)); n_bc += 1
        rel = path.relative_to(B.OUT).as_posix()
        if rel in ("index.html", "en/index.html"):
            add.append(_ld(home_ld(rel.startswith("en/"))))
        if add:
            doc = doc.replace("</head>", "\n".join(add) + "\n</head>", 1)
            files[path] = doc
            path.write_text(doc, encoding="utf-8")

    # Sitemap: lastmod = Tag der letzten inhaltlichen Änderung
    try:
        store = json.loads(LASTMOD.read_text(encoding="utf-8"))
    except Exception:
        store = {}
    sm = (B.OUT / "sitemap.xml").read_text(encoding="utf-8")
    today, new, changed = B.TODAY.isoformat(), {}, []

    def repl(m):
        loc = m.group(1)
        f = B.OUT / (loc[len(SITE) + 1:] + "index.html")
        h = main_hash(files.get(f, "")) if f in files else ""
        old = store.get(loc)
        day = old[1] if old and old[0] == h else today
        if day == today and (not old or old[0] != h):
            changed.append(loc)
        new[loc] = [h, day]
        return f"<loc>{loc}</loc><lastmod>{day}</lastmod>"

    sm = re.sub(r"<loc>(.*?)</loc><lastmod>[^<]*</lastmod>", repl, sm)
    sm = re.sub(r"<changefreq>[^<]*</changefreq>", "", sm)  # wird von Google ignoriert
    (B.OUT / "sitemap.xml").write_text(sm, encoding="utf-8")
    try:
        LASTMOD.write_text(json.dumps(new, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")
    except Exception as x:
        print("lastmod nicht gespeichert:", x)
    (B.OUT / "indexnow.json").write_text(json.dumps(changed), encoding="utf-8")
    (B.OUT / "404.html").write_text(page404(H._frame(agenda_html)), encoding="utf-8")
    print(f"SEO: {n_bc} Seiten mit Breadcrumb, {len(changed)} geänderte Adressen für IndexNow, 404.html")
