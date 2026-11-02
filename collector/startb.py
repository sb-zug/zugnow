"""zug.now – Startseite (ehemals Variante B, seit 2.11.2026).

Baut auf der fertig vorgerenderten index.html auf (Kopf, Infoleiste, Agenda, News, Kino bleiben gleich)
und ergänzt: Abstimmungs-Kachel in der Infoleiste, «Jetzt mitreden», «Wie sich Zug verändert»
(Wohnzähler + 3 Vorhaben) und «Aus dem Parlament» (Ratsinfo). «Themen aus Zug» entfällt.
Wird von build.py aufgerufen.
"""
import re
from datetime import date

import build as B
import wandel as W

MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
SESS = re.compile(r"vom (\d{1,2})\.(\d{1,2})\.(\d{4})")


def _iso(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _tile(d, live=False):
    return (f'<span class="mt{" live" if live else ""}"><b>{d.day}</b>{MON[d.month - 1]}</span>')


def _mitreden(projekte, pol_news, politik):
    rows = []  # (sortdatum, tile-datum, live, label, titel, text, url)
    for p in projekte:
        for m, s in zip(p["meilensteine"], W._state(p["meilensteine"])):
            a, _ = W._d(m.get("datum"))
            if s not in ("now", "next", "later") or not a or (a - B.TODAY).days > 60:
                continue
            if not re.search(r"Auflage|Mitwirkung|Infoanlass|Informationsanlass", m["text"]):
                continue
            live = s == "now"
            b, _ = W._d(m.get("bis")) if m.get("bis") else (a, "")
            lbl = "Auflage läuft" if live else ("Infoanlass" if "anlass" in m["text"] else "Auflage" if "Auflage" in m["text"] else "Mitwirkung")
            text = (f'Noch bis {b.day}.{b.month}. · ' if live else "") + m["text"]
            rows.append((B.TODAY if live else a, b if live else a, live, lbl, p["titel"], text, f'wandel/{p["slug"]}/'))
    sess = []
    for n in pol_news:
        mm = SESS.search(n["title"])
        if mm and "Sitzung" in n["title"]:
            d = date(int(mm[3]), int(mm[2]), int(mm[1]))
            if d >= B.TODAY:
                sess.append((d, n))
    if sess:
        d, n = min(sess, key=lambda x: x[0])
        rows.append((d, d, False, "Parlament", "Sitzung des Grossen Gemeinderats", "Öffentlich, ab 8 Uhr im Regierungsgebäude – oder im Livestream", n["url"]))
    nv = _iso(politik.get("nextVoteDate"))
    if nv and nv >= B.TODAY:
        k = len([v for v in politik.get("upcoming") or [] if v.get("date") == politik.get("nextVoteDate")])
        rows.append((nv, nv, False, "Abstimmung", "Abstimmungssonntag",
                     f'{k} {"Vorlage" if k == 1 else "Vorlagen"} · Unterlagen und Resultate' if k else "Vorlagen werden aufgeschaltet", "politik/#pAbst"))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return ""
    return ('<section class="block" aria-labelledby="mTitle"><div class="shead"><h2 id="mTitle">Jetzt mitreden</h2>'
            '<a href="wandel/">Alle Termine →</a></div><div class="mrow">'
            + "".join(f'<a class="mi{" live" if live else ""}" href="{B.esc(u)}">{_tile(td, live)}<span class="mc"><span class="eyebrow">{B.esc(lbl)}</span>'
                      f'<strong>{B.esc(t)}</strong><span>{B.esc(x)}</span></span></a>' for _, td, live, lbl, t, x, u in rows[:4])
            + "</div></section>")


def _wandel(projekte):
    if not projekte:
        return ""
    wp = [p for p in projekte if p.get("wohnen")]
    pg = sum(p["wohnen"].get("preisguenstig") or 0 for p in wp)

    def soon(p):
        m, s = W._next(p)
        a = W._d(m.get("datum"))[0] if m else None
        return (0 if s == "now" else 1, a or date(2100, 1, 1))
    pick = sorted(projekte, key=soon)[:3]
    band = (f'<a class="wband" href="wohnen/"><strong>{B.esc(f"{pg:,}".replace(",", "’"))}</strong>'
            f'<span>preisgünstige Wohnungen sind geplant oder im Bau</span><em>Günstig wohnen →</em></a>') if pg else ""
    return ('<section class="block" aria-labelledby="wTitle"><div class="shead"><h2 id="wTitle">Wie sich Zug verändert</h2>'
            f'<a href="wandel/">Alle {len(projekte)} Vorhaben →</a></div>'
            f'<div class="wgrid w3">{"".join(W._card(p) for p in pick)}</div>{band}</section>')


def _parlament(politik):
    G = politik.get("geschaefte") or {}
    col = {p[0]: p[3] for p in (politik.get("ggr") or {}).get("parteien") or [] if len(p) > 3}
    badge = lambda p: f'<span class="pbadge"><i style="background:{B.esc(col.get(p, "var(--soft)"))}"></i>{B.esc(p)}</span>'
    rows = [(v.get("touched") or v["date"], f'<b>{B.esc(v["art"])}</b>' + "".join(badge(p) for p in v.get("parteien") or []),
             v["title"], f'<span class="gs {B.esc(v.get("tone") or "")}">{B.esc(v["status"])}</span>',
             (v.get("answer") or {}).get("url") or v["url"]) for v in G.get("vorstoesse") or []]
    rows += [(v["date"], f'<b>{B.esc(v.get("bereich") or "Vorlage")}</b><span class="muted">Stadtrat · Nr. {B.esc(v["nr"])}</span>',
              v["title"], f'<span class="gs">Bei {B.esc(v.get("stage") or "Kommission")}</span>', v["url"]) for v in G.get("vorlagen") or []]
    rows.sort(key=lambda r: r[0], reverse=True)
    if not rows:
        return ""
    return ('<section class="block" aria-labelledby="pTitle"><div class="shead"><h2 id="pTitle">Aus dem Parlament</h2>'
            '<a href="politik/#pGes">Alle Geschäfte →</a></div><div class="glist2">'
            + "".join(f'<a class="gr" href="{B.esc(u)}"><span class="d">{B.dlabel(d)}</span><span class="c"><span class="gk">{k}</span>'
                      f'<span class="t">{B.esc(t)}</span>{st}</span></a>' for d, k, t, st, u in rows[:3])
            + "</div></section>")


VOTE_ICON = ('<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'stroke-linejoin="round" aria-hidden="true"><path d="M4 13h16v7H4zM8 13V5h8v8M10 9l1.5 1.5L14 8"/></svg>')


def build_start_b(index_html, pol_news):
    """Neue Startseite (seit 2.11.2026). start-b.html leitet auf / um."""
    politik = B.load("politik", {})
    projekte = (B.load("wandel", {}).get("projekte") or [])
    p = index_html
    p = p.replace('<body data-page="start">', '<body data-page="start" class="v2">', 1)
    nv = _iso(politik.get("nextVoteDate"))
    if nv and nv >= B.TODAY:
        tile = (f'<a class="iitem ilink" href="politik/#pAbst"><span class="iic cal">{VOTE_ICON}</span>'
                f'<span class="itx"><strong>{B.WDL[nv.weekday()]} {nv.day}.{nv.month}.</strong><span>Abstimmung</span></span>{B.CHEVR.replace("<svg", "<svg class=\"ichev\"", 1)}</a>')
        p = p.replace("</a></div></div></div></div>\n<main", "</a>" + tile + "</div></div></div></div>\n<main", 1)
    extra = _mitreden(projekte, pol_news, politik) + _wandel(projekte)
    p = re.sub(r'(<div class="swipe" id="todayList"[^>]*>.*?</div>\s*</section>)', lambda m: m.group(1) + "\n" + extra, p, count=1, flags=re.S)
    p = re.sub(r'<section class="block" aria-labelledby="thTitle">.*?</section>', lambda m: "", p, count=1, flags=re.S)
    p = re.sub(r'(<section class="block hn".*?</section>)', lambda m: m.group(1) + "\n" + _parlament(politik), p, count=1, flags=re.S)
    redirect = ('<!doctype html><html lang="de-CH"><head><meta charset="utf-8"><title>zug.now</title>'
                '<meta name="robots" content="noindex"><link rel="canonical" href="https://zug.now/">'
                '<meta http-equiv="refresh" content="0; url=/"></head><body><a href="/">Zur Startseite</a></body></html>')
    return {"index.html": p, "start-b.html": redirect}
