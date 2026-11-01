"""zug.now – Geschäfte des Grossen Gemeinderats aus dem Ratsinformationssystem.

Quelle: öffentliche JSON-Schnittstelle von ratsinfo.stadtzug.ch (geprüft 1.11.2026)
  /api/businesses?committee=1&page_size=200&ordering=-begin_date
  Felder: id, number, title, begin_date, end_date, type_id
  Detailseite für Besucher: /gremium/1/geschaefte/<id>

Aus den Rohdaten entstehen zwei Listen:
  vorlagen   – Berichte und Anträge des Stadtrats, zusammengefasst über die Geschäftsnummer
               (3033 SR → 3033.1 GPK = Stadtrat → Kommission)
  vorstoesse – Motionen, Postulate, Interpellationen, Kleine Anfragen mit Partei(en) und Stand
Nur Python-Standardbibliothek. Wird von collect.py aufgerufen.
"""
import re

BASE = "https://ratsinfo.stadtzug.ch"
API = BASE + "/api/businesses?committee=1&page={page}&page_size=200&ordering=-begin_date"
URL = BASE + "/gremium/1/geschaefte/{id}"
PAGES = 2            # 2 × 200 = rund die letzten anderthalb Jahre

# Typen im Ratsinfo (api/business_types)
T_VORSTOSS, T_ANTRAG2, T_PROTOKOLL, T_ANTWORT, T_BERICHT_SR = 6, 7, 8, 9, 10
T_KOMMISSION = {11: "BPK", 12: "GPK", 13: "SPK", 14: "RPK", 15: "Büro"}
T_ZWISCHEN = 16

ARTEN = ["Kleine Anfrage", "Interpellation", "Postulat", "Motion"]
# Partei-Erkennung im Titel → Kürzel wie auf zug.now (Reihenfolge = Sitzordnung links → rechts)
PARTEIEN = [("ALG-CSP", r"ALG-CSP|\bALG\b|\bCSP\b"), ("SP", r"\bSP\b"), ("GLP", r"\bGLP\b|\bglp\b"),
            ("Die Mitte", r"Die Mitte|\bMitte\b"), ("FDP", r"\bFDP\b"), ("SVP", r"\bSVP\b")]
STATUS = [(r"^Nicht Überw", "Nicht überwiesen", "no"), (r"^zur Überw", "Zur Überweisung", "open"),
          (r"^Überw", "Überwiesen an den Stadtrat", "ok"), (r"^Bearb", "In Bearbeitung beim Stadtrat", "open")]


def _art(title):
    t = re.sub(r"^Postulat \(Motion\)", "Postulat", title)
    for a in ARTEN:
        if t.startswith(a):
            return a
    return None


def _parteien(title):
    head = title.split("betreffend")[0]
    if re.search(r"Fraktionen ALG-CSP, FDP, GLP, Die Mitte, SP und SVP|alle Fraktionen", head):
        return ["Alle Fraktionen"]
    return [p for p, rx in PARTEIEN if re.search(rx, head)]


def _thema(title):
    m = re.search(r"\bbetreffend\s+(.*)$", title)
    t = (m.group(1) if m else title).strip()
    t = t.strip(" .«»\"„“").replace("«", "").replace("»", "") or title
    return t[:1].upper() + t[1:]


def _base(nr):
    m = re.match(r"(\d{4})(?:\.(\d+))?", nr or "")
    return (m.group(1), int(m.group(2) or 0)) if m else (None, None)


def _vorlage_titel(title):
    """«Hochbau: Neubau Hallenbad …; Wettbewerbskredit» → Bereich, Titel"""
    m = re.match(r"([^:]{3,45}):\s*(.+)$", title)
    return (m.group(1).strip(), m.group(2).strip()) if m else ("", title)


def build(rows, today=None):
    """rows: Liste der Rohobjekte aus /api/businesses → dict mit vorlagen, vorstoesse"""
    rows = [r for r in rows if r.get("title")]
    by_base = {}
    for r in rows:
        b, step = _base(r.get("number"))
        if b:
            by_base.setdefault(b, []).append((step, r))

    # ── Vorlagen des Stadtrats (inkl. Antworten auf Vorstösse, die als Bericht und Antrag kommen)
    vorlagen = []
    for b, items in by_base.items():
        items.sort(key=lambda x: (x[1]["begin_date"], x[0]))
        sr = [r for s, r in items if r["type_id"] in (T_BERICHT_SR, T_ZWISCHEN)]
        if not sr:
            continue
        first = sr[0]
        if _art(first["title"]):          # Bericht zu einem Vorstoss → erscheint dort als Antwort
            continue
        kom = [(T_KOMMISSION[r["type_id"]], r) for s, r in items if r["type_id"] in T_KOMMISSION]
        l2 = [r for s, r in items if r["type_id"] == T_ANTRAG2 or "2. Lesung" in r["title"]]
        bereich, titel = _vorlage_titel(first["title"])
        last = items[-1][1]
        steps = [{"label": "Stadtrat", "date": first["begin_date"], "url": URL.format(id=first["id"])}]
        for k, r in kom:
            if not any(s["label"] == k for s in steps):
                steps.append({"label": k, "date": r["begin_date"], "url": URL.format(id=r["id"])})
        vorlagen.append({
            "nr": b, "bereich": bereich, "title": titel, "date": last["begin_date"], "start": first["begin_date"],
            "stage": "Kommission" if kom else "Stadtrat", "kommission": [k for k, _ in kom],
            "zweiteLesung": bool(l2), "kenntnis": "Kenntnisnahme" in titel or first["type_id"] == T_ZWISCHEN,
            "steps": steps, "url": URL.format(id=last["id"]),
        })
    vorlagen.sort(key=lambda v: v["date"], reverse=True)

    # ── Vorstösse: eingereicht (Typ 6), Antwort/Bericht des Stadtrats über die gleiche Nummer
    answers = {}
    for r in rows:
        if r["type_id"] in (T_ANTWORT, T_BERICHT_SR) and _art(r["title"]):
            b, _ = _base(r["number"])
            if b:
                answers.setdefault(b, r)
    seen, vorstoesse = set(), []
    for r in rows:
        art = _art(r["title"])
        if not art:
            continue
        b, _ = _base(r.get("number"))
        key = re.sub(r"\W+", "", r["title"].lower())[:120]
        if r["type_id"] != T_VORSTOSS and (key in seen):
            continue
        if r["type_id"] != T_VORSTOSS:
            # Antwort ohne eingereichten Vorstoss in den Daten (älter): nur aufnehmen, wenn der Vorstoss fehlt
            if any(x["type_id"] == T_VORSTOSS and _base(x.get("number"))[0] == b for x in rows):
                continue
        seen.add(key)
        nr = (r.get("number") or "").strip()
        ans = answers.get(b) if b else None
        if ans:
            st, tone = ("Antwort des Stadtrats liegt vor" if ans["type_id"] == T_ANTWORT else "Bericht und Antrag des Stadtrats liegt vor"), "done"
        else:
            st, tone = next(((lab, t) for rx, lab, t in STATUS if re.match(rx, nr)), ("Eingereicht", "new"))
        m = re.search(r"vom (\d{1,2})\.\s*(\w+)\s+(\d{4})", r["title"])
        vorstoesse.append({
            "art": art, "parteien": _parteien(r["title"]), "title": _thema(r["title"]), "full": r["title"],
            "date": r["begin_date"], "status": st, "tone": tone,
            "answer": ({"date": ans["begin_date"], "url": URL.format(id=ans["id"])} if ans else None),
            "url": URL.format(id=r["id"]), "eingereicht": " ".join(m.groups()) if m else "",
            "touched": max(r["begin_date"], ans["begin_date"] if ans else ""),
        })
    vorstoesse.sort(key=lambda v: v["touched"], reverse=True)
    return {"vorlagen": vorlagen, "vorstoesse": vorstoesse}
