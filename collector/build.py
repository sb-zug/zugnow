"""zug.now – Vorrendern für Suchmaschinen.

Liest site/data/*.json und schreibt eine Kopie von site/ nach _site/, in der die
Inhalte (Agenda, News, Amtliches, Politik) bereits als HTML in den Seiten stehen.
Im Browser übernimmt danach assets/app.js wie bisher (ersetzt die Inhalte live).
Nur Python-Standardbibliothek. Aufruf: python collector/build.py
"""
import html
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "site", ROOT / "_site"
TZ = ZoneInfo("Europe/Zurich")
NOW = datetime.now(TZ)
TODAY = NOW.date()

WD = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]
WDL = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MO = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]
# Hauptseiten liegen seit 2.11.2026 unter /agenda/ usw.; agenda.html etc. sind Weiterleitungen
PATHS = {f"{n}.html": f"{n}/index.html" for n in ("agenda", "news", "amtlich", "politik")}
GGR = re.compile(r"Grosse[nr]? Gemeinderat|\bGGR\b", re.I)
EXT = ('<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" '
       'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg>')
CHEVR = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>')
CHEV = ('<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>')
CAL = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
       'aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M3 10h18M8 3v4M16 3v4"></path></svg>')
NTOPICS = [("politik", "Politik & Verwaltung"), ("bauen", "Bauen & Planung"), ("mobilitaet", "Mobilität & Verkehr"),
           ("bildung", "Bildung & Schule"), ("kultur", "Kultur & Freizeit"), ("umwelt", "Umwelt & Energie"),
           ("soziales", "Soziales & Gesundheit")]


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def load(name, default):
    try:
        return json.loads((SRC / "data" / f"{name}.json").read_text(encoding="utf-8"))
    except Exception:
        return default


def dt(iso):
    return datetime.fromisoformat(iso).astimezone(TZ)


def dlabel(d):  # 'YYYY-MM-DD' oder date → 31.10.2026
    d = d if not isinstance(d, str) else datetime.strptime(d[:10], "%Y-%m-%d").date()
    return f"{d.day}.{d.month}.{d.year}"


def dshort(d):
    return f"{WDL[d.weekday()]} {d.day}.{d.month}."


def hm(iso):
    return dt(iso).strftime("%H:%M")


def time_label(e):
    if e.get("allday"):
        return "ganztags"
    return hm(e["start"]) + ("–" + hm(e["end"]) if e.get("end") else "")


def over(e):
    return not e.get("allday") and dt(e.get("end") or e["start"]) < NOW


def img(src):
    return (f'<img src="{esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
            if src else "")


def weekend():
    wd = TODAY.weekday()  # Mo=0 … So=6
    if wd == 6:
        return TODAY, TODAY
    if wd == 5:
        return TODAY, TODAY + timedelta(days=1)
    sa = TODAY + timedelta(days=5 - wd)
    return sa, sa + timedelta(days=1)


# ---------- Bausteine (gleiches Markup wie app.js)
def ev_row(e):
    d = dt(e["start"]).date()
    meta = time_label(e) + (" · " + esc(e["rhythm"]) if e.get("rhythm") else "") + " · " + esc(e.get("place"))
    side = '<span class="tag off">Abgesagt</span>' if e.get("cancelled") else f'<span class="tag">{esc(e.get("catLabel"))}</span>'
    end = "" if e.get("allday") else f' data-end="{esc(e.get("end") or e["start"])}"'
    return (f'<details class="ev" id="ev-{esc(e["id"])}"{end}><summary><div class="date" aria-label="{dlabel(d)}">'
            f'<span class="wd">{WD[d.weekday()]}</span><span class="d">{d.day}</span><span class="mo">{MO[d.month - 1]}</span></div>'
            + (f'<div class="thumb">{img(e["image"])}</div>' if e.get("image") else "")
            + f'<div class="evmain"><span class="ttl">{esc(e["title"])}</span><span class="meta">{meta}</span></div>'
            f'<div class="evside">{side}<small>Quelle: {esc(e.get("source"))}</small></div>{CHEV}</summary>'
            f'<div class="panel{" withimg" if e.get("image") else ""}"><div style="display:flex;flex-direction:column;gap:14px;min-width:0">'
            f'<p>{esc(e.get("text") or e.get("teaser") or "Keine Beschreibung vorhanden.")}</p><span class="facts">{esc(e.get("location"))}</span>'
            '<div class="actions">' + (f'<a class="btn primary" href="{esc(e["page"])}">Details →</a><a class="btn" href="{esc(e.get("url"))}">Zur Quelle ↗</a>' if e.get("page") else f'<a class="btn primary" href="{esc(e.get("url"))}">Zum Anlass →</a>') + '</div></div>'
            + (f'<div class="pimg">{img(e["image"])}</div>' if e.get("image") else "") + "</div></details>")


def news_row(n):
    mm = "mm" if "Medien" in (n.get("type") or "") else ""
    return (f'<a href="{esc(n["url"])}" class="{"img" if n.get("image") else ""}"><span class="d"><b class="{mm}">{esc(n.get("type") or "News")}</b>{dlabel(n["date"])}'
            + (f'<i class="ntop">{esc(n["topicLabel"])}</i>' if n.get("topicLabel") else "") + "</span>"
            f'<span class="c"><span class="t">{esc(n["title"])}</span><span class="l">{esc(n.get("lead"))}</span></span>'
            + (f'<span class="i">{img(n["image"])}</span>' if n.get("image") else "") + "</a>")


def topic_of(n):
    return "Stadtleben" if not n.get("topicLabel") or n.get("topic") == "weitere" else n["topicLabel"]


def tcard(e, show_day):
    d = dt(e["start"]).date()
    t = "ganztags" if e.get("allday") else hm(e["start"])
    im = f'<div class="tim">{img(e["image"])}</div>' if e.get("image") else f'<div class="tim nob c-{esc(e.get("cat") or "weitere")}"><span>{esc(e.get("catLabel"))}</span></div>'
    return (f'<a class="tcard" href="{esc(e.get("page") or "agenda/#ev-" + e["id"])}">{im}<div class="tb"><span class="tm">{(dshort(d) + " · " + t) if show_day else t}</span>'
            f'<strong>{esc(e["title"])}</strong><span class="ts"><span>{esc(e.get("place"))} · {esc(e.get("catLabel"))}</span>{CHEVR}</span></div></a>')


# ---------- Seiten
def fill(doc, el_id, inner):
    """Setzt Inhalt in ein leeres Element mit dieser ID (<tag … id="x"></tag>)."""
    pat = re.compile(r'(<([a-z]+)[^>]*\bid="' + re.escape(el_id) + r'"[^>]*>)(</\2>)')
    new, n = pat.subn(lambda m: m.group(1) + inner + m.group(3), doc, count=1)
    if not n:
        print(f"  ! Platzhalter #{el_id} nicht gefunden")
    return new


def raster(doc):
    """Raster-Layout (seit 5.11.2026) auf allen Seiten: Klasse v3 am body, Schrift Inter Tight."""
    if "<body" not in doc or "http-equiv=\"refresh\"" in doc:
        return doc
    m = re.search(r"<body([^>]*)>", doc)
    attrs = m.group(1)
    if 'class="' in attrs:
        if "v3" not in re.search(r'class="([^"]*)"', attrs).group(1).split():
            attrs = re.sub(r'class="([^"]*)"', r'class="\1 v3"', attrs, count=1)
    else:
        attrs += ' class="v3"'
    doc = doc[:m.start()] + f"<body{attrs}>" + doc[m.end():]
    if "Inter+Tight" not in doc:
        doc = doc.replace("family=Archivo:", "family=Inter+Tight:wght@600;700;800&family=Archivo:", 1)
    return doc


def build():
    news, agenda, amtlich = load("news", []), load("agenda", []), load("amtlich", [])
    politik = load("politik", {})
    no_ggr = lambda x: not GGR.search(x.get("title") or "")
    pol_news = [n for n in news if n.get("topic") == "politik" or GGR.search(n.get("title") or "")]
    # Sitzungsanzeigen im Amtsblatt doppeln die Meldungen der Stadt → weglassen
    pol_amt = [a for a in amtlich if not re.search(r"Sitzung des Grossen Gemeinderat", a.get("title") or "", re.I)
               and (GGR.search(a.get("title") or "") or re.search("Abstimmung|Wahlen", a.get("label") or ""))]
    news, amtlich, agenda = [n for n in news if no_ggr(n)], [a for a in amtlich if no_ggr(a)], [e for e in agenda if no_ggr(e)]
    events = [e for e in agenda if not e.get("ongoing") and dt(e["start"]).date() >= TODAY]
    ongoing = [e for e in agenda if e.get("ongoing")]
    import events as evpages
    evpages.assign(events)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    pages = {p: (OUT / PATHS.get(p, p)).read_text(encoding="utf-8") for p in ["index.html", "agenda.html", "news.html", "amtlich.html", "politik.html"]}

    # Startseite: Agenda heute (wie app.js: kommende zuerst, Bilder vorne), News, Themen
    upcoming = [e for e in events if not e.get("cancelled") and not over(e)]
    today = [e for e in upcoming if dt(e["start"]).date() == TODAY][:12]
    lst = today + ([e for e in upcoming if dt(e["start"]).date() > TODAY][: 6 - len(today) + (0 if today else 3)] if len(today) < 6 else [])
    lst = [e for e in lst if e.get("image")] + [e for e in lst if not e.get("image")]
    p = pages["index.html"]
    p = fill(p, "todayList", "".join(tcard(e, dt(e["start"]).date() != TODAY) for e in lst))
    pool = [n for n in news if not re.match(r"Baugesuche vom", n["title"], re.I)]
    lead = next((n for n in pool if n.get("image")), pool[0] if pool else None)
    if lead:
        rest = [n for n in pool if n is not lead][:3]
        p = fill(p, "newsGrid",
                 f'<a class="blead" href="{esc(lead["url"])}">' + (f'<div class="bim">{img(lead["image"])}</div>' if lead.get("image") else "")
                 + f'<div class="bb"><span class="beye">{esc(topic_of(lead))} · {dlabel(lead["date"])}</span><strong>{esc(lead["title"])}</strong>'
                 + (f'<span class="bl">{esc(lead["lead"])}</span>' if lead.get("lead") else "")
                 + f'<span class="bsrc">{esc(lead.get("type") or "News")} · Stadt Zug {EXT}</span></div></a>'
                 + '<div class="blist">' + "".join(
                     f'<a href="{esc(n["url"])}"><span class="bc"><span class="beye">{esc(topic_of(n))} · {int(n["date"][8:10])}.{int(n["date"][5:7])}.</span><strong>{esc(n["title"])}</strong>'
                     + (f'<span class="bl">{esc(n["lead"])}</span>' if n.get("lead") else "") + f'<span class="bsrc">Stadt Zug {EXT}</span></span>'
                     + (f'<span class="bth">{img(n["image"])}</span>' if n.get("image") else "") + "</a>" for n in rest) + "</div>")
    pages["index.html"] = p

    # Agenda: Liste (erste 20 wie app.js), Wochenende, Laufend
    p = pages["agenda.html"]
    p = fill(p, "agCount", f'{len(events)} {"Anlass" if len(events) == 1 else "Anlässe"} in den nächsten 60 Tagen')
    rows_html, last = [], None
    for e in events[:20]:  # Raster: Datum pro Tag nur in der ersten Zeile
        d = dt(e["start"]).date()
        r = ev_row(e)
        rows_html.append(r.replace('<details class="ev"', '<details class="ev same"', 1) if d == last else r)
        last = d
    p = fill(p, "agList", "".join(rows_html))
    wa, wb = weekend()
    wk = [e for e in events if wa <= dt(e["start"]).date() <= wb and not e.get("cancelled")]
    seen, pick = set(), []
    for e in [e for e in wk if e.get("image")] + [e for e in wk if not e.get("image")]:
        if e["title"] not in seen and len(pick) < 6:
            seen.add(e["title"]); pick.append(e)
    pick.sort(key=lambda e: e["start"])
    p = fill(p, "wkBadgeN", f'{len(wk)} {"Anlass" if len(wk) == 1 else "Anlässe"} →')
    p = fill(p, "wkCards", "".join(
        f'<a href="{esc(e.get("page") or "agenda/#ev-" + e["id"])}"><div class="ph">{img(e.get("image"))}<span class="when">{dshort(dt(e["start"]).date())} · {"ganztags" if e.get("allday") else hm(e["start"])}</span></div>'
        f'<span class="eyebrow">{esc(e.get("catLabel"))}</span><strong>{esc(e["title"])}</strong><span class="s">{esc(e.get("place"))}</span></a>' for e in pick))
    lauf, keys = [], set()
    for e in ongoing:
        k = (e["title"], e.get("place"))
        if k not in keys:
            keys.add(k); lauf.append(e)
    p = fill(p, "laufGrid", "".join(
        f'<a href="{esc(e.get("url"))}"><div class="ph">{img(e.get("image"))}</div><span class="eyebrow">{esc(e.get("place"))}</span>'
        f'<strong>{esc(e["title"])}</strong><span>{esc(e.get("rhythm") or time_label(e))} · '
        + (f'bis {dlabel(e["until"])}' if e.get("until") and e["until"] < "2028" else "Dauerangebot") + "</span></a>" for e in lauf))
    pages["agenda.html"] = p

    # News, Amtlich
    pages["news.html"] = fill(pages["news.html"], "newsList", "".join(news_row(n) for n in news))
    pages["amtlich.html"] = fill(pages["amtlich.html"], "amtList", "".join(
        f'<a href="{esc(a["url"])}"><span class="d">{dlabel(a["date"])}</span><span class="t"><span class="lbl" style="display:block;margin-bottom:2px">{esc(a.get("label"))}</span>{esc(a["title"])}</span>'
        f'<span class="o">{esc(a.get("office"))}' + (f' · einsehbar bis {dlabel(a["expires"])}' if a.get("expires") else "") + "</span></a>" for a in amtlich))

    # Politik: Parlament, Parteimeldungen, Parteien
    rows = ([(n["date"], n.get("type") or "News", "Medien" in (n.get("type") or ""), n["title"], n.get("lead"), n["url"]) for n in pol_news]
            + [(a["date"], "Amtsblatt · " + (a.get("label") or ""), False, a["title"], "", a["url"]) for a in pol_amt])
    rows.sort(key=lambda r: r[0], reverse=True)
    p = pages["politik.html"]
    p = fill(p, "polParl", "".join(
        f'<a href="{esc(u)}"><span class="d"><b class="{"mm" if red else ""}">{esc(lbl)}</b>{dlabel(d)}</span>'
        f'<span class="c"><span class="t">{esc(t)}</span>' + (f'<span class="l">{esc(sub)}</span>' if sub else "") + "</span></a>"
        for d, lbl, red, t, sub, u in rows[:8]))
    p = fill(p, "polPosts", "".join(
        f'<a href="{esc(x["url"])}"><span class="d"><b>{esc(x.get("party"))}</b>{dlabel(x["date"])}</span>'
        f'<span class="c"><span class="t">{esc(x["title"])}</span>' + (f'<span class="l">{esc(x["lead"])}</span>' if x.get("lead") else "")
        + f'<span class="psrc2">{esc(x.get("partyName"))} {EXT}</span></span></a>' for x in (politik.get("posts") or [])[:12]))
    p = fill(p, "polParties", "".join(
        f'<a href="{esc(x[1])}"><strong>{esc(x[0])}</strong><span>Website {EXT}</span></a>' for x in (politik.get("parteien") or [])))
    pages["politik.html"] = p

    import hubs
    pages.update(evpages.pages(pages["agenda.html"], events))
    pg = {e["id"]: e["page"] for e in events}
    raw = load("agenda", [])
    for e in raw:
        if e["id"] in pg:
            e["page"] = pg[e["id"]]
    (OUT / "data" / "agenda.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    pages.update(hubs.build_hubs(pages["agenda.html"], events=events, ongoing=ongoing, amtlich=amtlich, all_news=load("news", [])))
    import wandel
    pages.update(wandel.build_wandel(pages["agenda.html"], news=load("news", []), amtlich=load("amtlich", [])))
    import wohnen
    pages.update(wohnen.build_wohnen(pages["agenda.html"]))
    import dossiers
    pages.update(dossiers.build_dossiers(pages["agenda.html"], pages["politik.html"], news=load("news", []), amtlich=load("amtlich", [])))
    import startb
    pages.update(startb.build_start_b(pages["index.html"], pol_news))
    import startc
    pages.update(startc.build_start_c(pages["index.html"], events, news, pol_news))
    import newsletter
    nl = newsletter.build_newsletter(pages["agenda.html"], events, pol_news)
    mail = nl.pop("newsletter/mail.html")
    pages.update(nl)
    for name, doc in pages.items():
        if name.endswith(".html"):
            doc = doc.replace("</div></div></footer>", "</div>" + hubs.FOOTER_COL + "</div></footer>", 1)
            doc = raster(doc)
        name = PATHS.get(name, name)
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(doc, encoding="utf-8")
    (OUT / "newsletter" / "mail.html").write_text(mail, encoding="utf-8")
    (OUT / "sitemap.xml").write_text(hubs.sitemap(pages), encoding="utf-8")
    import i18n
    written = {PATHS.get(n, n): (OUT / PATHS.get(n, n)).read_text(encoding="utf-8") for n in pages if n.endswith(".html")}
    i18n.build_en(written)
    print(f"Vorgerendert: {len(events)} Anlässe ({min(20, len(events))} in der Liste), {len(news)} News, {len(amtlich)} Amtlich, "
          f"{len(rows)} Politik-Meldungen → {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
