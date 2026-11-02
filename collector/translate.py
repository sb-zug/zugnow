"""zug.now – automatische Übersetzung DE → EN mit der DeepL API (für /en/).

Übersetzt Inhalte der Quellen, die auf den englischen Seiten erscheinen:
  News (Titel, Lead), Anlässe (Titel, Beschreibung gekürzt auf ~400 Zeichen),
  Ratsinfo-Geschäfte (Titel), Parteimeldungen (Titel, Lead).
Nicht übersetzt: Amtsblatt (rechtlich gilt Deutsch), Texte, die nicht deutsch sind.

Speicher: site/data/translations_en.json  {deutscher Text: englischer Text}
  - jeder Text wird nur einmal übersetzt (Cache); Texte, die in keiner Quelle mehr vorkommen,
    werden entfernt (hält die Datei klein).
  - i18n.py liest den Speicher beim Build, app.js über assets/i18n-en.json.

Sicherungen (DeepL Developer: 1 Mio. Zeichen insgesamt, erneuert sich nicht):
  - höchstens MAX_RUN Zeichen pro Lauf; der Rest folgt in den nächsten Läufen,
  - Stopp, sobald der Kontoverbrauch STOP_AT erreicht,
  - ohne DEEPL_KEY oder bei Fehlern: nichts passiert, die Seite läuft normal weiter.
Aufruf (GitHub Actions, nach collect.py): DEEPL_KEY=… python collector/translate.py
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
STORE = DATA / "translations_en.json"
MAX_RUN = 30_000      # Zeichen pro Lauf
STOP_AT = 950_000     # Kontoverbrauch, ab dem nichts mehr übersetzt wird
SNIP = 400            # Anlassbeschreibungen: so viele Zeichen werden übersetzt
DE_WORDS = re.compile(r"\b(und|der|die|das|den|dem|mit|für|ist|sind|nicht|ein|eine|einen|zu|zum|zur|im|auf|von|bei|wir|sie|uns|auch|wird|werden|des|sich|oder|über|aus|nach|neue|neuer|neues|deutscher|unsere)\b", re.I)


def german(s):
    """Grobe Erkennung: nur deutsche Texte übersetzen (englische, spanische … Anlässe bleiben)."""
    words = len(DE_WORDS.findall(s))
    if len(s) < 120:
        return words >= 1 or bool(re.search(r"[äöüß]", s))
    return words >= 3 or (words >= 1 and len(re.findall(r"[äöüß]", s)) >= 3)


def snippet(s):
    """Auf ~SNIP Zeichen kürzen, an Satz- oder Wortgrenze."""
    s = s.strip()
    if len(s) <= SNIP:
        return s, False
    cut = s[:SNIP]
    m = re.search(r"^(.*[.!?])\s", cut, re.S)
    cut = m.group(1) if m and len(m.group(1)) > SNIP * 0.6 else cut.rsplit(" ", 1)[0]
    return cut.strip(), True


def load(name, default):
    try:
        return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    except Exception:
        return default


def wanted():
    """Alle Texte, die übersetzt werden sollen: {Schlüssel (wie angezeigt): Text für DeepL}."""
    out = {}

    def add(s, long=False):
        s = (s or "").strip()
        if not s or not german(s):
            return
        if long:
            cut, more = snippet(s)
            out[s] = (cut, more)
        else:
            out[s] = (s, False)

    for n in load("news", []):
        add(n.get("title")); add(n.get("lead"))
    for e in load("agenda", []):
        add(e.get("title")); add(e.get("teaser")); add(e.get("text"), long=True)
    p = load("politik", {})
    for k in ("vorlagen", "vorstoesse"):
        for v in (p.get("geschaefte") or {}).get(k, []):
            add(v.get("title"))
    for x in p.get("posts") or []:
        add(x.get("title")); add(x.get("lead"))
    return out


def api(key, path, body=None):
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    req = urllib.request.Request(f"https://{host}{path}", data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"DeepL-Auth-Key {key}", "Content-Type": "application/json"},
                                 method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    key = os.environ.get("DEEPL_KEY", "").strip()
    store = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    want = wanted()
    store = {k: v for k, v in store.items() if k in want}  # nicht mehr verwendete Texte entfernen
    todo = [(k, src, more) for k, (src, more) in want.items() if k not in store]
    print(f"Übersetzung: {len(want)} Texte, {len(store)} schon übersetzt, {len(todo)} offen")
    if not key:
        print("  kein DEEPL_KEY – nichts übersetzt")
    elif todo:
        try:
            use = api(key, "/v2/usage")
            used, limit = use.get("character_count", 0), use.get("character_limit", 0)
            print(f"  DeepL-Verbrauch bisher: {used:,} von {limit:,} Zeichen".replace(",", "'"))
            budget = min(MAX_RUN, STOP_AT - used, (limit - used) if limit else MAX_RUN)
            if budget <= 0:
                print("  Obergrenze erreicht – nichts übersetzt")
                todo = []
            batch, size, sent = [], 0, 0
            todo.sort(key=lambda x: len(x[1]))  # kurze zuerst: Titel und Leads haben Vorrang
            for item in todo:
                if sent + size + len(item[1]) > budget:
                    break
                batch.append(item); size += len(item[1])
                if len(batch) == 40 or size > 8000:
                    sent += size; _send(key, batch, store); batch, size = [], 0
            if batch:
                sent += size; _send(key, batch, store)
            print(f"  übersetzt: {sent:,} Zeichen in diesem Lauf".replace(",", "'"))
        except Exception as ex:  # nie den Lauf abbrechen
            print(f"  DeepL-Fehler: {ex}", file=sys.stderr)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def _send(key, batch, store):
    res = api(key, "/v2/translate", {"text": [src for _, src, _ in batch], "source_lang": "DE", "target_lang": "EN-GB",
                                      "preserve_formatting": True})
    for (k, _, more), t in zip(batch, res.get("translations", [])):
        store[k] = t["text"].strip() + (" …" if more else "")


if __name__ == "__main__":
    main()
