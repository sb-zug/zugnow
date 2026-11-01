"""zug.now – Rubrik «Günstig wohnen in Zug» (/wohnen/).

Zwei Teile:
  1. Wohnungs-Pipeline: zählt aus wandel.json (Feld «wohnen») zusammen, wie viele
     Wohnungen – und wie viele davon preisgünstig – in Planung, Bewilligung und Bau sind.
     Meilensteine mit "typ": "vermietung" erscheinen unter «Jetzt bewerben».
  2. Service: wie man zu einer günstigen Wohnung kommt (site/data/wohnen.json, von Hand).
Wird von build.py aufgerufen.
"""
import build as B
import hubs as H
import wandel as W

STUFEN = [("Planung & Politik", (1, 2, 3, 4)), ("Bewilligung", (5,)), ("Im Bau", (6,)), ("Bezogen", (7,))]


def _n(x):
    return f"{x:,}".replace(",", "'")


def build_wohnen(agenda_html):
    projekte = [p for p in (B.load("wandel", {}).get("projekte") or []) if p.get("wohnen")]
    info = B.load("wohnen", {})
    if not projekte:
        return {}
    frame = H._frame(agenda_html)
    stand = B.dlabel(info.get("stand") or B.TODAY.isoformat())

    # ── Zähler ──
    stufen = []
    for name, phasen in STUFEN:
        ps = [p for p in projekte if p["phase"] in phasen]
        stufen.append((name, sum(p["wohnen"].get("preisguenstig") or 0 for p in ps),
                       sum(p["wohnen"].get("total") or 0 for p in ps)))
    pg_total = sum(s[1] for s in stufen)
    alle_total = sum(s[2] for s in stufen)
    offen = [p for p in projekte if p["wohnen"].get("preisguenstig") is None]

    body = ('<div class="pagehead"><span class="eyebrow">Wohnen</span><h1>Günstig wohnen in Zug</h1>'
            '<p>Wo in der Stadt Zug bezahlbare Wohnungen entstehen, wie weit die Vorhaben sind und wie du selbst zu einer '
            'günstigen Wohnung kommst – bei der Stadt, bei Genossenschaften oder mit Unterstützung des Kantons. '
            'Ohne Inserate von Privaten: Hier geht es um Wohnungen zur Kostenmiete.</p>'
            + H._crumb(("Wandel", "wandel/"), ("Wohnen", None)) + "</div>")

    ziel = info.get("ziel") or {}
    bar = ""
    if ziel.get("zahl"):
        pct = min(100, round(pg_total / ziel["zahl"] * 100))
        bar = (f'<div class="wzbar" role="img" aria-label="{_n(pg_total)} von {_n(ziel["zahl"])}"><i style="width:{pct}%"></i></div>'
               f'<p class="wzziel">Zum Vergleich: {B.esc(ziel["text"])} <a class="src" href="{B.esc(ziel["quelle"])}">Quelle {B.EXT}</a></p>')
    body += ('<section class="block"><div class="shead"><h2>Preisgünstige Wohnungen in der Pipeline</h2>'
             f'<span>{len(projekte)} Vorhaben mit Wohnungen · Stand {stand}</span></div>'
             f'<div class="wzahl"><strong>{_n(pg_total)}</strong><span>preisgünstige oder genossenschaftliche Wohnungen sind fest geplant oder im Bau '
             f'– von insgesamt {_n(alle_total)} Wohnungen in diesen Vorhaben.'
             + (f' Dazu kommen {len(offen)} Vorhaben, deren Zahl noch offen ist.' if offen else "") + '</span></div>'
             + bar
             + '<div class="wfacts">' + "".join(f'<div><span>{B.esc(n)}</span><strong>{_n(pg)}</strong></div>' for n, pg, _ in stufen) + "</div>"
             '</section>')

    # ── Jetzt bewerben ──
    bewerben = []
    for p in projekte:
        for m, s in zip(p["meilensteine"], W._state(p["meilensteine"])):
            if m.get("typ") == "vermietung" and s in ("now", "next"):
                bewerben.append((p, m))
    body += '<section class="block"><div class="mitreden"><span class="eyebrow">Jetzt bewerben</span>'
    if bewerben:
        body += "".join(f'<a href="wandel/{p["slug"]}/"><strong>{B.esc(p["titel"])}</strong>'
                        f'<span>{B.esc(W._when(m))} · {B.esc(m["text"])}</span></a>' for p, m in bewerben)
    else:
        body += '<p>Zurzeit ist keine Erstvermietung angekündigt. Tipp: Bei Genossenschaften früh Mitglied werden – vermietet wird oft nur an Mitglieder.</p>'
    body += "</div></section>"

    # ── Vorhaben ──
    rows = []
    for p in sorted(projekte, key=lambda p: (-(p["wohnen"].get("preisguenstig") or -1), p["titel"])):
        w = p["wohnen"]
        zahl = (f'<b>{_n(w["preisguenstig"])}</b> preisgünstig' + (f' von {_n(w["total"])}' if w.get("total") else "")) if w.get("preisguenstig") is not None else "<b>Zahl offen</b>"
        rows.append(f'<a href="wandel/{p["slug"]}/"><span class="d">{zahl}</span><span class="t"><strong>{B.esc(p["titel"])}</strong>'
                    f'<span class="o">{B.esc(w.get("hinweis"))} · {B.esc(w.get("traeger") or "")}</span>'
                    f'<span class="o">Phase {p["phase"]}/7: {B.esc(W.PHASEN[p["phase"] - 1])}</span></span></a>')
    body += ('<section class="block"><div class="shead"><h2>Wo die Wohnungen entstehen</h2><span>Antippen für das Dossier</span></div>'
             f'<div class="amtlist wlist">{"".join(rows)}</div></section>')

    # ── So kommst du zu einer günstigen Wohnung ──
    wege = info.get("wege") or []
    if wege:
        cards = []
        for w in wege:
            pts = "".join(f"<li>{B.esc(x)}</li>" for x in w.get("punkte", []))
            lk = " · ".join(f'<a href="{B.esc(u)}">{B.esc(t)} {B.EXT}</a>' for t, u in w.get("links", []))
            cards.append(f'<div class="wweg"><span class="eyebrow">{B.esc(w["wer"])}</span><h3>{B.esc(w["titel"])}</h3>'
                         f'<p>{B.esc(w["text"])}</p>' + (f"<ul>{pts}</ul>" if pts else "") + f'<p class="lk">{lk}</p></div>')
        body += ('<section class="block"><div class="shead"><h2>So kommst du zu einer günstigen Wohnung</h2><span>Anlaufstellen</span></div>'
                 f'<div class="wwege">{"".join(cards)}</div></section>')

    body += (f'<section class="block"><p class="note">Stand {stand}, redaktionell aus öffentlichen Quellen. Zahlen gemäss Bauträgerschaften und Stadt; '
             'massgebend sind die amtlichen Publikationen und die Angaben der Vermieterinnen.</p>'
             '<p><a href="politik/wohnen/">Wohnpolitik: was Parlament und Parteien sagen →</a> · <a href="wandel/">Alle Vorhaben →</a></p></section>')

    page = H._page(frame, "wohnen/", "Günstig wohnen in Zug – preisgünstige Wohnungen und Genossenschaften | zug.now",
                   f"Preisgünstige Wohnungen in der Stadt Zug: {_n(pg_total)} in Planung und Bau, Kriterien der Stadt, "
                   "Genossenschaften und Mietzinszuschüsse – alles an einem Ort.", body)
    print(f"Wohnen: {len(projekte)} Vorhaben, {pg_total} preisgünstig von {alle_total}, {len(bewerben)} Vermietungen")
    return {"wohnen/index.html": page}
