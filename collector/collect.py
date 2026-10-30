#!/usr/bin/env python3
"""zug.now – Sammler.

Holt Live-Daten der Stadt Zug aus offenen Quellen und schreibt JSON nach site/data/.
Nur Python-Standardbibliothek (läuft so direkt in GitHub Actions).

  python collector/collect.py                 # live
  python collector/collect.py --offline tests/fixtures   # gegen gespeicherte Rohdaten

Quellen:
  News     https://stadtzug.ch/de/news?content_category=news (HTML, inkl. Artikelbild)
  Agenda   https://veranstaltungen.zug.ch/events/ical       (OneGov iCal, auf Stadt Zug gefiltert)
  Amtlich  https://amtsblatt.zg.ch/api/v1/publications       (eSHAB REST-API, Absender «Stadt Zug»)
  Theater  https://www.theatercasino.ch/programm/veranstaltungen (HTML-Spielplan, in die Agenda gemischt)
  Galvanik https://galvanik-zug.ch/programm/                 (HTML-Programm + Detailseite für Uhrzeit/Bild)
Bibliothek, Museum Burg, Kunsthaus, Musikschule sind in der OneGov-Agenda enthalten
und werden über Ort/Kategorie als Institution markiert.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Zurich")
UA = "zug.now-collector/1.0 (+https://zug.now; Prototyp, nicht-kommerziell)"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data"

NEWS_URL = "https://stadtzug.ch/de/news?content_category=news"
ICAL_URL = "https://veranstaltungen.zug.ch/events/ical"
AMTSBLATT_URL = ("https://amtsblatt.zg.ch/api/v1/publications?publicationStates=PUBLISHED"
                 "&cantons=ZG&pageRequest.size=300&pageRequest.sortOrders=publicationDate:DESC")
AMTSBLATT_DETAIL = "https://amtsblatt.zg.ch/#!/search/publications/detail/{id}"

AGENDA_DAYS = 60          # so weit voraus
EVENT_IMAGES_MAX = 150    # Bilder (og:image) für die nächsten n Anlässe; gecacht, nur neue werden abgerufen
NEWS_IMAGES_MAX = 10


# ---------------------------------------------------------------- HTTP

def fetch(url: str, accept: str = "*/*", timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


# ---------------------------------------------------------------- News (stadtzug.ch)

_LI = re.compile(r"<li\b[^>]*>(.*?)</li>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _text(s: str) -> str:
    return html.unescape(_TAG.sub("", s)).strip()


def parse_news_list(page: str) -> list[dict]:
    items = []
    for li in _LI.findall(page):
        a = re.search(r'<a href="(https://stadtzug\.ch/de/news/20[^"]+)"[^>]*>(.*?)</a>', li, re.S)
        if not a:
            continue
        d = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", li)
        typ = re.search(r'tablet:block desktop:col-span-6"><p[^>]*><span>([^<]+)</span>', li)
        lead = re.search(r'dxp-typo-body[^"]*"[^>]*>(.*?)</div>', li, re.S)
        items.append({
            "id": a.group(1).rstrip("/").split("/")[-1],
            "url": a.group(1),
            "title": _text(a.group(2)),
            "date": f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None,
            "type": _text(typ.group(1)) if typ else None,
            "lead": re.sub(r"\s+", " ", _text(lead.group(1))) if lead else "",
            "image": None,
            "source": "Stadt Zug",
        })
    return items


# News-Themen: Stichwortregeln (Teilwort, Gross/klein egal). Titel zählt doppelt; Gleichstand → Reihenfolge hier.
# Anpassen: Begriff in die passende Liste eintragen. Zahl nach «:» = Gewicht (Standard 1).
NEWS_TOPICS = [
    ("politik", "Politik & Verwaltung", "ggr, gemeinderat, stadtrat, stadtpräsident, abstimmung, urnengang, wahlen, parlament, "
     "motion, interpellation, postulat, initiative, referendum, vernehmlassung, budget, voranschlag, jahresrechnung, "
     "finanzplan, steuer, legislatur, kommission, stadtverwaltung, stadtkanzlei, rechtssammlung, reglement"),
    ("bauen", "Bauen & Planung", "baugesuch:2, bebauungsplan:2, gestaltungsplan:2, ortsplanung:2, zonenplan, richtplan, "
     "gebietsplanung, stadtentwicklung, areal, überbauung, bauprojekt, neubau, umbau, sanierung, baustelle, hochhaus, "
     "wohnungen, wohnraum, siedlung, liegenschaft, planauflage, öffentlich aufgelegt"),
    ("mobilitaet", "Mobilität & Verkehr", "verkehr, velo, fussverkehr, fussgänger, schulweg:2, strasse, trottoir, parkier, "
     "parkplatz, tempo 30, buslinie, bushaltestelle, ortsbus, bahnhof, stadtbahn, zugerland verkehrsbetriebe, sperrung, umleitung, signalisation, "
     "winterdienst:2, mobilität, e-scooter, ladestation"),
    ("bildung", "Bildung & Schule", "schule, schulhaus, kindergarten, schüler, lehrperson, bildung, tagesschule, "
     "schulergänzende, kita, betreuungsgutschein, lehrstelle, ausbildung"),
    ("kultur", "Kultur & Freizeit", "kultur, museum, kunst, konzert, theater, ausstellung, bibliothek, festival, "
     "stadtfest, seefest, chilbi, fasnacht, jubiläum, sport, sportanlage, strandbad, hallenbad, badi, eishalle, "
     "freizeit, spielplatz, verein, märt"),
    ("umwelt", "Umwelt & Energie", "umwelt, energie, klima, abfall, entsorgung, recycling, sammelstelle, grüngut, "
     "wasserversorgung, natur, biodiversität, bäume, baumpflanz, wald, solar, fernwärme, energiestadt, lärm, littering"),
    ("soziales", "Soziales & Gesundheit", "sozial, quartier, senior, alterszentrum, altersheim, jugend, familie, "
     "gesundheit, integration, asyl, spitex, pflege, freiwillig, gesellschaft, gleichstellung, prävention"),
]
_NEWS_TOPICS = [(cid, label, [(k.split(":")[0].strip().lower(), int(k.split(":")[1]) if ":" in k else 1)
                              for k in keys.split(",")]) for cid, label, keys in NEWS_TOPICS]


def news_topic(title: str, lead: str = "") -> tuple[str, str]:
    t, l = (title or "").lower(), (lead or "").lower()
    best, score = ("weitere", "Weitere"), 0
    for cid, label, keys in _NEWS_TOPICS:
        sc = sum(w * (2 * (k in t) + (k in l)) for k, w in keys)
        if sc > score:
            best, score = (cid, label), sc
    return best


_FOOTER_IMG = re.compile(r"Unicef|Energiestadt|SwissApps|Label%20Employer|Favicon", re.I)
_CDN_IMG = re.compile(r"https://cdn\.zg\.ch/\.imaging/flex/[^\"'\s\\]+?/width/(\d+)/[^\"'\s\\]+?\.(?:jpe?g|png|webp)", re.I)


def pick_article_image(page: str, want: int = 1120) -> str | None:
    """Grösstes Inhaltsbild bis `want` px Breite; Footer-Logos ignorieren."""
    best = None
    for m in _CDN_IMG.finditer(page):
        url, w = m.group(0), int(m.group(1))
        if _FOOTER_IMG.search(url):
            continue
        if w <= want and (best is None or w > best[0]):
            best = (w, url)
    return best[1] if best else None


# ---------------------------------------------------------------- Agenda (OneGov iCal)

def _unfold(ics: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", ics).splitlines()


def _ical_unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _ical_dt(key: str, val: str) -> tuple[datetime, bool]:
    """-> (lokale Zeit, ganztägig?)"""
    if "VALUE=DATE" in key or re.fullmatch(r"\d{8}", val):
        return datetime.strptime(val[:8], "%Y%m%d").replace(tzinfo=TZ), True
    if val.endswith("Z"):
        return datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TZ), False
    tz = re.search(r"TZID=([^;:]+)", key)
    return datetime.strptime(val[:15], "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(tz.group(1)) if tz else TZ), False


def parse_ics(ics: str) -> list[dict]:
    events, cur = [], None
    for line in _unfold(ics):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            cur[k] = v
    out = []
    for e in events:
        sk = next((k for k in e if k.startswith("DTSTART")), None)
        if not sk:
            continue
        start, allday = _ical_dt(sk, e[sk])
        ek = next((k for k in e if k.startswith("DTEND")), None)
        end = _ical_dt(ek, e[ek])[0] if ek else None
        geo = None
        if "GEO" in e:
            try:
                lat, lon = (float(x) for x in e["GEO"].split(";"))
                geo = [lat, lon]
            except ValueError:
                pass
        out.append({
            "uid": e.get("UID", ""),
            "title": _ical_unescape(e.get("SUMMARY", "")),
            "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "allday": allday or (end is not None and (end - start) >= timedelta(hours=20)),
            "location": _ical_unescape(e.get("LOCATION", "")).replace("\t", " "),
            "geo": geo,
            "tags": [t.strip() for t in _ical_unescape(e.get("CATEGORIES", "")).split(",") if t.strip()],
            "description": _ical_unescape(e.get("DESCRIPTION", "")),
            "url": e.get("URL", "").strip(),
            "rrule": e.get("RRULE"),
        })
    return out


_WD = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
_WD_DE = {"MO": "Montag", "TU": "Dienstag", "WE": "Mittwoch", "TH": "Donnerstag", "FR": "Freitag", "SA": "Samstag", "SU": "Sonntag"}


_WD_SHORT = {"MO": "Mo", "TU": "Di", "WE": "Mi", "TH": "Do", "FR": "Fr", "SA": "Sa", "SU": "So"}


def rhythm_text(days: list[str]) -> str:
    idx = sorted({_WD.index(d) for d in days if d in _WD})
    if len(idx) == 7:
        return "täglich"
    if len(idx) == 1:
        return "jeden " + _WD_DE[_WD[idx[0]]]
    if len(idx) >= 3 and idx == list(range(idx[0], idx[-1] + 1)):
        return f"{_WD_SHORT[_WD[idx[0]]]}–{_WD_SHORT[_WD[idx[-1]]]}"
    return ", ".join(_WD_SHORT[_WD[i]] for i in idx)


def next_occurrence(start: datetime, rrule: str, today: date) -> tuple[datetime | None, str]:
    """Nächster Termin ab `today` für FREQ=DAILY/WEEKLY (mehr nutzt OneGov kaum) + Rhythmus-Text."""
    r = dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)
    until = None
    if "UNTIL" in r:
        u = r["UNTIL"]
        until = (datetime.strptime(u, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TZ).date()
                 if "T" in u else datetime.strptime(u[:8], "%Y%m%d").date())
    freq = r.get("FREQ")
    days = [d[-2:] for d in r.get("BYDAY", "").split(",") if d] or [_WD[start.weekday()]]
    rhythm = "täglich" if freq == "DAILY" else rhythm_text(days)
    if freq not in ("DAILY", "WEEKLY"):
        return (start if start.date() >= today else None), ""
    d = max(today, start.date())
    for _ in range(400):
        if until and d > until:
            return None, rhythm
        if freq == "DAILY" or _WD[d.weekday()] in days:
            return start.replace(year=d.year, month=d.month, day=d.day), rhythm
        d += timedelta(days=1)
    return None, rhythm


# Stadt Zug: PLZ 6300–6303 (Zug), 6317 Oberwil b. Zug; sonst Koordinaten im Stadtgebiet
_ZUG_PLZ = re.compile(r"\b63(?:00|01|02|03|17)\b")
_OTHER_TOWN = re.compile(r"\b(Baar|Cham|Steinhausen|Hünenberg|Risch|Rotkreuz|Walchwil|Menzingen|Neuheim|Oberägeri|Unterägeri|Luzern|Zürich|Winterthur|Langnau)\b", re.I)
_ZUG_VENUES = re.compile(r"Bibliothek Zug|Burg Zug|Kunsthaus Zug|Chollerhalle|Gewürzmühle|Theater Casino|Industrie45|Siehbach|Landsgemeindeplatz|Zündhölzli|Bahnhofshalle Zug|Kantonsschule Zug|Kino Gotthard|Shedhalle|Hafen Zug", re.I)
_ZUG_BBOX = (47.095, 47.195, 8.470, 8.560)   # lat min/max, lon min/max (grob Stadtgebiet)


def is_stadt_zug(ev: dict) -> bool:
    loc = ev["location"]
    if _ZUG_PLZ.search(loc):
        return True
    if _OTHER_TOWN.search(loc):
        return False
    if _ZUG_VENUES.search(loc) or re.search(r"(?:,|\s)Zug\s*$|^Zug\b", loc):
        return True
    if ev["geo"]:
        lat, lon = ev["geo"]
        a, b, c, d = _ZUG_BBOX
        return a <= lat <= b and c <= lon <= d
    return False


CAT_MAP = [  # (Kategorie-ID, OneGov-Tags) – erste Übereinstimmung gewinnt
    ("kinder", {"Familie & Kind", "Jugend", "Ludothek", "Schule"}),
    ("maerkte", {"Markt", "Fest", "Brauchtum", "Kulinarik"}),
    ("kultur", {"Konzert", "Musik", "Musikschule", "Kultur", "Kunst", "Ausstellung", "Theater", "Literatur/Lesung", "Tanz", "Film"}),
    ("treff", {"Treffen/Austausch", "Vereine", "Alter", "Mitwirkung", "Religion"}),
    ("sport", {"Sport", "Natur", "Gesundheit"}),
]
CAT_LABEL = {"kinder": "Kinder & Familie", "maerkte": "Märkte & Feste", "kultur": "Kultur & Musik",
             "treff": "Treffpunkte", "sport": "Sport & Natur", "weitere": "Weitere"}

INSTITUTIONS = [
    ("bibliothek", "Bibliothek Zug", re.compile(r"Bibliothek Zug|St\.-Oswalds-Gasse 21", re.I), "Bibliothek"),
    ("burg", "Museum Burg Zug", re.compile(r"Burg Zug", re.I), None),
    ("kunsthaus", "Kunsthaus Zug", re.compile(r"Kunsthaus Zug", re.I), None),
    ("musikschule", "Musikschule Zug", re.compile(r"Musikschule", re.I), "Musikschule"),
    ("theatercasino", "Theater Casino Zug", re.compile(r"Theater Casino", re.I), None),
    ("galvanik", "Galvanik", re.compile(r"Galvanik", re.I), None),
]


_KIDS = re.compile(r"Kinder|Kids|Jahre\)|\d\s*(?:-|–|bis)\s*\d+\s*Jahre|Familie|Bookworm|Bilderbuch|Märli|Geschichtenzeit|niños|儿童", re.I)


def categorize(tags: list[str], title: str = "") -> str:
    if _KIDS.search(title):
        return "kinder"
    s = set(tags)
    for cid, keys in CAT_MAP:
        if s & keys:
            return cid
    return "weitere"


def institution(ev: dict) -> str | None:
    for iid, _name, rx, tag in INSTITUTIONS:
        if rx.search(ev["location"]) or (tag and tag in ev["tags"]):
            return iid
    return None


def short_place(loc: str) -> str:
    """'Bibliothek Zug, St.-Oswalds-Gasse 21, 6300 Zug' -> 'Bibliothek Zug'"""
    first = loc.split(",")[0].split("|")[0].strip()
    return first or loc


def rrule_until(rrule: str) -> date | None:
    m = re.search(r"UNTIL=(\d{8})(T\d{6}Z?)?", rrule)
    if not m:
        return None
    if m.group(2) and m.group(2).endswith("Z"):
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TZ).date()
    return datetime.strptime(m.group(1), "%Y%m%d").date()


_ONGOING = re.compile(r"Ausstellung|Dauer|Skulpturenweg|Installation|Schaudepot", re.I)


def is_ongoing(ev: dict, title: str, start: datetime, end: datetime, rhythm: str) -> bool:
    """Laufende Angebote (Ausstellungen, Tagesangebote) statt einzelner Anlässe."""
    long_slot = (end - start) >= timedelta(hours=8)
    if ev["allday"] and (end - start) >= timedelta(days=2):
        return True
    if ev["rrule"]:
        many_days = rhythm == "täglich" or "–" in rhythm or rhythm.count(",") >= 1
        return bool(long_slot or many_days or _ONGOING.search(title) or "Ausstellung" in ev["tags"])
    return long_slot and bool(_ONGOING.search(title) or "Ausstellung" in ev["tags"])


def build_agenda(raw: list[dict], today: date) -> list[dict]:
    horizon = today + timedelta(days=AGENDA_DAYS)
    seen, out = set(), []
    for ev in raw:
        if not is_stadt_zug(ev):
            continue
        start = datetime.fromisoformat(ev["start"])
        end = datetime.fromisoformat(ev["end"]) if ev["end"] else start
        rhythm = ""
        if ev["rrule"]:
            nxt, rhythm = next_occurrence(start, ev["rrule"], today)
            if nxt is None:
                continue
            end, start = nxt + (end - start), nxt
        if end.date() < today or start.date() > horizon:
            continue
        key = (ev["title"], start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        cancelled = bool(re.search(r"abgesagt|annulliert|fällt aus", ev["title"], re.I))
        title = re.sub(r"\s*[–-]\s*ABGESAGT!?\s*$", "", ev["title"], flags=re.I)
        cat = categorize(ev["tags"], title)
        until = rrule_until(ev["rrule"]) if ev["rrule"] else None
        if until and (until - start.date()).days < 2:   # «täglich» bis morgen = Einzeltermin
            rhythm, until = "", None
        ongoing = is_ongoing(ev, title, start, end, rhythm)
        # iCal-URL zeigt auf 404; gültig ist /event/<slug>-<YYYY-MM-DD> des jeweiligen Termins
        slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", ev["uid"].split("@")[0])
        url = f"https://veranstaltungen.zug.ch/event/{slug}-{start.date().isoformat()}" if slug else ev["url"]
        out.append({
            "id": ev["uid"].split("@")[0],
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat() if ev["end"] else None,
            "allday": ev["allday"],
            "rhythm": rhythm,
            "ongoing": ongoing,
            "until": until.isoformat() if until else None,
            "cancelled": cancelled,
            "place": short_place(ev["location"]),
            "location": ev["location"],
            "cat": cat,
            "catLabel": CAT_LABEL[cat],
            "tags": ev["tags"],
            "institution": institution(ev),
            "teaser": re.sub(r"\s+", " ", ev["description"])[:220],
            "text": re.sub(r"\n{3,}", "\n\n", ev["description"]).strip()[:1200],
            "url": url,
            "image": None,
            "source": "veranstaltungen.zug.ch",
        })
    out.sort(key=lambda e: e["start"])
    return out


_OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.I)


def og_image(page: str) -> str | None:
    m = _OG_IMAGE.search(page) or re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', page, re.I)
    return html.unescape(m.group(1)) if m else None


# ---------------------------------------------------------------- Kulturhäuser (eigene Websites, HTML)
# Theater Casino und Galvanik fehlen in der OneGov-Agenda → direkt von ihren Programmseiten.

TCZ_URL = "https://www.theatercasino.ch/programm/veranstaltungen"
GALVANIK_URL = "https://galvanik-zug.ch/programm/"
GALVANIK_BASE = "https://galvanik-zug.ch"

_TCZ_TOKEN = re.compile(r'id="month-(\d{4})-(\d{2})"|<div id="node-([0-9a-f-]+)" class="event-date-entry\b')
_MONTHS_DE = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7,
              "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12}


def _house_event(eid, title, sub, start, allday, url, cat, tags, inst, place, location, source, cancelled=False, soldout=False):
    teaser = sub + (" · Ausverkauft" if soldout else "")
    return {
        "id": eid, "title": title, "start": start.isoformat(), "end": None, "allday": allday,
        "rhythm": "", "ongoing": False, "until": None, "cancelled": cancelled,
        "place": place, "location": location, "cat": cat, "catLabel": CAT_LABEL[cat], "tags": tags,
        "institution": inst, "teaser": teaser[:220], "text": teaser[:1200], "url": url, "image": None,
        "source": source,
    }


def parse_theatercasino(page: str) -> list[dict]:
    toks = list(_TCZ_TOKEN.finditer(page))
    year, out = None, []
    for i, m in enumerate(toks):
        if m.group(1):
            year = int(m.group(1))
            continue
        chunk = page[m.end(): toks[i + 1].start() if i + 1 < len(toks) else len(page)]
        d = re.search(r'date-font[^>]*>\s*\w*\s*(\d{1,2})\.(\d{1,2})\.', chunk)
        title = re.search(r'event-title-text[^>]*>(.*?)</strong>', chunk, re.S)
        if not (d and title and year):
            continue
        hm = re.search(r'(\d{1,2}):(\d{2})\s*Uhr', chunk)
        day, mon = int(d.group(1)), int(d.group(2))
        start = datetime(year, mon, day, int(hm.group(1)) if hm else 0, int(hm.group(2)) if hm else 0, tzinfo=TZ)
        link = re.search(r'href="(https://www\.theatercasino\.ch/programm/veranstaltungen/[^"]+)"', chunk)
        sub = re.search(r'<p class="fs-lg[^"]*">(.*?)</p>', chunk, re.S)
        cats = re.search(r'data-categories="([^"]*)"', page[m.start(): m.end() + 400])
        junges = re.search(r'data-junges="([^"]+)"', page[m.start(): m.end() + 400])
        t = _text(title.group(1))
        tags = [c for c in (cats.group(1).split(",") if cats else []) if c]
        out.append(_house_event(
            "tcz-" + m.group(3), t, re.sub(r"\s+", " ", _text(sub.group(1))) if sub else "", start, not hm,
            html.unescape(link.group(1)) if link else TCZ_URL,
            "kinder" if junges or _KIDS.search(t) else "kultur", tags, "theatercasino",
            "Theater Casino Zug", "Theater Casino Zug, Artherstrasse 2–4, 6300 Zug", "theatercasino.ch",
            cancelled=bool(re.search(r"abgesagt", chunk, re.I)), soldout="isSoldOut" in chunk))
    return out


def tcz_image(page: str) -> str | None:
    """Erstes Bühnenbild der Detailseite, Variante ~768 px."""
    m = re.search(r'<img class="img-lazy[^"]*object-fit-cover"[^>]*data-srcset="([^"]+)"', page)
    if not m:
        return None
    cands = [c.strip().split() for c in m.group(1).split(",") if c.strip()]
    cands = [(int(w[:-1]), u) for u, w in (c for c in cands if len(c) == 2) if w.endswith("w")]
    fit = [c for c in cands if c[0] <= 800] or cands
    return max(fit)[1] if fit else None


_GALV_CAT = {"Kinder": "kinder", "Familie": "kinder", "Markt": "maerkte"}


def parse_galvanik(page: str) -> list[dict]:
    year, out = None, []
    for m in re.finditer(r'<tr class="year-row"><td[^>]*>(\d{4})</td></tr>|<tr class="event[^"]*">(.*?)</tr>', page, re.S):
        if m.group(1):
            year = int(m.group(1))
            continue
        row = m.group(2)
        href = re.search(r'href="(/programm/[^"]+)"', row)
        day = re.search(r'class="day">(\d{1,2})\.', row)
        mon = re.search(r'class="month">([^<.]+)', row)
        title = re.search(r'class="title">(.*?)</span>', row, re.S)
        if not (href and day and mon and title and year):
            continue
        mnum = _MONTHS_DE.get(mon.group(1).strip().lower()[:3])
        if not mnum:
            continue
        serie = re.search(r'class="serie">(.*?)</span>', row, re.S)
        cat = re.search(r'class="category[^"]*">\s*([^<]+?)\s*</div>', row)
        catname = cat.group(1) if cat else ""
        t = _text(title.group(1))
        out.append(_house_event(
            "galvanik-" + href.group(1).strip("/").split("/")[-1], t,
            re.sub(r"\s+", " ", _text(serie.group(1))) if serie else catname,
            datetime(year, mnum, int(day.group(1)), tzinfo=TZ), True, GALVANIK_BASE + href.group(1),
            "kinder" if _KIDS.search(t) else _GALV_CAT.get(catname, "kultur"), [catname] if catname else [],
            "galvanik", "Galvanik", "Kulturzentrum Galvanik, Chamerstrasse 173, 6300 Zug", "galvanik-zug.ch",
            cancelled=bool(re.search(r"abgesagt|verschoben", t, re.I))))
    return out


def galvanik_detail(page: str) -> dict:
    """Uhrzeit und Bild von der Detailseite."""
    hm = re.search(r'date-time[\s\S]{0,200}?(\d{1,2}):(\d{2})\s*Uhr', page)
    return {"hm": f"{int(hm.group(1)):02d}:{hm.group(2)}" if hm else None, "image": og_image(page)}


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9äöü]+", "", t.lower())


def merge_events(base: list[dict], extra: list[dict], today: date) -> list[dict]:
    """Zusätzliche Anlässe anfügen: nur im Zeitfenster, ohne Doppel (gleicher Tag, ähnlicher Titel)."""
    horizon = today + timedelta(days=AGENDA_DAYS)
    have = {}
    for e in base:
        have.setdefault(e["start"][:10], []).append(_norm_title(e["title"]))
    out = list(base)
    for e in extra:
        d = date.fromisoformat(e["start"][:10])
        if d < today or d > horizon:
            continue
        n = _norm_title(e["title"])
        if any(n == o or (min(len(n), len(o)) >= 6 and (n in o or o in n)) for o in have.get(e["start"][:10], [])):
            continue
        have.setdefault(e["start"][:10], []).append(n)
        out.append(e)
    out.sort(key=lambda e: e["start"])
    return out


# ---------------------------------------------------------------- Amtlich (eSHAB API)

RUBRIC_LABEL = {
    "BP": "Baugesuch", "RS": "Rechtsetzung & Politik", "AB": "Abstimmung", "WA": "Wahlen",
}


_PRIVATE = re.compile(r"Testament|Erbschaft|Erbenruf|Verschollen|Schuldenruf|Konkurs|Betreibung|Nachlass|Kraftloserklärung|Einbürgerung", re.I)


def amtlich_label(meta: dict) -> str:
    title = (meta.get("title") or {}).get("de", "")
    if title.startswith("Kommunale Baugesuch"):
        return "Baugesuch"
    if "Grossen Gemeinderat" in title:
        return "Gemeinderat"
    if re.search(r"Abstimmung|Urnengang", title):
        return "Abstimmung"
    if re.search(r"Wahl", title):
        return "Wahlen"
    if re.search(r"Planauflage|Bebauungsplan|Zonenplan|Auflage", title):
        return "Planauflage"
    return RUBRIC_LABEL.get(meta.get("rubric", "")[:2], "Publikation")


def parse_amtsblatt(data: dict) -> list[dict]:
    out = []
    for p in data.get("content", []):
        m = p["meta"]
        office = (m.get("registrationOffice") or {}).get("displayName", "")
        if not office.startswith("Stadt Zug"):
            continue
        title = (m.get("title") or {}).get("de", "")
        if _PRIVATE.search(title):   # Meldungen über Privatpersonen nicht übernehmen
            continue
        out.append({
            "id": m["id"],
            "date": m["publicationDate"][:10],
            "label": amtlich_label(m),
            "title": re.sub(r"^Kommunale Baugesuchspublikation:\s*", "", title),
            "office": office,
            "number": m.get("publicationNumber"),
            "expires": (m.get("expirationDate") or "")[:10] or None,
            "url": AMTSBLATT_DETAIL.format(id=m["id"]),
            "source": "amtsblatt.zg.ch",
        })
    return out


# ---------------------------------------------------------------- Ablauf

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def write_json(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


def run(offline: Path | None, only: set[str]) -> int:
    now = datetime.now(TZ)
    meta = load_json(OUT / "meta.json", {"sources": {}})
    cache = load_json(OUT / "image_cache.json", {})
    errors = 0

    def source(name: str, fn):
        nonlocal errors
        if only and name not in only:
            return
        try:
            data = fn()
            write_json(f"{name}.json", data)
            meta["sources"][name] = {"ok": True, "updated": now.isoformat(timespec="minutes"), "count": len(data)}
            print(f"✓ {name}: {len(data)} Einträge")
        except Exception as e:  # Quelle down → alte Datei bleibt stehen
            errors += 1
            prev = meta["sources"].get(name, {})
            meta["sources"][name] = {**prev, "ok": False, "error": f"{type(e).__name__}: {e}", "failed": now.isoformat(timespec="minutes")}
            print(f"✗ {name}: {e}", file=sys.stderr)

    def get(url: str, fixture: str, accept="*/*") -> str:
        if offline:
            return (offline / fixture).read_text("utf-8")
        return fetch(url, accept)

    def image_for(url: str, fixture: str | None, picker) -> str | None:
        if url in cache:
            return cache[url]
        if offline:
            p = offline / fixture if fixture else None
            img = picker(p.read_text("utf-8")) if p and p.exists() else None
        else:
            try:
                img = picker(fetch(url))
            except Exception:
                return None
        cache[url] = img
        return img

    def news():
        items = parse_news_list(get(NEWS_URL, "news_list.html"))
        for it in items:
            it["topic"], it["topicLabel"] = news_topic(it["title"], it["lead"])
        for it in items[:NEWS_IMAGES_MAX]:
            fx = "news_article.html" if it["id"] == "z-fuess-fahrsch-besser" else None
            it["image"] = image_for(it["url"], fx, pick_article_image)
        return items

    def agenda():
        today = date(2026, 10, 29) if offline else now.date()
        items = build_agenda(parse_ics(get(ICAL_URL, "events.ics", "text/calendar")), today)
        for it in items[:EVENT_IMAGES_MAX]:
            if it["url"]:
                it["image"] = image_for(it["url"], None, og_image)
        # Kulturhäuser: Ausfall einer Website stoppt die Agenda nicht
        for name, url, fixture, parser in (("theatercasino", TCZ_URL, "theatercasino.html", parse_theatercasino),
                                           ("galvanik", GALVANIK_URL, "galvanik.html", parse_galvanik)):
            try:
                extra = parser(get(url, fixture))
                if not extra:
                    raise ValueError("keine Anlässe erkannt (Seitenaufbau geändert?)")
                n0 = len(items)
                items = merge_events(items, extra, today)
                meta["sources"][name] = {"ok": True, "updated": now.isoformat(timespec="minutes"), "count": len(items) - n0}
                print(f"  ✓ {name}: {len(extra)} gefunden, {len(items) - n0} übernommen")
            except Exception as e:
                meta["sources"][name] = {**meta["sources"].get(name, {}), "ok": False,
                                         "error": f"{type(e).__name__}: {e}", "failed": now.isoformat(timespec="minutes")}
                print(f"  ✗ {name}: {e}", file=sys.stderr)
        for it in items:
            if it["source"] == "theatercasino.ch" and it["url"] != TCZ_URL:
                base = it["url"].split("?")[0]   # ein Bild pro Produktion, nicht pro Termin
                fx = "theatercasino_event.html" if "wiener-concert-verein" in base else None
                it["image"] = image_for(base, fx, tcz_image)
            elif it["source"] == "galvanik-zug.ch":
                fx = "galvanik_event.html" if "noise-fest" in it["url"] else None
                key, det = "detail:" + it["url"], None
                if key in cache:
                    det = cache[key]
                elif offline:
                    det = galvanik_detail((offline / fx).read_text("utf-8")) if fx else None
                else:
                    try:
                        det = cache[key] = galvanik_detail(fetch(it["url"]))
                    except Exception:
                        pass
                if det:
                    it["image"] = det.get("image")
                    if det.get("hm"):
                        h, mi = map(int, det["hm"].split(":"))
                        it["start"] = datetime.fromisoformat(it["start"]).replace(hour=h, minute=mi).isoformat()
                        it["allday"] = False
        items.sort(key=lambda e: e["start"])
        return items

    def amtlich():
        return parse_amtsblatt(json.loads(get(AMTSBLATT_URL, "amtsblatt.json", "application/json")))

    source("news", news)
    source("agenda", agenda)
    source("amtlich", amtlich)

    meta["generated"] = now.isoformat(timespec="minutes")
    write_json("meta.json", meta)
    # Cache klein halten
    write_json("image_cache.json", dict(list(cache.items())[-400:]))
    return 1 if errors == 3 else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", type=Path, help="Rohdaten-Ordner statt Live-Abruf")
    ap.add_argument("--only", default="", help="z. B. news oder agenda,amtlich")
    a = ap.parse_args()
    sys.exit(run(a.offline, {s for s in a.only.split(",") if s}))
