"""zug.now – Einzelseiten pro Anlass: /agenda/<datum-titel>/

Jede Seite enthält Datum, Zeit, Ort, Beschreibung, Bild, Link zur Quelle, Kalenderdatei
(termin.ics) und strukturierte Daten (schema.org/Event) für Google.
Anlässe ohne nennenswerte Beschreibung erhalten noindex (dünne Seite) und fehlen in der Sitemap.
Wird von build.py aufgerufen: zuerst assign() (setzt e["page"]), am Schluss pages().
"""
import hashlib
import json
import re
import unicodedata
from datetime import timedelta

import build as B
import hubs as H

MIN_TEXT = 60  # Zeichen Beschreibung, ab denen eine Seite indexiert wird
WDAY = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTH = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
ORT_SLUG = {o[1]: (o[0], o[2]) for o in H.ORTE}
_indexed = []


def slugify(s, n=60):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:n].rsplit("-", 1)[0] if len(s) > n else s) or "anlass"


def assign(events):
    """Vergibt jedem Anlass eine stabile Adresse (Datum + Titel; bei Doppel + Uhrzeit, dann + Kurz-ID)."""
    used = set()
    for e in sorted(events, key=lambda x: (x["start"], x["id"])):
        d = B.dt(e["start"])
        base = f"{d:%Y-%m-%d}-{slugify(e['title'])}"
        slug = base if base not in used else f"{base}-{d:%H%M}"
        if slug in used:
            slug = f"{base}-{hashlib.sha1(e['id'].encode()).hexdigest()[:6]}"
        used.add(slug)
        e["page"] = f"agenda/{slug}/"


def dlong(d):
    return f"{WDAY[d.weekday()]}, {d.day}. {MONTH[d.month - 1]} {d.year}"


def text_of(e):
    return (e.get("text") or e.get("teaser") or "").strip()


def address(e):
    """«Name, Strasse 1, 6300 Zug» → PostalAddress (best effort)."""
    parts = [p.strip() for p in re.sub(r"\s+", " ", e.get("location") or "").split(",") if p.strip()]
    adr = {"@type": "PostalAddress", "addressLocality": "Zug", "addressRegion": "ZG", "addressCountry": "CH"}
    if parts:
        m = re.match(r"(\d{4})\s+(.+)", parts[-1])
        if m:
            adr["postalCode"], adr["addressLocality"] = m.group(1), m.group(2)
            parts = parts[:-1]
        if len(parts) >= 2:
            adr["streetAddress"] = parts[-1]
    return adr


def jsonld(e):
    start, end = B.dt(e["start"]), B.dt(e["end"]) if e.get("end") else None
    data = {
        "@context": "https://schema.org", "@type": "Event", "name": e["title"],
        "startDate": start.date().isoformat() if e.get("allday") else start.isoformat(),
        "eventStatus": "https://schema.org/EventCancelled" if e.get("cancelled") else "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {"@type": "Place", "name": e.get("place") or "Zug", "address": address(e)},
        "url": H.SITE + e["page"],
    }
    if end and end > start:
        data["endDate"] = end.date().isoformat() if e.get("allday") else end.isoformat()
    if text_of(e):
        data["description"] = text_of(e)[:500]
    if e.get("image"):
        data["image"] = [e["image"]]
    if e.get("url"):
        data["sameAs"] = e["url"]
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def ics(e):
    def stamp(x):
        return B.dt(x).astimezone(B.ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    def esc(s):
        return str(s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

    if e.get("allday"):
        d = B.dt(e["start"]).date()
        de = B.dt(e["end"]).date() + timedelta(days=1) if e.get("end") else d + timedelta(days=1)
        when = [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{de:%Y%m%d}"]
    else:
        end = e.get("end") or (B.dt(e["start"]) + timedelta(hours=1)).isoformat()
        when = [f"DTSTART:{stamp(e['start'])}", f"DTEND:{stamp(end)}"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//zug.now//DE", "BEGIN:VEVENT", f"UID:{e['id']}@zug.now",
             f"DTSTAMP:{B.NOW.astimezone(B.ZoneInfo('UTC')):%Y%m%dT%H%M%SZ}", *when, f"SUMMARY:{esc(e['title'])}",
             f"LOCATION:{esc(e.get('location'))}", f"DESCRIPTION:{esc((e.get('teaser') or '') + chr(10) + chr(10) + H.SITE + e['page'])}",
             f"URL:{H.SITE}{e['page']}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def page(frame, e, same_day):
    d = B.dt(e["start"]).date()
    when = dlong(d) + ("" if e.get("allday") and not e.get("end") else " · " + B.time_label(e) + ("" if e.get("allday") else " Uhr"))
    txt = text_of(e)
    idx = len(txt) >= MIN_TEXT
    wa, wb = B.weekend()
    ort = ORT_SLUG.get(e.get("institution"))
    paras = "".join(f"<p>{B.esc(p)}</p>" for p in re.split(r"\n\s*\n|\n", txt) if p.strip()) or '<p class="note">Keine Beschreibung vorhanden – Details beim Veranstalter.</p>'
    src = re.sub(r"^www\.", "", e.get("source") or "Veranstalter")
    facts = [("Datum", B.esc(when)), ("Ort", B.esc(e.get("location") or e.get("place"))), ("Kategorie", B.esc(e.get("catLabel")))]
    if e.get("rhythm"):
        facts.append(("Rhythmus", B.esc(e["rhythm"])))
    if ort:
        facts.append(("Programm", f'<a href="orte/{ort[0]}/">Ganzes Programm {B.esc(ort[1])} →</a>'))
    more = [x for x in same_day if x is not e][:8]
    body = (
        f'<div class="pagehead evhead">'
        + H._crumb(("Agenda", "agenda/"), (f"{d.day}.{d.month}.{d.year}", None))
        + (f'<span class="tag off" style="align-self:flex-start">Abgesagt</span>' if e.get("cancelled") else f'<span class="eyebrow">{B.esc(e.get("catLabel"))} · {B.esc(e.get("place"))}</span>')
        + f'<h1>{B.esc(e["title"])}</h1><p class="evwhen">{B.esc(when)}</p></div>'
        + '<section class="block evd"><div class="evbody">'
        + paras
        + '<dl class="evfacts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>"
        + f'<div class="actions"><a class="btn primary" href="{B.esc(e.get("url"))}">Zum Anlass auf {B.esc(src)} →</a>'
        + ("" if e.get("cancelled") else f'<a class="btn" href="{e["page"]}termin.ics" download>{B.CAL}In Kalender</a>') + "</div>"
        + f'<p class="note">Angaben automatisch übernommen von {B.esc(src)}. Massgebend sind die Angaben des Veranstalters.</p>'
        + "</div>"
        + (f'<div class="evimg">{B.img(e["image"])}</div>' if e.get("image") else "")
        + "</div></section>"
    )
    if more:
        body += (f'<section class="block"><div class="shead"><h2>Mehr am {WDAY[d.weekday()]}, {d.day}.{d.month}.</h2>'
                 f'<a href="agenda/">Ganze Agenda →</a></div><div class="amtlist">'
                 + "".join(f'<a href="{x["page"]}"{"" if x.get("allday") else " data-end=" + chr(34) + B.esc(x.get("end") or x["start"]) + chr(34)}>'
                           f'<span class="d">{"ganztags" if x.get("allday") else B.hm(x["start"])}</span>'
                           f'<span class="t">{B.esc(x["title"])}</span><span class="o">{B.esc(x.get("place"))} · {B.esc(x.get("catLabel"))}</span></a>' for x in more)
                 + "</div></section>")
    links = ['<a href="agenda/">Ganze Agenda →</a>']
    if wa <= d <= wb:
        links.insert(0, '<a href="wochenende/">Alles am Wochenende →</a>')
    body += f'<section class="block"><p>{" · ".join(links)}</p></section>'
    title = f'{e["title"]} – {d.day}.{d.month}.{d.year}, {e.get("place") or "Zug"}'
    desc = (txt[:150].rsplit(" ", 1)[0] + " …") if len(txt) > 155 else (txt or f'{when} in {e.get("place") or "Zug"}.')
    html = H._page(frame, e["page"], f"{title} | zug.now", f"{when} · {desc}", body, nav="agenda/", index=idx, image=e.get("image"))
    html = html.replace("</head>", f'<script type="application/ld+json">{jsonld(e)}</script>\n</head>', 1)
    if idx:
        _indexed.append(e["page"])
    return html


def pages(agenda_html, events):
    frame = H._frame(agenda_html)
    by_day = {}
    for e in events:
        by_day.setdefault(B.dt(e["start"]).date(), []).append(e)
    out = {}
    for e in events:
        out[e["page"] + "index.html"] = page(frame, e, by_day[B.dt(e["start"]).date()])
        out[e["page"] + "termin.ics"] = ics(e)
    # /agenda/ selbst → Agenda-Seite
    print(f"Einzelseiten: {len(events)} Anlässe, davon {len(_indexed)} indexierbar")
    return out
