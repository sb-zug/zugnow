"""zug.now – Einzelseiten pro Anlass: /agenda/<datum-titel>/

Jede Seite enthält Datum, Zeit, Ort, Beschreibung, Bild, Link zur Quelle, Kalenderdatei
(termin.ics) und strukturierte Daten (schema.org/Event) für Google.
Anlässe ohne nennenswerte Beschreibung erhalten noindex (dünne Seite) und fehlen in der Sitemap.
Wird von build.py aufgerufen: zuerst assign() (setzt e["page"]), am Schluss pages().

Vorbei (7.11.2026): Vergangene oder aus dem Kalender verschwundene Anlässe behalten ihre Seite noch
KEEP_DAYS Tage (Hinweis «vorbei» + kommende Anlässe am selben Ort, noindex) statt sofort 404.
Fehlt ein noch kommender Anlass (z. B. Quelle kurz ausgefallen), bleibt seine normale Seite bis zum Datum stehen.
Gespeichert in site/data/agenda_past.json (wird mit den Daten committet).
"""
import hashlib
import json
import re
import unicodedata
from datetime import timedelta

import build as B
import hubs as H

KEEP_DAYS = 30  # so lange bleibt die Seite eines vergangenen Anlasses stehen
PAST = B.SRC / "data" / "agenda_past.json"
SLIM = ("id", "title", "start", "end", "allday", "rhythm", "cancelled", "place", "location", "institution", "catLabel", "url", "source", "image", "page")
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


def archive(events):
    """Merkt sich alle aktuellen Anlässe und liefert die vergangenen/verschwundenen der letzten KEEP_DAYS Tage."""
    try:
        old = json.loads(PAST.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    cur = {e["page"] for e in events}
    limit = B.TODAY - timedelta(days=KEEP_DAYS)
    keep = {k: v for k, v in old.items() if k not in cur and B.dt(v.get("end") or v["start"]).date() >= limit}
    for e in events:
        keep[e["page"]] = {k: e.get(k) for k in SLIM} | {"teaser": (e.get("teaser") or "")[:300], "text": (e.get("text") or "")[:2000]}
    try:
        PAST.write_text(json.dumps(keep, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception as x:
        print("Archiv nicht gespeichert:", x)
    return [v for k, v in keep.items() if k not in cur]


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
    ort = ORT_SLUG.get(e.get("institution"))
    web = next((o[3] for o in H.ORTE if o[1] == e.get("institution")), "")
    if ort:  # Veranstalter nur, wenn sicher bekannt (Plattformen wie Eventfrog sind keine Veranstalter)
        data["organizer"] = {"@type": "Organization", "name": ort[1], **({"url": web} if web else {})}
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


def where(e):
    """Ort für den Titel – «Zug» kommt genau einmal vor (wichtiger Suchbegriff), z. B. «Lounge Gallery, Zug»."""
    pl = (e.get("place") or "").strip()
    if "zug" in pl.lower():
        return pl
    if "zug" in e["title"].lower():
        return pl
    return f"{pl}, Zug" if pl else "Zug"


def snippet(e, d, when, txt):
    """Suchtreffer (7.11.2026): Titel mit Wochentag, Datum und Ort; Beschreibung beginnt kurz mit Zeit und Ort,
    dann der Text; bleibt Platz, folgt der Mehrwert von zug.now (Kalender, weitere Anlässe)."""
    wd = B.WDL[d.weekday()]
    pl = where(e)
    stamp = f"{wd} {d.day}.{d.month}.{d.year}" + (f", {B.hm(e['start'])}" if e.get("_dup") and not e.get("allday") else "")
    title = f'{e["title"]} – {stamp}' + (f", {pl}" if pl else "")
    if len(title) > 62 and pl and "zug" not in e["title"].lower():  # langer Ort → nur «Zug»
        title = f'{e["title"]} – {stamp}, Zug'
    elif len(title) > 62:
        title = f'{e["title"]} – {stamp}'
    zeit = "" if e.get("allday") else f", {B.hm(e['start'])} Uhr"
    head = f'{wd} {d.day}. {MONTH[d.month - 1]} {d.year}{zeit} · {e.get("place") or "Zug"}. '
    tail = " Mit Kalendereintrag und weiteren Anlässen am selben Tag."
    room = 158 - len(head)
    body = (txt[:room - 2].rsplit(" ", 1)[0].rstrip(".,;:–- ") + " …") if len(txt) > room else txt
    if body and not body.endswith((".", "…", "!", "?")):
        body += "."
    desc = head + body + (tail if len(head + body + tail) <= 160 else "")
    return f"{title} | zug.now", re.sub(r"\s+", " ", desc).strip()


def past_page(frame, e, upcoming):
    """Seite eines vergangenen Anlasses: noindex, Hinweis «vorbei», kommende Anlässe am selben Ort."""
    d = B.dt(e["start"]).date()
    when = dlong(d) + ("" if e.get("allday") else " · " + B.hm(e["start"]) + " Uhr")
    same = [x for x in upcoming if (e.get("institution") and x.get("institution") == e.get("institution"))
            or (e.get("place") and x.get("place") == e.get("place"))]
    more, label = (same, f'Demnächst: {e.get("place")}') if same else (upcoming, "Demnächst in Zug")
    ort = ORT_SLUG.get(e.get("institution"))
    src = re.sub(r"^www\.", "", e.get("source") or "Veranstalter")
    note = f"Dieser Anlass hat am {d.day}.{d.month}.{d.year} stattgefunden."
    body = (
        '<div class="pagehead evhead">'
        + H._crumb(("Agenda", "agenda/"), (f"{d.day}.{d.month}.{d.year}", None))
        + '<span class="tag off" style="align-self:flex-start">Vorbei</span>'
        + f'<h1>{B.esc(e["title"])}</h1><p class="evwhen">{B.esc(when)} · {B.esc(e.get("place"))}</p></div>'
        + f'<section class="block"><p>{note}</p>'
        + (f'<p><a href="{B.esc(e.get("url"))}">Zum Anlass auf {B.esc(src)} →</a></p>' if e.get("url") else "") + "</section>"
    )
    if more:
        body += (f'<section class="block"><div class="shead"><h2>{B.esc(label)}</h2><a href="agenda/">Ganze Agenda →</a></div><div class="amtlist">'
                 + "".join(f'<a href="{x["page"]}"><span class="d">{B.dshort(B.dt(x["start"]).date())}</span>'
                           f'<span class="t">{B.esc(x["title"])}</span><span class="o">{B.esc(x.get("place"))} · {B.esc(x.get("catLabel"))}</span></a>'
                           for x in more[:8]) + "</div></section>")
    links = (([f'<a href="orte/{ort[0]}/">Programm {B.esc(ort[1])} →</a>'] if ort else [])
             + ['<a href="wochenende/">Wochenende in Zug →</a>', '<a href="agenda/">Ganze Agenda →</a>'])
    body += f'<section class="block"><p>{" · ".join(links)}</p></section>'
    return H._page(frame, e["page"], f'{e["title"]} – {d.day}.{d.month}.{d.year} (vorbei) | zug.now',
                   f'{when} · {e.get("place") or "Zug"}. Vorbei – kommende Anlässe in Zug auf zug.now.',
                   body, nav="agenda/", index=False, image=e.get("image"))


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
    links = [f'<a href="{H.month_slug(d)}">Alle Anlässe im {H.month_name(d)} →</a>', '<a href="agenda/">Ganze Agenda →</a>']
    if wa <= d <= wb:
        links.insert(0, '<a href="wochenende/">Alles am Wochenende →</a>')
    body += f'<section class="block"><p>{" · ".join(links)}</p></section>'
    title, desc = snippet(e, d, when, txt)
    html = H._page(frame, e["page"], title, desc, body, nav="agenda/", index=idx, image=e.get("image"))
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
    seen = {}
    for e in events:  # gleicher Titel am selben Tag → Uhrzeit in den Titel (keine doppelten Titel)
        seen.setdefault((e["title"], B.dt(e["start"]).date()), []).append(e)
    for grp in seen.values():
        for e in grp:
            e["_dup"] = len(grp) > 1
    for e in events:
        out[e["page"] + "index.html"] = page(frame, e, by_day[B.dt(e["start"]).date()])
        out[e["page"] + "termin.ics"] = ics(e)
    upcoming = [e for e in events if not e.get("cancelled")]
    past = archive(events)
    for e in past:
        if B.dt(e.get("end") or e["start"]).date() >= B.TODAY:  # kommt noch, fehlt nur in den Daten
            out[e["page"] + "index.html"] = page(frame, e, by_day.get(B.dt(e["start"]).date(), []))
            out[e["page"] + "termin.ics"] = ics(e)
        else:
            out[e["page"] + "index.html"] = past_page(frame, e, upcoming)
    gone = sum(1 for e in past if B.dt(e.get("end") or e["start"]).date() < B.TODAY)
    print(f"Einzelseiten: {len(events)} Anlässe, davon {len(_indexed)} indexierbar; {gone} vorbei (noindex), {len(past) - gone} aus dem Archiv")
    return out
