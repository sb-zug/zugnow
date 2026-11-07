"""zug.now – Wochenbrief «Diese Woche in Zug» (Entwurf seit 7.11.2026).

Baut aus den vorhandenen Daten (kein KI-Text) eine Ausgabe mit bis zu sechs Themenblöcken.
Abonnentinnen wählen Themen; der Versanddienst (vorgesehen: Brevo) blendet Blöcke über
Kontakt-Attribute aus (NL_MITREDEN, NL_BAUGESUCHE …, Typ Boolean).

Ausgabe:
  /newsletter/          Anmeldeseite mit Themenwahl (?t=baugesuche,wohnen kreuzt vor)
  /newsletter/muster/   Webversion der aktuellen Ausgabe (noindex)
  /newsletter/mail.html E-Mail-HTML mit Brevo-Bedingungen {% if contact.NL_… %}
Solange FORM_ACTION leer ist, ist die Anmeldung deaktiviert und die Seiten sind noindex.
Wird von build.py aufgerufen.
"""
import re
from datetime import timedelta

import build as B
import hubs as H
import startb as SB
import wandel as W

SITE = "https://zug.now/"
FORM_ACTION = ""  # Brevo-Formular-URL (sibforms.com/serve/…), sobald das Konto steht

TOPICS = [
    ("mitreden", "Jetzt mitreden", "Auflagen, Mitwirkungen und Infoanlässe – mit Frist"),
    ("baugesuche", "Baugesuche", "Neu im Amtsblatt, mit Adresse und Auflagefrist"),
    ("politik", "Parlament & Abstimmungen", "Sitzungen, neue Vorstösse und Vorlagen, Abstimmungssonntage"),
    ("wochenende", "Wochenende", "Fünf ausgewählte Anlässe für Samstag und Sonntag"),
    ("wandel", "Wie sich Zug verändert", "Was bei den grossen Vorhaben passiert ist oder bald passiert"),
    ("wohnen", "Günstig wohnen", "Erstvermietungen preisgünstiger und genossenschaftlicher Wohnungen"),
]
WEEK = 7    # «neu» = letzte 7 Tage
AHEAD = 21  # Termine in den nächsten 3 Wochen


def _abs(u):
    u = u or ""
    return u if u.startswith("http") else SITE + u.lstrip("/")


def _dm(d):
    return f"{B.WDL[d.weekday()]} {d.day}.{d.month}."


def issue(events, pol_news):
    """Inhalt der Ausgabe: [(key, titel, mehr-link, [(kicker, titel, text, url)])]. Leere Blöcke fallen weg."""
    politik = B.load("politik", {})
    projekte = B.load("wandel", {}).get("projekte") or []
    amtlich = B.load("amtlich", [])
    end = B.TODAY + timedelta(days=AHEAD)
    out = []

    # 1 Jetzt mitreden (ohne Parlament/Abstimmung/Vermietung – die haben eigene Themen)
    rows = [r for r in SB.mitreden_rows(projekte, pol_news, politik) if r[3] not in ("Parlament", "Abstimmung", "Jetzt bewerben")]
    items = [(f'{r[3]} · {"läuft" if r[2] else _dm(r[1])}' if r[1] else r[3], r[4], r[5], r[6]) for r in rows if r[2] or r[0] <= end]
    out.append(("mitreden", "Jetzt mitreden", "wandel/", items[:5]))

    # 2 Baugesuche der letzten Woche, solange die Auflage läuft
    bg = [a for a in amtlich if a.get("label") == "Baugesuch" and H._current(a) and (B.TODAY - SB._iso(a["date"])).days <= WEEK]
    out.append(("baugesuche", "Neue Baugesuche", "baugesuche/",
                [(f'Einsehbar bis {B.dlabel(a["expires"])}' if a.get("expires") else "Publiziert " + B.dlabel(a["date"]),
                  re.sub(r",\s*Zug$", "", a["title"]), "Amtsblatt · Pläne einsehen, Einsprache möglich", a["url"]) for a in bg]))

    # 3 Parlament & Abstimmungen
    items = []
    ns = SB.next_session(pol_news)
    if ns and ns[0] <= end:
        items.append((f"Parlament · {_dm(ns[0])}", "Sitzung des Grossen Gemeinderats", "Öffentlich – oder im Livestream", ns[1]["url"]))
    nv = SB._iso(politik.get("nextVoteDate"))
    if nv and B.TODAY <= nv:
        n = (nv - B.TODAY).days
        items.append((f"Abstimmung · {_dm(nv)}", "Abstimmungssonntag", f"In {n} {'Tag' if n == 1 else 'Tagen'} · Vorlagen und Unterlagen", "politik/#pAbst"))
    G = politik.get("geschaefte") or {}
    neu = [v for v in G.get("vorstoesse") or [] if (B.TODAY - SB._iso(v.get("touched") or v["date"])).days <= WEEK]
    for v in neu[:4]:
        items.append((f'{v["art"]} · {" / ".join(v.get("parteien") or []) or "GGR"}', v["title"], v.get("status") or "",
                      (v.get("answer") or {}).get("url") or v["url"]))
    for v in [v for v in G.get("vorlagen") or [] if (B.TODAY - SB._iso(v["date"])).days <= WEEK][:2]:
        items.append((f'Vorlage Stadtrat · Nr. {v["nr"]}', v["title"], f'Bei {v.get("stage") or "Kommission"}', v["url"]))
    out.append(("politik", "Parlament & Abstimmungen", "politik/", items))

    # 4 Wochenende: verschiedene Titel, mit Bild bevorzugt, chronologisch
    wa, wb = B.weekend()
    wk = [e for e in events if wa <= B.dt(e["start"]).date() <= wb and not e.get("cancelled")]
    seen, pick = set(), []
    for e in [e for e in wk if e.get("image")] + [e for e in wk if not e.get("image")]:
        if e["title"] not in seen and len(pick) < 5:
            seen.add(e["title"]); pick.append(e)
    pick.sort(key=lambda e: e["start"])
    out.append(("wochenende", f"Wochenende {B.dt(wk[0]['start']).day}.–{wb.day}.{wb.month}." if wk else "Wochenende", "wochenende/",
                [(f'{_dm(B.dt(e["start"]).date())} · {"ganztags" if e.get("allday") else B.hm(e["start"]).replace(":", ".")}',
                  e["title"], e.get("place") or "", e.get("page") or e.get("url")) for e in pick]))

    # 5 Wie sich Zug verändert: Meilensteine der letzten Woche und der nächsten 3 Wochen (ohne Mitreden-Termine)
    items = []
    for p in projekte:
        for m in p["meilensteine"]:
            a, _ = W._d(m.get("datum"))
            if not a or m.get("typ") == "vermietung" or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(m.get("datum"))):
                continue
            if re.search(r"Auflage|Mitwirkung|Infoanlass|Informationsanlass", m["text"]):
                continue
            if -WEEK <= (a - B.TODAY).days <= AHEAD:
                items.append((a, ("Erledigt · " if a < B.TODAY else "Als Nächstes · ") + _dm(a), p["titel"], m["text"], f'wandel/{p["slug"]}/'))
    items.sort(key=lambda x: x[0])
    out.append(("wandel", "Wie sich Zug verändert", "wandel/", [x[1:] for x in items[:5]]))

    # 6 Günstig wohnen: laufende und angekündigte Erstvermietungen
    items = []
    for p in projekte:
        for m, s in zip(p["meilensteine"], W._state(p["meilensteine"])):
            if m.get("typ") == "vermietung" and s in ("now", "next"):
                n = (p.get("wohnen") or {}).get("total")
                items.append(("Jetzt bewerben" if s == "now" else "Angekündigt · " + W._when(m), p["titel"],
                              (f"{n} Wohnungen · " if n else "") + m["text"], f'wandel/{p["slug"]}/'))
    out.append(("wohnen", "Günstig wohnen", "wohnen/", items))
    return [s for s in out if s[3]]


# ─────────────────────────── Webseiten ───────────────────────────

CSS = """<style>
.nlform{display:grid;gap:28px;max-width:760px}
.nltop{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));border-top:1px solid var(--fg);border-left:1px solid var(--fg)}
.nltop label{display:flex;gap:14px;align-items:flex-start;padding:18px 20px;border-right:1px solid var(--fg);border-bottom:1px solid var(--fg);cursor:pointer}
.nltop input{width:20px;height:20px;margin-top:3px;accent-color:var(--brand);flex:none}
.nltop strong{display:block;font-size:18px}.nltop span span{display:block;color:var(--soft);font-size:15px;margin-top:4px}
.nlrow{display:flex;flex-wrap:wrap;gap:12px;align-items:stretch}
.nlrow input[type=email]{flex:1 1 280px;font:inherit;font-size:18px;padding:14px 16px;border:1px solid var(--fg);background:var(--bg);color:var(--fg);border-radius:0}
.nlrow button{font:inherit;font-weight:700;font-size:18px;padding:14px 26px;border:0;background:var(--brand);color:#fff;cursor:pointer;border-radius:0}
.nlrow button[disabled]{opacity:.45;cursor:not-allowed}
.nllang{display:flex;gap:24px;font-size:16px}.nllang label{display:flex;gap:8px;align-items:center}
.nlsoon{padding:14px 18px;border:1px solid var(--fg);font-size:16px}
.nlis{max-width:760px}.nlis h2{font-size:clamp(24px,3vw,30px);font-weight:800;margin:0}
.nlsec{border-top:1px solid var(--fg);padding-top:18px;margin-top:40px}
.nlsec .nlh{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:6px}
.nltag{font-size:13px;font-weight:600;color:var(--soft);text-transform:uppercase;letter-spacing:.06em}
.nlit{display:block;padding:14px 0;border-bottom:1px solid color-mix(in srgb,var(--fg) 18%,transparent);color:inherit;text-decoration:none}
.nlit .k{font-size:14px;color:var(--brand);font-weight:600}.nlit strong{display:block;font-size:19px;margin:3px 0}
.nlit .x{color:var(--soft);font-size:15px}.nlit:hover strong{text-decoration:underline}
</style>"""

PRESELECT_JS = """<script>
(function(){var t=(new URLSearchParams(location.search).get('t')||'').split(',').filter(Boolean);if(!t.length)return;
document.querySelectorAll('.nltop input').forEach(function(i){i.checked=t.indexOf(i.dataset.t)>=0})})();
</script>"""


def _web_issue(sections, stand):
    h = (f'<div class="nlis"><p class="nltag">Musterausgabe · Stand {B.dlabel(stand)}</p>'
         '<p>Jeden Freitagmorgen. Du bekommst nur die Blöcke deiner Themen; Blöcke ohne Neues fallen weg.</p>')
    for key, title, more, items in sections:
        lbl = next(t[1] for t in TOPICS if t[0] == key)
        h += (f'<section class="nlsec"><div class="nlh"><h2>{B.esc(title)}</h2>' + (f'<span class="nltag">Thema: {B.esc(lbl)}</span>' if lbl not in title else "") + '</div>'
              + "".join(f'<a class="nlit" href="{B.esc(u)}"><span class="k">{B.esc(k)}</span><strong>{B.esc(t)}</strong>'
                        + (f'<span class="x">{B.esc(x)}</span>' if x else "") + "</a>" for k, t, x, u in items)
              + f'<p><a href="{B.esc(more)}">Mehr auf zug.now →</a></p></section>')
    return h + "</div>"


def _signup(n_sections):
    boxes = "".join(f'<label><input type="checkbox" name="NL_{k.upper()}" value="true" data-t="{k}" checked>'
                    f'<span><strong>{B.esc(t)}</strong><span>{B.esc(d)}</span></span></label>' for k, t, d in TOPICS)
    live = bool(FORM_ACTION)
    return (f'<form class="nlform" method="post" action="{B.esc(FORM_ACTION or "#")}"' + ("" if live else ' onsubmit="return false"') + ">"
            f'<fieldset style="border:0;padding:0;margin:0"><legend class="nltag" style="margin-bottom:12px">Deine Themen</legend><div class="nltop">{boxes}</div></fieldset>'
            '<div class="nllang"><span class="nltag">Sprache</span><label><input type="radio" name="LANG" value="DE" checked> Deutsch</label>'
            '<label><input type="radio" name="LANG" value="EN"> English</label></div>'
            '<div class="nlrow"><input type="email" name="EMAIL" required placeholder="deine@e-mail.ch" autocomplete="email" aria-label="E-Mail-Adresse">'
            f'<button type="submit"{"" if live else " disabled"}>Abonnieren</button></div>'
            + ("" if live else '<p class="nlsoon">Die Anmeldung öffnet in Kürze. Schau dir bis dahin die <a href="newsletter/muster/">Musterausgabe</a> an.</p>')
            + '<p class="note">Gratis, jederzeit abbestellbar. Du bestätigst die Anmeldung per Mail (Double-Opt-in). Themen kannst du in jedem Mail über «Themen anpassen» ändern. '
              'Die Adresse wird nur für den Versand genutzt und nicht weitergegeben.</p></form>')


# ─────────────────────────── E-Mail ───────────────────────────

F = "font-family:Arial,Helvetica,sans-serif;"


def mail_html(sections, stand):
    """E-Mail mit Inline-Styles; jeder Block in {% if contact.NL_<THEMA> %} (Brevo Template Language)."""
    blocks = ""
    for key, title, more, items in sections:
        rows = "".join(
            f'<tr><td style="padding:12px 0;border-bottom:1px solid #e3e3e3;{F}">'
            f'<div style="font-size:13px;color:#1F55C4;font-weight:bold">{B.esc(k)}</div>'
            f'<a href="{B.esc(_abs(u))}" style="display:block;font-size:17px;font-weight:bold;color:#111;text-decoration:none;margin:3px 0">{B.esc(t)}</a>'
            + (f'<div style="font-size:14px;color:#666">{B.esc(x)}</div>' if x else "") + "</td></tr>" for k, t, x, u in items)
        blocks += (f"{{% if contact.NL_{key.upper()} %}}\n"
                   f'<tr><td style="padding:28px 0 4px;border-top:2px solid #111;{F}"><div style="font-size:22px;font-weight:bold;color:#111">{B.esc(title)}</div></td></tr>'
                   f"{rows}"
                   f'<tr><td style="padding:10px 0 0;{F}"><a href="{_abs(more)}" style="font-size:14px;color:#1F55C4;font-weight:bold">Mehr auf zug.now →</a></td></tr>'
                   "\n{% endif %}\n")
    return f"""<!doctype html>
<html lang="de-CH"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Diese Woche in Zug</title></head>
<body style="margin:0;background:#f4f4f4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff">
<tr><td style="padding:28px 28px 8px;{F}">
<div style="font-size:15px;font-weight:bold;color:#1F55C4">zug.now</div>
<div style="font-size:30px;font-weight:bold;color:#111;margin-top:6px">Diese Woche in Zug</div>
<div style="font-size:14px;color:#666;margin-top:6px">{B.dlabel(stand)} · Fristen, Baugesuche, Parlament und Wochenende – nur deine Themen</div>
</td></tr>
<tr><td style="padding:0 28px 28px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{blocks}</table></td></tr>
<tr><td style="padding:20px 28px;background:#111;color:#bbb;font-size:12px;line-height:1.6;{F}">
Automatisch zusammengestellt aus öffentlichen Quellen (Stadt Zug, Amtsblatt, Ratsinfo, Veranstaltungskalender). Massgebend sind die amtlichen Publikationen.<br>
<a href="{{{{ update_profile }}}}" style="color:#fff">Themen anpassen</a> · <a href="{{{{ unsubscribe }}}}" style="color:#fff">Abbestellen</a> · <a href="{SITE}" style="color:#fff">zug.now</a>
</td></tr></table></td></tr></table></body></html>
"""


def build_newsletter(agenda_html, events, pol_news):
    frame = H._frame(agenda_html)
    sections = issue(events, pol_news)
    stand = B.TODAY
    live = bool(FORM_ACTION)
    head = ('<div class="pagehead"><span class="eyebrow">Newsletter</span><h1>Diese Woche in Zug</h1>'
            '<p>Jeden Freitagmorgen das Wichtigste aus der Stadt Zug: laufende Fristen, neue Baugesuche, Parlament und Abstimmungen, '
            'das Wochenende und was sich bei den grossen Vorhaben tut. Du wählst die Themen – was dich nicht interessiert, bekommst du nicht.</p>'
            + H._crumb(("Newsletter", None)) + "</div>")
    signup = H._page(frame, "newsletter/", "Newsletter «Diese Woche in Zug» – Themen wählen | zug.now",
                     "Jeden Freitag das Wichtigste aus der Stadt Zug: Fristen, Baugesuche, Parlament, Wochenende, Stadtentwicklung und günstige Wohnungen – nur deine Themen.",
                     head + f'<section class="block">{_signup(len(sections))}</section>', index=live)
    muster = H._page(frame, "newsletter/muster/", "Musterausgabe «Diese Woche in Zug» | zug.now",
                     "So sieht der Wochenbrief von zug.now aus.",
                     '<div class="pagehead"><span class="eyebrow">Newsletter</span><h1>Diese Woche in Zug</h1>'
                     + H._crumb(("Newsletter", "newsletter/"), ("Musterausgabe", None)) + "</div>"
                     + f'<section class="block">{_web_issue(sections, stand)}</section>'
                     '<section class="block"><p><a href="newsletter/">Themen wählen und abonnieren →</a></p></section>', index=False)
    signup = signup.replace("</head>", CSS + "\n</head>", 1).replace("</body>", PRESELECT_JS + "\n</body>", 1)
    muster = muster.replace("</head>", CSS + "\n</head>", 1)
    print("Newsletter:", ", ".join(f"{k} {len(i)}" for k, _, _, i in sections) or "leer")
    return {"newsletter/index.html": signup, "newsletter/muster/index.html": muster, "newsletter/mail.html": mail_html(sections, stand)}
