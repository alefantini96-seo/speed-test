"""
Report HTML self-contained. Nessuna risorsa esterna, nessun JavaScript:
si apre da file, si allega a una mail, si stampa in PDF con Ctrl+P.

Il CSS e' scritto per la stampa: A4, niente sfondi pieni, interruzioni di pagina
fra un template e l'altro.
"""
from __future__ import annotations

from datetime import date
from html import escape

from ..core.extract import FASI_IT
from ..core.soglie import ETICHETTE, SOGLIE, formatta, giudizio
from ..core.aggregazione import raggruppa
from ..core.thirdparty import etichetta_tipo

COLORI = {"buono": "#1a7f4b", "da_migliorare": "#a16207", "scarso": "#b42318", "sconosciuto": "#6b7280"}
PAROLA = {"buono": "buono", "da_migliorare": "da migliorare", "scarso": "scarso", "sconosciuto": "n/d"}
GRAVITA = {"alta": "#b42318", "media": "#a16207", "bassa": "#6b7280"}

CSS = """
:root { --testo:#1f2328; --tenue:#6b7280; --bordo:#e5e7eb; --sfondo:#fff; }
* { box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       color:var(--testo); background:var(--sfondo); margin:0; padding:32px;
       max-width:920px; margin-inline:auto; line-height:1.5; }
h1 { font-size:24px; margin:0 0 4px; }
h2 { font-size:19px; margin:36px 0 4px; padding-top:20px; border-top:2px solid var(--testo); }
h3 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:var(--tenue);
     margin:22px 0 8px; font-weight:600; }
.sottotitolo { color:var(--tenue); font-size:14px; margin:0 0 28px; }
.url { font-family:ui-monospace,Consolas,monospace; font-size:12px; color:var(--tenue);
       word-break:break-all; margin:2px 0 14px; }
table { width:100%; border-collapse:collapse; font-size:14px; margin:8px 0 4px; }
th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--bordo); }
th { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--tenue); font-weight:600; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px;
        font-weight:600; border:1px solid currentColor; }
.fase { display:flex; align-items:center; gap:10px; font-size:13px; margin:3px 0; }
.fase .barra { height:9px; background:#dbe1e8; border-radius:2px; }
.fase .barra.dom { background:#b42318; }
.fase .et { width:210px; color:var(--tenue); }
.fase .pc { width:44px; text-align:right; font-variant-numeric:tabular-nums; }
.problema { border:1px solid var(--bordo); border-left:3px solid var(--tenue);
            border-radius:4px; padding:12px 14px; margin:10px 0; }
.problema h4 { margin:0 0 2px; font-size:15px; }
.meta { font-size:11px; color:var(--tenue); text-transform:uppercase; letter-spacing:.04em; }
ul { margin:8px 0 0; padding-left:18px; font-size:14px; }
li { margin:3px 0; }
.evidenza li { color:var(--tenue); font-size:13px; }
.nota { font-size:12px; color:var(--tenue); font-style:italic; margin-top:8px; }
.nota a { color:var(--tenue); }
.guadagno { float:right; font-size:13px; font-weight:600; color:#b42318;
            font-variant-numeric:tabular-nums; }
.marchio { display:inline-block; margin-left:8px; padding:1px 7px; border-radius:9px;
           font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.04em;
           color:#6b7280; border:1px solid #d1d5db; vertical-align:middle; }
table.risorse { margin:10px 0 4px; font-size:12px; }
table.risorse th { font-size:10px; }
table.risorse td.tag { width:26px; color:var(--tenue); font-size:10px; font-weight:600; }
table.risorse td.risorsa { font-family:ui-monospace,Consolas,monospace; font-size:11px;
                           word-break:break-all; }
table.risorse .percorso { color:var(--tenue); font-size:10px; }
.avviso { background:#fffbeb; border:1px solid #fde68a; border-radius:4px;
          padding:10px 14px; font-size:13px; margin:14px 0; }
footer { margin-top:44px; padding-top:14px; border-top:1px solid var(--bordo);
         font-size:12px; color:var(--tenue); }
@media print {
  body { padding:0; max-width:none; font-size:12px; }
  h2 { break-before:page; }
  h2:first-of-type { break-before:avoid; }
  .problema { break-inside:avoid; }
}
"""


def _e(t) -> str:
    return escape(str(t if t is not None else ""))


def _sparkline(valori: list, soglia_buona: float, soglia_scarsa: float,
               larghezza: int = 260, altezza: int = 40) -> str:
    puliti = [(i, v) for i, v in enumerate(valori) if v is not None]
    if len(puliti) < 2:
        return ""
    vals = [v for _, v in puliti]
    lo, hi = min(vals + [soglia_buona]), max(vals + [soglia_scarsa])
    span = (hi - lo) or 1
    passo = larghezza / (len(valori) - 1)

    def y(v):
        return altezza - (v - lo) / span * altezza

    punti = " ".join(f"{i * passo:.1f},{y(v):.1f}" for i, v in puliti)
    y_buona, y_scarsa = y(soglia_buona), y(soglia_scarsa)
    return (
        f'<svg width="{larghezza}" height="{altezza}" viewBox="0 0 {larghezza} {altezza}" '
        f'style="overflow:visible">'
        f'<line x1="0" y1="{y_buona:.1f}" x2="{larghezza}" y2="{y_buona:.1f}" '
        f'stroke="#1a7f4b" stroke-width="1" stroke-dasharray="3 3" opacity=".55"/>'
        f'<line x1="0" y1="{y_scarsa:.1f}" x2="{larghezza}" y2="{y_scarsa:.1f}" '
        f'stroke="#b42318" stroke-width="1" stroke-dasharray="3 3" opacity=".55"/>'
        f'<polyline points="{punti}" fill="none" stroke="#1f2328" stroke-width="1.6"/>'
        f'</svg>')


def _tabella_campo(campo: dict) -> str:
    metriche = campo.get("metriche") or {}
    if not metriche:
        return ('<div class="avviso">Nessun dato di campo per questo URL: '
                'CrUX non ha traffico sufficiente. Restano validi solo i fatti '
                'diagnostici del lab, senza metrica reale ne\' storico.</div>')

    storico = (campo.get("storico") or {}).get("serie", {})
    periodi = (campo.get("storico") or {}).get("periodi", [])
    righe = []
    for m, v in metriche.items():
        if m not in ETICHETTE:
            continue
        g = giudizio(m, v)
        serie = storico.get(m, [])
        puliti = [x for x in serie if x is not None]
        delta = ""
        if len(puliti) >= 2:
            d = puliti[-1] - puliti[0]
            unita = SOGLIE[m].unita
            delta = f"{d:+.0f} {unita}" if unita else f"{d:+.2f}"
        spark = _sparkline(serie, SOGLIE[m].buono, SOGLIE[m].scarso) if serie else ""
        righe.append(
            f"<tr><td><strong>{_e(ETICHETTE[m])}</strong></td>"
            f'<td class="num">{_e(formatta(m, v))}</td>'
            f'<td><span class="pill" style="color:{COLORI[g]}">{PAROLA[g]}</span></td>'
            f'<td class="num">{_e(delta)}</td>'
            f"<td>{spark}</td></tr>")

    intestazione = ""
    if periodi:
        intestazione = (f'<p class="meta">storico {_e(periodi[0])} &rarr; {_e(periodi[-1])} '
                        f'&middot; {len(periodi)} settimane &middot; delta = ultimo meno primo</p>')
    return (f'<table><tr><th>metrica</th><th class="num">p75 reale</th><th></th>'
            f'<th class="num">delta</th><th>andamento</th></tr>{"".join(righe)}</table>'
            f"{intestazione}")


def _fasi_lcp(fatti: dict) -> str:
    fasi = fatti.get("lcp_fasi") or {}
    if not fasi:
        return ""
    totale = sum(fasi.values()) or 1
    dominante = max(fasi, key=fasi.get)
    barre = []
    for chiave, valore in fasi.items():
        quota = valore / totale
        classe = "barra dom" if chiave == dominante else "barra"
        barre.append(
            f'<div class="fase"><span class="et">{_e(FASI_IT.get(chiave, chiave))}</span>'
            f'<span class="{classe}" style="width:{quota * 260:.0f}px"></span>'
            f'<span class="pc">{quota * 100:.0f}%</span></div>')
    snippet = fatti.get("lcp_elemento_snippet") or ""
    riga_elemento = (f'<p class="url">elemento LCP: {_e(snippet[:200])}</p>' if snippet else "")
    return ("<h3>Dove si perde il tempo dell'LCP</h3>" + "".join(barre) + riga_elemento +
            '<p class="nota">Proporzioni sul trace osservato: non sommano alla metrica LCP '
            "riportata da Lighthouse, che e' simulata con throttling.</p>")


FONTE = {
    "lighthouse": "testo di Lighthouse",
    "classificazione": "classificazione su dati di laboratorio",
    "campo": "classificazione su dati di campo",
}


def _risorse(righe: list) -> str:
    """I file che causano il problema, con la misura e l'attribuzione."""
    if not righe:
        return ""
    corpo = "".join(
        f'<tr><td class="tag">{"3P" if terza else "1P"}</td>'
        f'<td class="risorsa">{_e(url)}</td>'
        f'<td class="num">{_e(misura)}</td></tr>'
        for url, misura, terza in righe)
    return (f'<table class="risorse"><tr><th></th><th>risorsa</th>'
            f'<th class="num">impatto</th></tr>{corpo}</table>')


def _elementi(righe: list) -> str:
    """Gli elementi del DOM indicati da Lighthouse: selettore, percorso, misura.

    Vanno resi separati dalle risorse: un nodo non ha un'unita' di prima o terza
    parte, e marcarlo "1P" sarebbe un'informazione inventata.
    """
    if not righe:
        return ""
    corpo = "".join(
        f'<tr><td class="risorsa">{_e(riferimento)}'
        f'{f"<br><span class=percorso>{_e(percorso)}</span>" if percorso else ""}</td>'
        f'<td class="num">{_e(misura)}</td></tr>'
        for riferimento, misura, percorso, _snippet in righe)
    return (f'<table class="risorse"><tr><th>elemento nel DOM</th>'
            f'<th class="num">impatto</th></tr>{corpo}</table>')


def _peso_per_tipo(per_tipo: dict) -> str:
    """Di che tipo e' il peso: dice quale intervento serve, dove il riepilogo
    terze parti dice a chi tocca. Sono complementari."""
    if not per_tipo:
        return ""
    voci = " &middot; ".join(f"{_e(etichetta_tipo(tipo))} {byte / 1024:.0f} KB"
                             for tipo, byte in list(per_tipo.items())[:6] if byte)
    return f'<p class="meta">{voci}</p>' if voci else ""


def _bersagli_raggruppati(intervento) -> str:
    """I file su cui agire, raggruppati per template.

    I comuni si isolano in cima: sono il bundle condiviso, e sistemarli una volta
    vale per tutto il sito. Gli altri sono lavoro per pagina.
    """
    righe = []
    for nome in intervento.comuni[:4]:
        _n, misura, dettaglio = intervento.misura_di(nome)
        righe.append(f'<tr><td class="tag">tutti</td>'
                     f'<td class="risorsa" title="{_e(dettaglio)}">{_e(nome)}</td>'
                     f'<td class="num">{_e(misura)}</td></tr>')
    for template in intervento.template:
        propri = intervento.propri_di(template)[:4]
        for nome, misura, dettaglio in propri:
            righe.append(f'<tr><td class="tag">{_e(template.nome[:10])}</td>'
                         f'<td class="risorsa" title="{_e(dettaglio)}">{_e(nome)}</td>'
                         f'<td class="num">{_e(misura)}</td></tr>')
    if not righe:
        return ""
    return (f'<table class="risorse"><tr><th>dove</th><th>su cosa agire</th>'
            f'<th class="num">impatto</th></tr>{"".join(righe)}</table>')


def _interventi(esecuzione: dict) -> str:
    """Un intervento per tipo, non ripetuto per ogni template.

    Su una scansione reale a tre template le schede passano da 37 a 14: il titolo
    era lo stesso, cambiavano solo i file — e quelli restano, raggruppati.
    """
    lista = raggruppa(esecuzione)
    if not lista:
        return ""
    blocchi = []
    for intervento in lista:
        colore = GRAVITA.get(intervento.gravita, "#6b7280")
        guadagno = (f'<span class="guadagno">{_e(intervento.guadagno)}</span>'
                    if intervento.guadagno else "")
        quanti = (f"su {intervento.quanti} template su {intervento.totale_template}"
                  if intervento.totale_template > 1 else "")
        marchio = ("" if intervento.azionabile else
                   '<span class="marchio">non azionabile direttamente</span>')
        evidenza = "".join(f"<li>{_e(x)}</li>" for x in intervento.evidenza)
        azioni = "".join(f"<li>{_e(x)}</li>" for x in intervento.azioni)
        doc = (f'<p class="nota"><a href="{_e(intervento.documentazione)}">'
               f"Documentazione Google</a></p>" if intervento.documentazione else "")
        blocchi.append(
            f'<div class="problema" style="border-left-color:{colore}">'
            f'<h4>{_e(intervento.titolo)}{marchio}{guadagno}</h4>'
            f'<p class="meta">{_e(quanti)}{" &middot; " if quanti else ""}'
            f'interviene: {_e(intervento.responsabile)} &middot; '
            f'{_e(FONTE.get(intervento.fonte, intervento.fonte))}</p>'
            f'<ul class="evidenza">{evidenza}</ul><ul>{azioni}</ul>'
            f'{_bersagli_raggruppati(intervento)}'
            f'{f"<p class=nota>{_e(intervento.nota)}</p>" if intervento.nota else ""}'
            f"{doc}</div>")
    return (f'<h2>Interventi</h2><p class="meta">{len(lista)} interventi per il sito, '
            f"con i file su cui agire raggruppati per template</p>"
            f"{''.join(blocchi)}")


def _problemi(problemi: list) -> str:
    if not problemi:
        return "<p>Nessun problema rilevato oltre soglia.</p>"
    blocchi = []
    for p in problemi:
        evidenza = "".join(f"<li>{_e(x)}</li>" for x in p.get("evidenza", []))
        azioni = "".join(f"<li>{_e(x)}</li>" for x in p.get("azioni", []))
        nota = f'<p class="nota">{_e(p["nota"])}</p>' if p.get("nota") else ""
        doc = (f'<p class="nota"><a href="{_e(p["documentazione"])}">'
               f"Documentazione Google</a></p>" if p.get("documentazione") else "")
        colore = GRAVITA.get(p.get("gravita", "bassa"), "#6b7280")
        marchio = ("" if p.get("azionabile", True) else
                   '<span class="marchio">non azionabile direttamente</span>')
        blocchi.append(
            f'<div class="problema" style="border-left-color:{colore}">'
            f'<h4>{_e(p["titolo"])}{marchio}</h4>'
            f'<p class="meta">priorita\' {_e(p.get("gravita"))} &middot; '
            f'interviene: {_e(p.get("responsabile"))} &middot; '
            f'{_e(FONTE.get(p.get("fonte"), p.get("fonte")))}</p>'
            f'<ul class="evidenza">{evidenza}</ul>'
            f"<ul>{azioni}</ul>"
            f'{_risorse(p.get("risorse") or [])}'
            f'{_elementi(p.get("elementi") or [])}{nota}{doc}</div>')
    return "".join(blocchi)


def _nota_ordinamento(esecuzione: dict) -> str:
    """Quando l'ordine non e' pesato sul traffico, va detto: e' la differenza fra
    "questo va fatto prima" e "questo e' piu' grave su una pagina qualsiasi"."""
    if esecuzione.get("ordinamento_pesato"):
        return ""
    return ('<div class="avviso"><strong>Ordinamento non pesato.</strong> '
            "Gli interventi sono ordinati per gravita' sul campo, ma tutti i template contano uguale: nel file di configurazione non e' dichiarato il traffico. Con `sessioni` o `quota_traffico` per template l'ordine tiene conto di quante persone ne sono toccate.</div>")


def _trasversale(pagine: list) -> str:
    """Se tutti i template perdono nella stessa fase, l'intervento e' uno solo."""
    fasi = {}
    for p in pagine:
        f = (p.get("fatti") or {}).get("lcp_fasi") or {}
        if f:
            fasi.setdefault(max(f, key=f.get), []).append(p["template"])
    if not fasi:
        return ""
    if len(fasi) == 1:
        fase, template = next(iter(fasi.items()))
        return (f'<div class="avviso"><strong>Diagnosi trasversale.</strong> Tutti i '
                f"template misurati ({_e(', '.join(template))}) perdono il tempo LCP nella "
                f"stessa fase: <em>{_e(FASI_IT.get(fase, fase))}</em>. Il problema e' del sito, "
                f"non delle singole pagine: un intervento solo li sistema tutti.</div>")
    dettaglio = "; ".join(f"{_e(FASI_IT.get(f, f))}: {_e(', '.join(t))}" for f, t in fasi.items())
    return (f'<div class="avviso"><strong>Diagnosi trasversale.</strong> I template perdono '
            f"tempo in fasi diverse ({dettaglio}). Sono interventi separati: la priorita' "
            f"va data ai template con piu' traffico.</div>")


def html_report(esecuzione: dict) -> str:
    pagine = esecuzione.get("pagine", [])
    sezioni = []
    for p in pagine:
        if p.get("errore"):
            sezioni.append(f'<h2>{_e(p["template"])}</h2>'
                           f'<div class="avviso">Misurazione fallita: {_e(p["errore"])}</div>')
            continue
        fatti = p.get("fatti") or {}
        terze = p.get("terze_parti") or {}
        quota = terze.get("byte_terzi", 0) / (terze.get("byte_totali") or 1)
        sezioni.append(
            f'<h2>{_e(p["template"])}</h2>'
            f'<p class="url">{_e(p["url"])}</p>'
            f'<p class="meta">{_e(p.get("misurazioni", 1))} misurazioni di laboratorio'
            f'{" &middot; " + _e(p["consenso"]) if p.get("consenso") else ""}</p>'
            f"{_tabella_campo(p.get('campo') or {})}"
            f"{_fasi_lcp(fatti)}"
            f"<h3>Peso della pagina</h3>"
            f"<p>{terze.get('byte_totali', 0) / 1024:.0f} KB su "
            f"{terze.get('richieste_totali', 0)} richieste, di cui "
            f"<strong>{terze.get('byte_terzi', 0) / 1024:.0f} KB di terze parti "
            f"({quota * 100:.0f}%)</strong>.</p>"
            f"{_peso_per_tipo(p.get('peso_per_tipo') or {})}"
            )

    vetrina = ", ".join(
        f"{_e(p['template'])} {(p.get('fatti') or {}).get('performance_score')}"
        for p in pagine if (p.get("fatti") or {}).get("performance_score") is not None)

    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Velocita' {_e(esecuzione.get('cliente'))} — {_e(esecuzione.get('data'))}</title>
<style>{CSS}</style></head><body>
<h1>Analisi velocita' — {_e(esecuzione.get('cliente'))}</h1>
<p class="sottotitolo">{_e(esecuzione.get('sito'))} &middot;
rilevazione del {_e(esecuzione.get('data'))} &middot;
{_e('mobile' if esecuzione.get('form_factor') == 'PHONE' else 'desktop')} &middot;
un URL rappresentativo per template</p>
{_trasversale(pagine)}
{_nota_ordinamento(esecuzione)}
<div class="avviso">Le metriche <strong>p75 reale</strong> vengono da CrUX: sono
l'esperienza degli utenti veri, su una finestra mobile di 28 giorni. Un intervento
messo online oggi entra in questi numeri gradualmente e si legge pulito solo dopo
quattro settimane. I fatti diagnostici (elemento LCP, fasi, peso) vengono invece da
una misurazione di laboratorio, che serve a capire <em>perche'</em>, non <em>quanto</em>.</div>
{"".join(sezioni)}
{_interventi(esecuzione)}
<footer>Punteggi PageSpeed Insights al momento della rilevazione: {vetrina or 'n/d'}.
Sono riportati solo come riferimento — variano fra due misurazioni identiche e non
vengono usati per nessuna valutazione in questo documento.<br>
Generato il {date.today():%d/%m/%Y} con speed-audit.</footer>
</body></html>"""

