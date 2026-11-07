"""zug.now – IndexNow: meldet geänderte Adressen sofort an Bing (und Yandex, Seznam …).

Läuft in GitHub Actions nach dem Veröffentlichen. Liste kommt von seo.py (_site/indexnow.json).
Schlüsseldatei: site/e73933eff35c460985c16f343aa5cd87.txt (öffentlich, so verlangt es IndexNow). Fehler brechen nie ab.
"""
import json
import urllib.request
from pathlib import Path

KEY = "e73933eff35c460985c16f343aa5cd87"
ROOT = Path(__file__).resolve().parent.parent


def main():
    try:
        urls = json.loads((ROOT / "_site" / "indexnow.json").read_text(encoding="utf-8"))
    except Exception:
        urls = []
    if not urls:
        print("IndexNow: nichts Neues")
        return
    body = json.dumps({"host": "zug.now", "key": KEY, "keyLocation": f"https://zug.now/{KEY}.txt", "urlList": urls[:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {len(urls)} Adressen gemeldet (HTTP {r.status})")
    except Exception as x:
        print("IndexNow fehlgeschlagen:", x)


if __name__ == "__main__":
    main()
