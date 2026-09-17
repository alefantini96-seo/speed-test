"""
Report HTML self-contained. Nessuna risorsa esterna, nessun JavaScript:
si apre da file, si allega a una mail, si stampa in PDF con Ctrl+P.

Il CSS e' scritto per la stampa: A4, niente sfondi pieni, interruzioni di pagina
fra un template e l'altro.
"""
from __future__ import annotations

from datetime import date
from html import escape

from dataclasses import fields

from ..core.cascata import cascata, piu_lente
from ..core.extract import FASI_IT, Richiesta
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
.tessere { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 4px; }
.tessera { border:1px solid var(--bordo); border-radius:4px; padding:8px 12px; min-width:104px; }
.tessera .et { display:block; font-size:10px; text-transform:uppercase;
               letter-spacing:.04em; color:var(--tenue); }
.tessera .val { font-size:17px; font-weight:600; font-variant-numeric:tabular-nums; }
.filmstrip { display:flex; gap:5px; margin:8px 0 4px; }
/* I fotogrammi si dividono la riga invece di avere una larghezza fissa: otto da
   104px sforavano di 18px la larghezza del testo e l'ultimo andava a capo da
   solo, facendo leggere la sequenza come due sequenze. */
.filmstrip figure { margin:0; flex:1 1 0; min-width:0; }
.filmstrip img { width:100%; height:auto; border:1px solid var(--bordo);
                 display:block; }
.filmstrip figcaption { font-size:10px; color:var(--tenue); text-align:center; margin-top:3px;
                        font-variant-numeric:tabular-nums; }
.finale { max-width:260px; border:1px solid var(--bordo); border-radius:3px; }
ol.catena { font-size:13px; padding-left:18px; }
ol.catena code { font-family:ui-monospace,Consolas,monospace; font-size:11px; word-break:break-all; }
table.cascata { font-size:11px; table-layout:fixed; }
table.cascata th,table.cascata td { padding:2px 6px; border-bottom:none; }
table.cascata tr:nth-child(even) td { background:#fafbfc; }
table.cascata td.nome { font-family:ui-monospace,Consolas,monospace; overflow:hidden;
                        text-overflow:ellipsis; white-space:nowrap; }
table.cascata td.nome .terza { color:var(--tenue); }
.linea { position:relative; height:10px; white-space:nowrap; overflow:hidden; }
/* nowrap: le tre parti della barra sommano al 100% della cella, e il minimo
   garantito al tratto puo' sforare di un decimo - senza, la riga andrebbe a capo */
.linea .coda { display:inline-block; height:7px; background:#e5e7eb; vertical-align:middle; }
.linea .tratto { display:inline-block; height:7px; background:#1f2328; vertical-align:middle;
                 min-width:1px; border-radius:1px; }
.linea .tratto.terza { background:#a16207; }
.righello { position:relative; font-size:9px; color:var(--tenue);
            font-weight:400; text-transform:none; letter-spacing:0; }
/* Una riga per riferimento, e il filetto scende fino in fondo al righello.
   Cosi' due etichette non possono sovrapporsi nemmeno quando i riferimenti si
   ammassano - e si ammassano: la scala della cascata arriva all'ultima
   richiesta, che su una pagina con beacon di analytics finisce molto dopo
   l'ultimo evento di paint. */
.righello span { position:absolute; white-space:nowrap;
                 border-left:1px solid var(--bordo); padding-left:2px; }
.righello span.destra { border-left:none; border-right:1px solid var(--bordo);
                        padding-left:0; padding-right:2px; }
footer { margin-top:44px; padding-top:14px; border-top:1px solid var(--bordo);
         font-size:12px; color:var(--tenue); }
@media print {
  body { padding:0; max-width:none; font-size:12px; }
  h2 { break-before:page; }
  h2:first-of-type { break-before:avoid; }
  .problema { break-inside:avoid; }
  .filmstrip, table.cascata { break-inside:avoid; }
  details.lunga { display:none; }
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



# --------------------------------------------------------------------------- #
#  Cio' che si vede del caricamento: fotogrammi, redirect, cascata delle
#  richieste, numeri di riferimento. Tutto da una misurazione di laboratorio, e
#  il report lo dichiara ogni volta: la metrica resta il campo (ADR-001).
# --------------------------------------------------------------------------- #

# Quante righe di cascata restano a vista. Oltre, la lista continua dentro un
# `<details>`: su una pagina reale sono 126 richieste, e stamparle tutte
# occuperebbe tre pagine di PDF per un dettaglio che si guarda a schermo.
CASCATA_VISIBILI = 30

LAB_IN_VETRINA = ("FCP", "SI", "TTI", "TTFB")

# Altezza di una riga del righello della cascata, in pixel. Ogni riferimento ha
# la sua: e' cio' che rende impossibile la sovrapposizione.
RIGHELLO_PASSO = 11


def _durata(ms) -> str:
    if ms is None:
        return "n/d"
    ms = float(ms)
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.1f} s".replace(".", ",")


def _peso(byte) -> str:
    byte = float(byte or 0)
    if byte < 1024:
        return f"{byte:.0f} B"
    if byte < 1024 * 1024:
        return f"{byte / 1024:.0f} KB"
    return f"{byte / 1048576:.1f} MB".replace(".", ",")


def _tessere(voci: list) -> str:
    """Righe di numeri con la loro etichetta: la forma in cui questi valori si
    leggono ovunque, da PageSpeed in giu'."""
    if not voci:
        return ""
    celle = "".join(f'<div class="tessera"><span class="et">{_e(et)}</span>'
                    f'<span class="val">{_e(val)}</span></div>' for et, val in voci)
    return f'<div class="tessere">{celle}</div>'


def _richieste(fatti: dict) -> list:
    """Le richieste tornano oggetti dopo il giro dal JSON.

    Le chiavi si filtrano sui campi della dataclass: un run salvato prima che
    esistessero i tempi non deve far fallire la rigenerazione del report, e uno
    salvato dopo un'aggiunta futura nemmeno.
    """
    campi = {f.name for f in fields(Richiesta)}
    return [Richiesta(**{k: v for k, v in r.items() if k in campi})
            for r in (fatti.get("richieste") or []) if isinstance(r, dict)]


def _dettagli_pagina(fatti: dict, terze: dict) -> str:
    """Peso, richieste e quanto ha impiegato quel caricamento a chiudersi."""
    tempi = fatti.get("tempi_osservati") or {}
    voci = [("richieste", str(terze.get("richieste_totali", 0))),
            ("peso", _peso(terze.get("byte_totali", 0)))]
    if tempi.get("Caricata"):
        voci.append(("caricata in", _durata(tempi["Caricata"])))
    if tempi.get("DOM pronto"):
        voci.append(("DOM pronto", _durata(tempi["DOM pronto"])))
    return _tessere(voci)


def _metriche_lab(fatti: dict) -> str:
    """Le quattro misure che completano il quadro e non hanno un pari sul campo.

    Il TTFB va letto sapendo da dove arriva: Lighthouse gira dai server Google, e
    su una pagina italiana riportava 10 ms contro i 403 ms misurati sugli utenti
    reali. Quello vero sta nella tabella di campo.
    """
    lab = fatti.get("metriche_lab") or {}
    voci = [(sigla, _durata(lab[sigla])) for sigla in LAB_IN_VETRINA if lab.get(sigla)]
    if not voci:
        return ""
    return ("<h3>Altre misure di laboratorio</h3>" + _tessere(voci) +
            '<p class="nota">Misurate da un data center Google su una rete simulata: '
            "servono a confrontare due misurazioni fra loro, non a dire quanto aspetta "
            "un utente. FCP e TTFB compaiono anche nella tabella di campo qui sopra: "
            "quelli sono gli utenti reali, questi il laboratorio, e i due numeri non si "
            "confrontano.</p>")


def _categorie(fatti: dict) -> str:
    """I punteggi di Lighthouse, dichiarati per quello che sono."""
    categorie = fatti.get("categorie") or []
    voci = [(c.get("titolo", ""), f"{c.get('punteggio')}")
            for c in categorie if c.get("punteggio") is not None]
    if len(voci) < 2:
        return ""
    return ("<h3>Punteggi Lighthouse</h3>" + _tessere(voci) +
            '<p class="nota">Riferimento, non valutazione: sono i numeri che compaiono '
            "aprendo pagespeed.web.dev, e variano fra due misurazioni identiche. "
            "Accessibilita&#39;, best practice e SEO arrivano dalla stessa misurazione "
            "e non sono state analizzate in questo documento.</p>")


def _catena_redirect(fatti: dict) -> str:
    salti = fatti.get("redirect") or []
    if not salti:
        return ""
    perso = sum(float(s.get("ms") or 0) for s in salti)
    righe = []
    for s in salti:
        speso = f" &middot; {_durata(s.get('ms'))}" if s.get("ms") else ""
        righe.append(f'<li><strong>{_e(s.get("stato"))}</strong> '
                     f'<code>{_e(s.get("da"))}</code> &rarr; '
                     f'<code>{_e(s.get("a"))}</code>{speso}</li>')
    return (f"<h3>Prima del documento</h3>"
            f'<ol class="catena">{"".join(righe)}</ol>'
            f'<p class="nota">{len(salti)} redirect prima di arrivare alla pagina, '
            f"{_durata(perso)} spesi in laboratorio prima che il documento cominci ad "
            f"arrivare. E&#39; tempo che precede qualunque intervento sulla pagina.</p>")


def _filmstrip(fatti: dict) -> str:
    fotogrammi = fatti.get("filmstrip") or []
    if not fotogrammi:
        return ""
    figure = "".join(
        f'<figure><img src="{_e(f.get("immagine"))}" alt="La pagina a '
        f'{_durata(f.get("ms"))} dall&#39;inizio del caricamento">'
        f'<figcaption>{_durata(f.get("ms"))}</figcaption></figure>'
        for f in fotogrammi)
    return ("<h3>Come si vede la pagina mentre carica</h3>"
            f'<div class="filmstrip">{figure}</div>')


def _riga_cascata(barra) -> str:
    tag = "3P" if barra.terza_parte else "1P"
    dettaglio = (f"{barra.url} - {barra.tipo} - {barra.protocollo} - "
                 f"priorita {barra.priorita}")
    coda = (f'<span class="coda" style="width:{barra.coda_pc:.2f}%"></span>'
            if barra.coda_pc > 0.05 else "")
    classe = "tratto terza" if barra.terza_parte else "tratto"
    return (f'<tr><td class="nome" title="{_e(dettaglio)}">'
            f'<span class="terza">{tag}</span> {_e(barra.nome)}</td>'
            f'<td class="linea"><span style="display:inline-block;'
            f'width:{barra.inizio_pc:.2f}%"></span>{coda}'
            f'<span class="{classe}" style="width:{max(barra.durata_pc, 0.15):.2f}%"></span>'
            f'</td><td class="num">{_e(_peso(barra.byte))}</td>'
            f'<td class="num">{_e(_durata(barra.durata_ms))}</td></tr>')


def _cascata(fatti: dict, url: str, domini_propri=()) -> str:
    """La cascata delle richieste, nell'ordine in cui la pagina le ha chieste.

    `domini_propri` sono i CDN e i domini fratelli dichiarati nella
    configurazione. Senza, la cascata marcava terze parti gli stessi host che il
    peso della pagina - due righe sopra - contava prima parte: su un run reale
    118 richieste su 126 con la targhetta 3P sotto un paragrafo che dichiarava
    il 23% di terze parti. Una contraddizione dentro lo stesso documento.
    """
    disegno = cascata(_richieste(fatti), fatti.get("tempi_osservati") or {}, url,
                      domini_propri)
    if not disegno.barre:
        return ""

    # Una riga per riferimento: sovrapporsi diventa impossibile invece che
    # improbabile. Girandone tre a rotazione si toccavano lo stesso, perche' la
    # scala arriva all'ultima richiesta - su una pagina con beacon di analytics
    # sono 30 secondi - mentre i paint stanno tutti nei primi cinque: cinque
    # etichette in un quinto della larghezza non stanno in tre righe.
    # Quelle oltre meta' scala si appendono a destra, o l'ultima uscirebbe dal
    # grafico.
    marchi = []
    for i, r in enumerate(disegno.riferimenti):
        alto = i * RIGHELLO_PASSO
        destra = r.pc > 60
        posa = f"right:{100 - r.pc:.2f}%" if destra else f"left:{r.pc:.2f}%"
        marchi.append(
            f'<span{" class=destra" if destra else ""} style="{posa};'
            f'top:{alto}px;height:calc(100% - {alto}px)">'
            f'{_e(r.etichetta)} {_e(_durata(r.ms))}</span>')
    righello = (f'<div class="righello" style="height:'
                f'{len(disegno.riferimenti) * RIGHELLO_PASSO + 4}px">'
                f'{"".join(marchi)}</div>')
    testa = ('<colgroup><col style="width:30%"><col><col style="width:11%">'
             '<col style="width:11%"></colgroup>'
             f'<tr><th>richiesta</th><th>{righello}</th>'
             f'<th class="num">peso</th><th class="num">in rete</th></tr>')
    visibili = "".join(_riga_cascata(b) for b in disegno.barre[:CASCATA_VISIBILI])
    resto = ""
    nascoste = disegno.barre[CASCATA_VISIBILI:]
    if nascoste:
        righe = "".join(_riga_cascata(b) for b in nascoste)
        resto = (f'<details class="lunga"><summary>le altre {len(nascoste)} richieste'
                 f'</summary><table class="cascata">{testa}{righe}</table></details>')

    elenco = "".join(
        f"<li>{_e(b.nome)} &middot; {_e(_durata(b.durata_ms))} &middot; {_e(_peso(b.byte))}"
        f"{' &middot; terza parte' if b.terza_parte else ''}</li>"
        for b in piu_lente(disegno, 5))
    return ("<h3>Cascata delle richieste</h3>"
            f'<table class="cascata">{testa}{visibili}</table>{resto}'
            f'<p class="nota">{disegno.quante} richieste su una scala di '
            f"{_durata(disegno.scala_ms)}. I tempi sono quelli osservati dal trace, non "
            "le metriche riportate da Lighthouse, che sono simulate su un&#39;altra "
            "scala. La cascata dice in quale ordine la pagina si carica e cosa aspetta "
            "cosa; quanto aspetta un utente vero lo dice il campo.</p>"
            f"<h3>Le richieste piu&#39; lunghe in rete</h3><ul>{elenco}</ul>")


def html_report(esecuzione: dict) -> str:
    pagine = esecuzione.get("pagine", [])
    # Un run salvato prima che la chiave esistesse non ce l'ha: si ricade sul
    # solo dominio della pagina, cioe' su com'era prima.
    domini_propri = esecuzione.get("domini_propri") or ()
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
            f"{_filmstrip(fatti)}"
            f"{_fasi_lcp(fatti)}"
            f"<h3>Peso della pagina</h3>"
            f"{_dettagli_pagina(fatti, terze)}"
            f"<p>Di quel peso, <strong>{terze.get('byte_terzi', 0) / 1024:.0f} KB "
            f"sono di terze parti ({quota * 100:.0f}%)</strong>.</p>"
            f"{_peso_per_tipo(p.get('peso_per_tipo') or {})}"
            f"{_catena_redirect(fatti)}"
            f"{_cascata(fatti, p['url'], domini_propri)}"
            f"{_metriche_lab(fatti)}"
            f"{_categorie(fatti)}"
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

