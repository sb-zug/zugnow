"""zug.now – Politische Themendossiers (/politik/<thema>/).

Pro Thema (Wohnen, Finanzen, Verkehr …) an einem Ort:
  - laufende Geschäfte mit Weg durch Stadtrat → Kommission → Parlament → Volk
  - zugehörige Vorhaben aus /wandel/ (Phase, nächster Schritt)
  - «Das sagen die Parteien»: Parteimeldungen zum Thema, alle gleich behandelt, filterbar
  - Abstimmungen und Meldungen von Stadt und Amtsblatt zum Thema
Themen und Geschäfte pflegt die Redaktion in site/data/dossiers.json; die Zuordnung
läuft bei jedem Build über Stichworte. Wird von build.py aufgerufen.
"""
import json
import re

import build as B
import hubs as H
import wandel as W

SCHRITTE = ["Stadtrat", "Kommission", "Parlament", "Volk", "Erledigt"]
DOM = {"federation": "Bund", "canton": "Kanton", "municipality": "Stadt"}

FILTER_JS = """<script>
(function(){var c=document.getElementById('dChips'),l=document.getElementById('dPosts');if(!c||!l)return;
c.onclick=function(e){var b=e.target.closest('.chip');if(!b)return;var v=b.dataset.v;
c.querySelectorAll('.chip').forEach(function(x){x.setAttribute('aria-pressed',x===b)});
l.querySelectorAll('a').forEach(function(a){a.hidden=v!=='alle'&&a.dataset.p!==v})};})();
</script>"""


def _hit(kws):
    return lambda t: any(k in (t or "").lower() for k in kws)


def _collect(t, news, amtlich, pol):
    hit = _hit([k.lower() for k in t.get("keywords", [])])
    meld = [(n["date"], n.get("type") or "News", n["title"], n["url"]) for n in news if not n["title"].startswith("Baugesuch") and hit(n["title"] + " " + (n.get("lead") or ""))]
    meld += [(a["date"], "Amtsblatt", a["title"], a["url"]) for a in amtlich if hit(a["title"])]
    posts = [p for p in pol.get("posts") or [] if hit(p["title"] + " " + (p.get("lead") or ""))]
    votes = [v for v in (pol.get("upcoming") or []) + (pol.get("votes") or []) if hit(v.get("title"))]
    G = pol.get("geschaefte") or {}
    ges = [("vorlage", v) for v in G.get("vorlagen") or [] if hit(v["title"] + " " + v.get("bereich", ""))]
    ges += [("vorstoss", v) for v in G.get("vorstoesse") or [] if hit(v["title"])]
    ges.sort(key=lambda x: x[1].get("touched") or x[1]["date"], reverse=True)
    return sorted(meld, reverse=True)[:10], posts, votes, ges[:12]


def _ges_row(kind, v):
    if kind == "vorlage":
        way = "".join(f'<li class="on">{B.esc(s["label"])}</li>' for s in v["steps"]) + "<li>Parlament</li>"
        return (f'<a class="gr" href="{B.esc(v["url"])}"><span class="d">{B.dlabel(v["date"])}</span><span class="c">'
                f'<span class="gk"><b>Vorlage des Stadtrats</b><span class="muted">Nr. {B.esc(v["nr"])}</span></span>'
                f'<span class="t">{B.esc(v["title"])}</span><ol class="gway">{way}</ol></span></a>')
    badges = "".join(f'<span class="pbadge">{B.esc(x)}</span>' for x in v["parteien"])
    url = v["answer"]["url"] if v.get("answer") else v["url"]
    return (f'<a class="gr" href="{B.esc(url)}"><span class="d">{B.dlabel(v.get("touched") or v["date"])}</span><span class="c">'
            f'<span class="gk"><b>{B.esc(v["art"])}</b>{badges}</span><span class="t">{B.esc(v["title"])}</span>'
            f'<span class="gs {B.esc(v["tone"])}">{B.esc(v["status"])}</span></span></a>')


def _steps(n):
    return ('<ol class="gsteps" aria-label="Stand: ' + B.esc(SCHRITTE[n - 1]) + '">'
            + "".join(f'<li class="{"cur" if i == n - 1 else "on" if i < n else ""}" title="{B.esc(s)}"></li>' for i, s in enumerate(SCHRITTE))
            + "</ol>")


def _next(ms):
    for m, s in zip(ms, W._state(ms)):
        if s in ("now", "next"):
            return m, s
    return None, None


def _nx(m, s):
    if not m:
        return ""
    return f'<p class="nx"><b>{"Läuft jetzt" if s == "now" else "Als Nächstes"}</b> {B.esc(W._when(m))} · {B.esc(m["text"])}</p>'


def _geschaeft(g):
    m, s = _next(g["meilensteine"])
    tl = "".join(
        f'<li class="{st}"><span class="d">{B.esc(W._when(x))}</span><span class="c">{B.esc(x["text"])}'
        + (f' <a class="src" href="{B.esc(x["quelle"])}">Quelle {B.EXT}</a>' if x.get("quelle") else "") + "</span></li>"
        for x, st in zip(g["meilensteine"], W._state(g["meilensteine"])))
    facts = "".join(f'<div><span>{B.esc(k)}</span><strong>{B.esc(v)}</strong></div>' for k, v in g.get("fakten", []))
    links = " · ".join(f'<a href="{B.esc(u)}">{B.esc(t)} {B.EXT}</a>' for t, u in g.get("links", []))
    return (f'<div class="gitem"><span class="gl">Geschäft · Stand: {B.esc(SCHRITTE[g["schritt"] - 1])}</span>'
            f'<h3>{B.esc(g["titel"])}</h3>{_steps(g["schritt"])}'
            f'<span class="gl">{" → ".join(SCHRITTE[:4])}</span><p>{B.esc(g["kurz"])}</p>{_nx(m, s)}'
            + (f'<div class="wfacts">{facts}</div>' if facts else "")
            + f'<ol class="wtl dossier">{tl}</ol>' + (f'<p class="gl">{links}</p>' if links else "") + "</div>")


def build_dossiers(agenda_html, politik_html, news, amtlich):
    data = B.load("dossiers", {})
    themen = data.get("themen") or []
    if not themen:
        return {}
    pol = B.load("politik", {})
    vh = {p["slug"]: p for p in (B.load("wandel", {}).get("projekte") or [])}
    frame = H._frame(agenda_html)
    stand = B.dlabel(data.get("stand") or B.TODAY.isoformat())
    pages, cards = {}, []

    for t in themen:
        meld, posts, votes, ges = _collect(t, news, amtlich, pol)
        gs = t.get("geschaefte") or []
        vs = [vh[s] for s in t.get("vorhaben", []) if s in vh]
        # nächster Termin über Geschäfte und Vorhaben
        nxt = sorted(((W._d(m.get("datum"))[0], m, s, x) for x in gs + vs for m, s in [_next(x["meilensteine"])]
                      if m and W._d(m.get("datum"))[0]), key=lambda z: z[0])
        n_items = len(gs) + len(vs)
        cnt = " · ".join(x for x in [f"{n_items + len(ges)} Geschäfte & Vorhaben" if n_items + len(ges) else "", f"{len(posts)} Parteimeldungen" if posts else "",
                                      f"{len(meld)} Meldungen" if meld else ""] if x) or "Neue Meldungen erscheinen automatisch"
        nx = (f'<span class="nx"><b>{"Jetzt" if nxt[0][2] == "now" else "Als Nächstes"}</b> {B.esc(W._when(nxt[0][1]))} · '
              f'{B.esc(nxt[0][3]["titel"])}</span>') if nxt else ""
        cards.append(f'<a class="dcard" href="politik/{t["slug"]}/"><span class="eyebrow">Dossier</span><strong>{B.esc(t["titel"])}</strong>'
                     f'<span class="sub">{B.esc(t["kurz"].split(". ")[0].rstrip(".") + ".")}</span>{nx}<span class="cnt">{cnt}</span></a>')

        body = (f'<div class="pagehead"><span class="eyebrow">Politisches Dossier</span><h1>{B.esc(t["titel"])}</h1><p>{B.esc(t["kurz"])}</p>'
                + H._crumb(("Politik", "politik/"), (t["titel"], None)) + "</div>")
        if gs or vs:
            body += '<section class="block"><div class="shead"><h2>Was gerade läuft</h2><span>Geschäfte und Vorhaben</span></div>'
            if gs:
                body += '<div class="glist">' + "".join(_geschaeft(g) for g in gs) + "</div>"
            if vs:
                body += ('<div class="wgrid" style="margin-top:16px">' + "".join(W._card(p).replace('href="wandel/', 'href="/wandel/') for p in vs) + "</div>")
            body += "</section>"
        if ges:
            body += ('<section class="block"><div class="shead"><h2>Aus dem Parlament</h2><span>Vorlagen und Vorstösse im Ratsinfo</span></div>'
                     '<div class="glist2">' + "".join(_ges_row(k, v) for k, v in ges) + '</div>'
                     '<p class="note">Automatisch aus dem Ratsinformationssystem zugeordnet. <a href="politik/#pGes">Alle Geschäfte →</a></p></section>')
        # Parteien
        body += '<section class="block"><div class="shead"><h2>Das sagen die Parteien</h2><span>Meldungen zum Thema</span></div>'
        if posts:
            ps = sorted({p["party"] for p in posts})
            body += ('<div class="chips" id="dChips" role="group" aria-label="Partei">'
                     + "".join(f'<button type="button" class="chip" data-v="{B.esc(v)}" aria-pressed="{"true" if v == "alle" else "false"}">{B.esc(l)}</button>'
                               for v, l in [("alle", "Alle")] + [(x, x) for x in ps]) + "</div>"
                     '<div class="nlist" id="dPosts">' + "".join(
                         f'<a href="{B.esc(p["url"])}" data-p="{B.esc(p["party"])}"><span class="d"><b>{B.esc(p["party"])}</b>{B.dlabel(p["date"])}</span>'
                         f'<span class="c"><span class="t">{B.esc(p["title"])}</span>' + (f'<span class="l">{B.esc(p["lead"])}</span>' if p.get("lead") else "")
                         + f'<span class="psrc2">{B.esc(p.get("partyName"))} {B.EXT}</span></span></a>' for p in posts) + "</div>")
        else:
            body += '<p class="note">Zurzeit keine Meldungen der Parteien zu diesem Thema (berücksichtigt werden die letzten vier Monate).</p>'
        body += ('<p class="note">Automatisch von den Websites der Parteien übernommen und über Stichworte zugeordnet. '
                 'Alle Parteien werden gleich behandelt; zug.now wählt nicht aus und wertet nicht.</p></section>')
        if votes:
            body += ('<section class="block"><div class="shead"><h2>Abstimmungen zum Thema</h2></div><div class="amtlist">'
                     + "".join(f'<a href="{B.esc(v["url"])}"><span class="d">{B.dlabel(v["date"])}</span><span class="t"><span class="lbl" style="display:block;margin-bottom:2px">'
                               f'{DOM.get(v.get("domain"), "")}</span>{B.esc(v["title"])}</span></a>' for v in votes) + "</div></section>")
        body += ('<section class="block"><div class="shead"><h2>Meldungen von Stadt und Amtsblatt</h2><span>Automatisch zugeordnet</span></div>'
                 + (('<div class="amtlist">' + "".join(
                     f'<a href="{B.esc(u)}"><span class="d">{B.dlabel(d)}</span><span class="t"><span class="lbl" style="display:block;margin-bottom:2px">{B.esc(l)}</span>{B.esc(ti)}</span></a>'
                     for d, l, ti, u in meld) + "</div>") if meld else '<p class="note">Zurzeit keine Meldungen zu diesem Thema.</p>')
                 + "</section>")
        others = " · ".join(f'<a href="/politik/{o["slug"]}/">{B.esc(o["titel"])}</a>' for o in themen if o is not t)
        body += (f'<section class="block"><p class="note">Stand {stand}. Redaktionell aus öffentlichen Quellen zusammengestellt, Meldungen automatisch zugeordnet. '
                 f'Massgebend sind die amtlichen Publikationen.</p><p><a href="politik/">← Politik</a> · Weitere Dossiers: {others}</p></section>')
        desc = f'{t["titel"]} in der Stadt Zug: laufende Geschäfte, Vorhaben, Abstimmungen und was die Parteien sagen – an einem Ort.'
        page = H._page(frame, f'politik/{t["slug"]}/', f'{t["titel"]} – Politik Stadt Zug | zug.now', desc, body, nav="politik/",
                       index=bool(n_items or ges or len(posts) + len(meld) >= 3))
        pages[f'politik/{t["slug"]}/index.html'] = page.replace("</body>", FILTER_JS + "\n</body>", 1)

    G = pol.get("geschaefte") or {}
    politik_html = B.fill(politik_html, "gesList", "".join(_ges_row("vorstoss", v) for v in (G.get("vorstoesse") or [])[:10]))
    pages["politik.html"] = B.fill(politik_html, "polDossiers", "".join(cards))
    print(f"Dossiers: {len(themen)} Themen")
    return pages
