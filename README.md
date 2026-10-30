# zug.now

Live-Website für die Stadt Zug. Ein Sammler holt zweimal täglich echte Daten aus offenen Quellen, schreibt sie als JSON, und eine statische Seite zeigt sie an. Keine Datenbank, kein Server, keine Kosten.

## Quellen (Stand 29.10.2026 geprüft)

| Bereich | Quelle | Schnittstelle | Filter |
|---|---|---|---|
| News + Bilder | stadtzug.ch/de/news | HTML (Server-gerendert), Bild aus Artikelseite (cdn.zg.ch) | – |
| Agenda | veranstaltungen.zug.ch | **OneGov iCal** `/events/ical` (offizieller Export) | PLZ 6300–6303/6317, Orte, Koordinaten |
| Institutionen | Bibliothek, Burg, Kunsthaus, Musikschule | stecken in der OneGov-Agenda | Ort / Kategorie |
| Amtlich | amtsblatt.zg.ch | **eSHAB REST-API** `/api/v1/publications` | Absender «Stadt Zug – …», ohne Privatpersonen |
| Wetter | Open-Meteo | im Browser, ohne Schlüssel | – |
| Politik: Abstimmungen | wab.zug.ch | **OneGov ElectionDay** `/archive/<jahr>/json`, Stadt-Resultat aus `/vote/<id>/data-json` | Gemeinde 1711 (Zug) |
| Politik: GGR | stadtzug.ch-News + Amtsblatt | aus News/Amtlich (Titel mit «GGR»/«Grosser Gemeinderat») | – |
| Politik: fest | Sitzverteilung, Stadtrat, Parteien | `POLITIK_FIX` in collector/collect.py, nach Wahlen von Hand nachführen | – |

Fällt eine Quelle aus, bleibt der letzte Stand stehen; `site/data/meta.json` zeigt den Status.

## In Betrieb nehmen (~15 Min.)

1. Auf github.com ein neues Repository anlegen, z. B. `zugnow` (öffentlich, damit Pages gratis ist).
2. Den Inhalt dieses Ordners hochladen («Add file → Upload files», Ordner hineinziehen, inkl. `.github`).
3. **Settings → Pages → Source: GitHub Actions** wählen.
4. **Actions → «Daten aktualisieren & veröffentlichen» → Run workflow.** Nach ~1 Min. ist die Seite unter `https://<name>.github.io/zugnow/` live.
5. Ab dann aktualisiert sie sich zweimal täglich selbst (ca. 6 und 13 Uhr).

Eigene Domain (z. B. zugnow.ch): unter Settings → Pages → Custom domain eintragen, beim Domain-Anbieter einen CNAME auf `<name>.github.io` setzen.

## Lokal testen

```
python3 collector/collect.py                         # live
python3 collector/collect.py --offline tests/fixtures  # mit gespeicherten Rohdaten (wab_*.json sind nachgebaut)
cd site && python3 -m http.server 8000                # dann http://localhost:8000
```

Nur Python-Standardbibliothek, keine Installation nötig.

## Vor dem öffentlichen Betrieb klären

- Bildrechte: Bilder aus Medienmitteilungen und Agenda werden verlinkt (nicht kopiert). OK der Stadtkommunikation einholen.
- Vereinsportal: Anbindung vorbereitet, sobald die Stadt ein Feed/Export anbietet.
- Wohnen: Quellen (Stadt, Genossenschaften) noch festlegen.
