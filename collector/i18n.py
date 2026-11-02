"""zug.now – englische Version (/en/).

Erzeugt aus den fertig gebauten deutschen Seiten eine englische Kopie unter /en/:
  - übersetzt Textknoten und Attribute (title, aria-label, placeholder, alt, Meta-Beschreibungen)
    über ein Wörterbuch (collector/i18n/en.json: "t" = exakte Texte, "p" = Muster mit Zahlen/Daten)
    plus den Übersetzungsspeicher site/data/translations_en.json (später automatisch, z. B. DeepL),
  - biegt interne Links auf /en/ um, wenn es die Seite englisch gibt (sonst bleibt der deutsche Link),
  - setzt lang, Canonical, og:url/og:locale, hreflang und den Sprachumschalter,
  - ergänzt die Sitemap um die englischen Seiten mit hreflang-Alternativen.
Im Browser übersetzt app.js nachgeladene Inhalte mit demselben Wörterbuch (assets/i18n-en.json).
Fehlende Übersetzungen bleiben deutsch und werden beim Build gezählt.
Wird von build.py am Schluss aufgerufen.
"""
import html
import json
import re
from pathlib import Path

import build as B

SITE = "https://zug.now"
DICT = Path(__file__).resolve().parent / "i18n" / "en.json"
WD = {"Mo": "Mon", "Di": "Tue", "Mi": "Wed", "Do": "Thu", "Fr": "Fri", "Sa": "Sat", "So": "Sun"}
MONTHS = {"Januar": "January", "Februar": "February", "März": "March", "April": "April", "Mai": "May", "Juni": "June",
          "Juli": "July", "August": "August", "September": "September", "Oktober": "October", "November": "November",
          "Dezember": "December", "Jan.": "Jan.", "Feb.": "Feb.", "Aug.": "Aug.", "Sept.": "Sept.", "Okt.": "Oct.",
          "Nov.": "Nov.", "Dez.": "Dec."}
RE_WD = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)(?=,? \d{1,2}\.)")
RE_MON = re.compile(r"(?<![\w.])(" + "|".join(re.escape(m) for m in MONTHS) + r")(?= \d{4}\b)")
ATTRS = re.compile(r'\b(title|aria-label|placeholder|alt)="([^"]*)"')
META = re.compile(r'(<meta (?:name="description"|property="og:(?:title|description)") content=")([^"]*)(")')
SPLIT = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S | re.I)


class Tr:
    def __init__(self):
        d = json.loads(DICT.read_text(encoding="utf-8"))
        self.t = dict(d.get("t", {}))
        self.t.update(B.load("translations_en", {}))  # automatischer Übersetzungsspeicher (DeepL)
        self.p = [(re.compile("^" + a + "$"), b) for a, b in d.get("p", [])]
        self.raw = d
        self.missing = set()

    def dates(self, s):
        s = RE_WD.sub(lambda m: WD[m[1]], s)
        return RE_MON.sub(lambda m: MONTHS[m[1]], s)

    def __call__(self, s, track=True):
        core = s.strip()
        if not core or not re.search(r"[A-Za-zÄÖÜäöü]", core):
            return s
        out = self.one(core, track)
        return s.replace(core, out, 1) if out != core else s

    def one(self, c, track=True):
        if c in self.t:
            return self.t[c]
        if " · " in c:
            return " · ".join(self.one(x, track) for x in c.split(" · "))
        for rx, rep in self.p:
            m = rx.match(c)
            if m:  # {{…}} im Ersatz = Teil erneut übersetzen
                return self.dates(re.sub(r"\{\{(.*?)\}\}", lambda x: self.one(x[1], track), m.expand(rep)))
        out = self.dates(c) if len(c) <= 30 else c  # nur kurze Datumsangaben, nie deutsche Sätze anpassen
        if out == c and track and re.search(r"[a-zäöü]{3}", c):
            self.missing.add(c)
        return out


def _href(h, en_paths):
    """Interner Link → /en/…, falls es die Seite englisch gibt."""
    if h.startswith(("http:", "https:", "mailto:", "tel:", "data:", "javascript:", "#")) and not h.startswith(SITE):
        return h
    path = h[len(SITE):] if h.startswith(SITE) else h
    if not path.startswith("/"):
        path = "/" + path
    m = re.match(r"([^?#]*)(.*)", path, re.S)
    p, rest = m[1], m[2]
    if p in en_paths:
        return ("/en" + p if p != "/" else "/en/") + rest
    return h if h.startswith(SITE) else path


def to_en(doc, de_path, tr, en_paths):
    parts = SPLIT.split(doc)
    out = []
    for seg in parts:
        if not seg:
            continue
        if seg.startswith("<"):
            low = seg[:30].lower()
            if low.startswith("<script") and 'id="wdata"' in seg:  # Kartenbeschriftungen /wandel/
                head, body = seg.split(">", 1)
                js, tail = body.rsplit("</script>", 1)
                pts = json.loads(js)
                for x in pts:
                    x["t"] = tr(x["t"])
                seg = head + ">" + json.dumps(pts, ensure_ascii=False) + "</script>" + tail
            elif not low.startswith(("<script", "<style")):
                seg = ATTRS.sub(lambda m: f'{m[1]}="{html.escape(tr(html.unescape(m[2])))}"', seg)
                seg = re.sub(r'\bhref="([^"]*)"', lambda m: f'href="{html.escape(_href(html.unescape(m[1]), en_paths))}"', seg)
            out.append(seg)
        else:
            u = html.unescape(seg)
            t = tr(u)
            out.append(seg if t == u else html.escape(t, quote=False))
    doc = "".join(out)
    doc = META.sub(lambda m: m[1] + html.escape(tr(html.unescape(m[2]))) + m[3], doc)
    doc = re.sub(r'<html lang="[^"]*"', '<html lang="en"', doc, 1)
    if "<base " not in doc:
        doc = doc.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="/">', 1)
    en_url = SITE + ("/en" + de_path if de_path != "/" else "/en/")
    doc = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m[1] + en_url + m[2], doc, 1)
    doc = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m[1] + en_url + m[2], doc, 1)
    doc = doc.replace('content="de_CH"', 'content="en_GB"')
    return doc


def _alt(de_path):
    de = SITE + de_path
    en = SITE + ("/en" + de_path if de_path != "/" else "/en/")
    return (f'<link rel="alternate" hreflang="de-CH" href="{de}">\n<link rel="alternate" hreflang="en" href="{en}">\n'
            f'<link rel="alternate" hreflang="x-default" href="{de}">')


def _switch(doc, target, label, lang):
    return re.sub(r'<a class="lang"[^>]*>[^<]*</a>',
                  f'<a class="lang" href="{target}" hreflang="{lang}" lang="{lang}" aria-label="{"English" if lang == "en" else "Deutsch"}">{label}</a>', doc)


def page_path(name):
    """'agenda/index.html' → '/agenda/', 'index.html' → '/'."""
    return "/" + name[: -len("index.html")] if name.endswith("index.html") else None


def build_en(written):
    """written: {Ausgabepfad relativ zu _site: html}. Schreibt /en/… und passt die deutschen Seiten an."""
    tr = Tr()
    de_pages = {page_path(n): (n, d) for n, d in written.items() if page_path(n) and not re.match(r"agenda/\d", n)
                and "http-equiv=\"refresh\"" not in d}
    en_paths = set(de_pages)
    for path, (name, doc) in de_pages.items():
        en = to_en(doc, path, tr, en_paths)
        en = en.replace("</title>", "</title>\n" + _alt(path), 1)
        en = _switch(en, path, "DE", "de")
        out = B.OUT / "en" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(en, encoding="utf-8")
        de = doc.replace("</title>", "</title>\n" + _alt(path), 1)
        de = _switch(de, "/en" + path if path != "/" else "/en/", "EN", "en")
        (B.OUT / name).write_text(de, encoding="utf-8")
    # alle übrigen deutschen Seiten (z. B. Anlässe): Umschalter auf die englische Startseite
    for name, doc in written.items():
        if page_path(name) not in en_paths and name.endswith(".html") and '<a class="lang"' in doc:
            (B.OUT / name).write_text(_switch(doc, "/en/", "EN", "en"), encoding="utf-8")
    # Wörterbuch für den Browser
    js = {"t": tr.t, "p": [[a, re.sub(r"\\(\d)", r"$\1", b)] for a, b in tr.raw.get("p", [])],
          "pages": sorted(en_paths)}
    (B.OUT / "assets" / "i18n-en.json").write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
    # Sitemap: englische Seiten mit hreflang-Alternativen
    sm = (B.OUT / "sitemap.xml").read_text(encoding="utf-8")
    entries = re.findall(r"  <url><loc>(.*?)</loc>(.*?)</url>\n", sm)
    rows = []
    for loc, rest in entries:
        p = loc[len(SITE):] or "/"
        if p in en_paths:
            alt = (f'<xhtml:link rel="alternate" hreflang="de-CH" href="{loc}"/>'
                   f'<xhtml:link rel="alternate" hreflang="en" href="{SITE}/en{p}"/>'
                   f'<xhtml:link rel="alternate" hreflang="x-default" href="{loc}"/>')
            rows.append(f"  <url><loc>{loc}</loc>{rest}{alt}</url>\n")
            rows.append(f"  <url><loc>{SITE}/en{p}</loc>{rest}{alt}</url>\n")
        else:
            rows.append(f"  <url><loc>{loc}</loc>{rest}</url>\n")
    (B.OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "".join(rows) + "</urlset>\n", encoding="utf-8")
    print(f"Englisch: {len(en_paths)} Seiten unter /en/, {len(tr.t)} Wörterbuch-Einträge, {len(tr.missing)} Texte noch ohne Übersetzung (meist Inhalte der Quellen)")
    return tr.missing
