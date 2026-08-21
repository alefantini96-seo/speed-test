"""
Sezione HTML del confronto fra due scansioni.

Riusa il CSS del report: e' lo stesso documento per chi legge, anche quando esce
come file a se'. Le due avvertenze compaiono in testa e non in fondo — servono a
leggere i numeri, non a giustificarli dopo.
"""
from __future__ import annotations

from html import escape

from ..core.confronto import AVVERTENZE
from ..core.soglie import ETICHETTE
from .render import CSS

COLORE_VERSO = {"migliorato": "#1a7f4b", "peggiorato": "#b42318",
                "stabile": "#6b7280", "sconosciuto": "#6b7280"}


def _e(t) -> str:
    return escape(str(t if t is not None else ""))


def _elenco(titolo: str, voci: list, colore: str) -> str:
    if not voci:
        return ""
    righe = "".join(f"<li>{_e(t)}</li>" for _c, t in voci)
    return (f'<h3 style="color:{colore}">{_e(titolo)} ({len(voci)})</h3>'
            f"<ul>{righe}</ul>")


def _metriche(confronto_template) -> str:
    if not confronto_template.metriche:
        return '<p class="attesa">Nessun dato di campo in una delle due scansioni.</p>'
    righe = []
    for movimento in confronto_template.metriche:
        colore = COLORE_VERSO[movimento.verso]
        righe.append(f'<tr><td><strong>{_e(ETICHETTE[movimento.metrica])}</strong></td>'
                     f'<td style="color:{colore}">{_e(movimento.descrivi())}</td></tr>')
    return f"<table>{''.join(righe)}</table>"


def html_confronto(confronto) -> str:
    sezioni = []
    for voce in confronto.template:
        if not voce.qualcosa_e_cambiato:
            sezioni.append(f'<h2>{_e(voce.template)}</h2>'
                           f'<p class="url">{_e(voce.url)}</p>'
                           f"{_metriche(voce)}"
                           f'<p class="attesa">Nessun problema comparso o sparito, '
                           f"nessun movimento oltre soglia.</p>")
            continue
        sezioni.append(
            f'<h2>{_e(voce.template)}</h2>'
            f'<p class="url">{_e(voce.url)}</p>'
            f"{_metriche(voce)}"
            f"{_elenco('Spariti', voce.spariti, '#1a7f4b')}"
            f"{_elenco('Comparsi', voce.comparsi, '#b42318')}"
            f'<p class="meta">{len(voce.restati)} problemi presenti in entrambe '
            f"le scansioni</p>")

    fuori = ""
    if confronto.solo_prima or confronto.solo_dopo:
        parti = []
        if confronto.solo_prima:
            parti.append("presenti solo nella prima scansione: "
                         + ", ".join(confronto.solo_prima))
        if confronto.solo_dopo:
            parti.append("presenti solo nella seconda: " + ", ".join(confronto.solo_dopo))
        fuori = (f'<div class="avviso"><strong>Template non confrontabili.</strong> '
                 f"{_e('; '.join(parti))}. Il confronto sta solo sugli URL comuni.</div>")

    avvertenze = "".join(f'<div class="avviso">{_e(a)}</div>' for a in AVVERTENZE)

    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Confronto {_e(confronto.data_prima)} — {_e(confronto.data_dopo)}</title>
<style>{CSS}
.attesa {{ color:var(--tenue); font-size:13px; font-style:italic; }}
</style></head><body>
<h1>Confronto fra due scansioni</h1>
<p class="sottotitolo">{_e(confronto.data_prima)} &rarr; {_e(confronto.data_dopo)} &middot;
{len(confronto.template)} template confrontati</p>
{avvertenze}
{fuori}
{"".join(sezioni)}
</body></html>"""
