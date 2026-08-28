"""
Run -> nota tecnica per lo sviluppo: pochi problemi, accorpati per tema.

E' il modello del terzo deliverable nella forma in cui viene consegnato oggi: una
nota di poche pagine che dice quali sono i problemi, in che ordine affrontarli, e
cita PSI per ciascuno. Non e' il documento di riferimento completo — quello e'
`render_md`, che elenca tutto — ed e' proprio la differenza a renderlo utile:
otto voci si leggono in una riunione, quaranta no.

Quattro scelte governano il modulo.

**Si accorpa per tema, non per audit.** `unused-javascript`, `third-parties` e
`network-dependency-tree` sono lo stesso lavoro per chi lo deve fare. La mappa
`TEMI` e' una classificazione nostra, enumerata, e ogni voce dice quali audit
raccoglie.

**Un tema attraversa i template.** Il font delle icone che pesa uguale su tutte
le pagine e' un problema solo, non tre: i file comuni li trova
`aggregazione.Intervento.comuni`, non un occhio umano.

**Il titolo e la gravita' sono calcolati, non scritti a mano.** Il titolo e' un
modello riempito col dato piu' grosso del tema; `bloccante` e' una soglia
dichiarata — tre volte il valore accettabile, o cinque megabyte su una pagina —
non un giudizio.

**La sintesi viene da regole dichiarate.** Le due o tre frasi in testa non sono
prosa libera: ognuna ha una condizione sui numeri e un modello, entrambi in
`REGOLE_SINTESI`, e il documento dichiara che sono nostre (ADR-004).

Funzioni pure sulla forma JSON di un run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .aggregazione import etichetta_pagina, nomi_dichiarati, raggruppa
from .masterplan import etichetta_problema, motivo_esclusione
from .soglie import ETICHETTE, SOGLIA_BUONA_LAB, formatta, giudizio

# --------------------------------------------------------------------------- #
#  Temi: quali audit sono lo stesso lavoro
#
#  L'ordine conta: vince il primo che combacia, e `igiene` chiude come raccolta
#  di cio' che nessuno affronta da solo. Ogni voce elenca i frammenti di chiave
#  audit che raccoglie: sono gli stessi frammenti che usa `ETICHETTA_PROBLEMA`.
# --------------------------------------------------------------------------- #

TEMI = (
    ("peso-pagina", "Peso della pagina",
     ("total-byte-weight", "peso-terze-parti")),
    ("main-thread", "Carico JavaScript sul thread principale",
     ("bootup-time", "mainthread-work", "long-tasks", "total-blocking")),
    ("lcp", "LCP",
     ("lcp-",)),
    ("font", "Font",
     ("font-display", "font-size")),
    ("cache", "Cache del browser",
     ("cache", "bf-cache")),
    ("js-inutile", "JavaScript inutilizzato, terze parti e catena di richieste",
     ("unused-javascript", "duplicated-javascript", "third-parties",
      "network-dependency-tree", "preconnect", "script-treemap")),
    ("reflow", "Reflow forzato da JavaScript",
     ("forced-reflow", "non-composited-animations")),
    ("server", "Risposta del server e redirect",
     ("server-response", "document-latency", "redirect")),
    ("layout", "Spostamenti di layout",
     ("cls-culprits", "layout-shift", "unsized-images")),
    ("igiene", "CSS, polyfill e immagini",
     ("unminified", "unused-css", "legacy-javascript", "image-delivery",
      "render-blocking", "dom-size", "viewport")),
)

TEMA_PREDEFINITO = ("altro", "Altri audit non superati")

# Metrica di laboratorio su cui si misura la gravita' di un tema, quando ne ha una.
METRICA_DEL_TEMA = {
    "main-thread": "TBT", "lcp": "LCP", "server": "TTFB",
    "layout": "CLS", "font": "FCP",
}

ORDINE_GRAVITA = {"bloccante": 0, "alta": 1, "media": 2, "bassa": 3}
ETICHETTA_GRAVITA = {"bloccante": "BLOCCANTE", "alta": "ALTA",
                     "media": "MEDIA", "bassa": "BASSA"}

# Quando un tema diventa BLOCCANTE. Non e' un giudizio: e' una moltiplicazione
# dichiarata sulla soglia di accettabilita' di Google, e una soglia di peso.
FATTORE_BLOCCANTE = 3.0
BYTE_BLOCCANTI = 5 * 1024 * 1024        # 5 MB su una singola pagina


def tema_di(codice: str) -> tuple:
    """(codice tema, titolo). Vince il primo frammento che combacia."""
    for tema, titolo, frammenti in TEMI:
        if any(f in codice for f in frammenti):
            return (tema, titolo)
    return TEMA_PREDEFINITO


# --------------------------------------------------------------------------- #
#  Quadro di sintesi
# --------------------------------------------------------------------------- #

COLONNE_LAB = ("FCP", "LCP", "TBT", "TTI", "CLS")


def _kb(byte) -> str:
    return f"{float(byte or 0) / 1024:,.0f} KiB".replace(",", ".")


def _ms(valore) -> str:
    if valore is None:
        return "n/d"
    if valore >= 1000:
        return f"{valore / 1000:.1f} s".replace(".", ",")
    return f"{valore:.0f} ms"


def _riuscite(esecuzione: dict) -> list:
    return [p for p in esecuzione.get("pagine") or [] if not p.get("errore")]


def quadro(esecuzione: dict) -> dict:
    """Intestazioni e righe della tabella di sintesi, piu' la modalita'.

    Le colonne sono di laboratorio perche' e' l'unica misura che esiste su ogni
    ambiente, staging compreso. Dove il campo c'e', si aggiunge: e' la metrica
    vera, e vederle accanto e' meglio che scegliere.
    """
    pagine = _riuscite(esecuzione)
    con_campo = [p for p in pagine
                 if ((p.get("campo") or {}).get("metriche") or {})]
    # Senza nomi dichiarati la colonna «Template» ripeterebbe l'URL riga per riga.
    con_nome = nomi_dichiarati(pagine)

    intestazioni = (["Template"] if con_nome else []) + ["URL"]
    intestazioni += list(COLONNE_LAB) + ["Peso"]
    if con_campo:
        intestazioni += ["LCP campo", "INP campo"]

    righe = []
    for pagina in pagine:
        lab = (pagina.get("fatti") or {}).get("metriche_lab") or {}
        campo = (pagina.get("campo") or {}).get("metriche") or {}
        riga = ([etichetta_pagina(pagina)] if con_nome else []) + [pagina.get("url", "")]
        for sigla in COLONNE_LAB:
            valore = lab.get(sigla)
            riga.append("n/d" if valore is None
                        else (f"{valore:.3f}".replace(".", ",") if sigla == "CLS"
                              else _ms(valore)))
        riga.append(_kb(lab.get("Peso")))
        if con_campo:
            riga.append(formatta("largest_contentful_paint",
                                 campo.get("largest_contentful_paint")))
            riga.append(formatta("interaction_to_next_paint",
                                 campo.get("interaction_to_next_paint")))
        righe.append(riga)

    return {"intestazioni": intestazioni, "righe": righe,
            "modalita": "campo" if con_campo else "laboratorio",
            "pagine_con_campo": len(con_campo), "pagine": len(pagine),
            "senza_campo": [etichetta_pagina(p) for p in pagine
                            if not ((p.get("campo") or {}).get("metriche") or {})]}


# --------------------------------------------------------------------------- #
#  Sintesi: frasi da regole dichiarate, non prosa
#
#  Ogni voce e' (condizione, modello). La condizione guarda solo numeri misurati;
#  il modello viene riempito con quegli stessi numeri. E' testo nostro, e il
#  documento lo dichiara: nessuna delle due parti e' scritta caso per caso.
# --------------------------------------------------------------------------- #

@dataclass
class Misure:
    """I numeri su cui le regole di sintesi decidono."""
    pagine: int = 0
    peggiore: str = ""
    peggiore_metrica: str = ""
    peggiore_valore: float = 0.0
    cls_entro_soglia: int = 0
    ttfb_min: float = 0.0
    ttfb_max: float = 0.0
    tbt_oltre_soglia: int = 0
    quota_due_tipi: float = 0.0
    due_tipi: str = ""
    template_pesante: str = ""
    peso_massimo: float = 0.0
    peso_minimo: float = 0.0
    template_leggero: str = ""


def _peso_per_tipo_totale(pagina: dict) -> dict:
    return pagina.get("peso_per_tipo") or {}


def misure(esecuzione: dict) -> Misure:
    from .thirdparty import etichetta_tipo

    pagine = _riuscite(esecuzione)
    if not pagine:
        return Misure()

    m = Misure(pagine=len(pagine))
    pesi = []
    for pagina in pagine:
        lab = (pagina.get("fatti") or {}).get("metriche_lab") or {}
        nome = etichetta_pagina(pagina)
        if lab.get("CLS") is not None and lab["CLS"] <= SOGLIA_BUONA_LAB["CLS"]:
            m.cls_entro_soglia += 1
        if lab.get("TBT") is not None and lab["TBT"] > SOGLIA_BUONA_LAB["TBT"]:
            m.tbt_oltre_soglia += 1
        if lab.get("TTFB") is not None:
            m.ttfb_min = min(m.ttfb_min or lab["TTFB"], lab["TTFB"])
            m.ttfb_max = max(m.ttfb_max, lab["TTFB"])
        if lab.get("Peso"):
            pesi.append((lab["Peso"], nome))
        # Il template peggiore si stabilisce sul TBT: e' la metrica di laboratorio
        # che separa di piu' le pagine fra loro.
        if lab.get("TBT") is not None and lab["TBT"] > m.peggiore_valore:
            m.peggiore, m.peggiore_metrica, m.peggiore_valore = nome, "TBT", lab["TBT"]

    if pesi:
        pesi.sort()
        m.peso_minimo, m.template_leggero = pesi[0]
        m.peso_massimo, m.template_pesante = pesi[-1]
        pagina = next(p for p in pagine
                      if etichetta_pagina(p) == m.template_pesante)
        per_tipo = _peso_per_tipo_totale(pagina)
        if per_tipo:
            totale = sum(per_tipo.values()) or 1
            primi = sorted(per_tipo.items(), key=lambda kv: -kv[1])[:2]
            m.quota_due_tipi = sum(v for _k, v in primi) / totale * 100
            nomi = [etichetta_tipo(k) for k, _v in primi]
            m.due_tipi = " e ".join([nomi[0]] + [n.lower() for n in nomi[1:]])
    return m


REGOLE_SINTESI = (
    (lambda m: bool(m.peggiore) and m.pagine > 1,
     "Il template peggiore del set e' {peggiore}, con {peggiore_metrica} "
     "{peggiore_valore_testo}."),
    (lambda m: m.cls_entro_soglia == m.pagine and m.tbt_oltre_soglia > 0
     and m.ttfb_max > 0,
     "Il CLS e' entro soglia su tutte e {pagine} le pagine e il server risponde "
     "in {ttfb_testo}: il tempo non si perde nel layout ne' nel backend, ma nel "
     "peso degli asset e nel JavaScript sul thread principale."),
    (lambda m: m.quota_due_tipi >= 60.0 and bool(m.due_tipi),
     "Su {template_pesante} {due_tipi} valgono il {quota_testo} del peso "
     "scaricato: e' li' che stanno i byte."),
    (lambda m: m.peso_massimo > 0 and m.peso_minimo > 0
     and m.peso_massimo >= m.peso_minimo * 3,
     "Fra il template piu' pesante e il piu' leggero c'e' un fattore "
     "{fattore_testo}: {template_pesante} {peso_massimo_testo} contro "
     "{template_leggero} {peso_minimo_testo}."),
)


def sintesi(esecuzione: dict) -> list:
    """Le frasi di sintesi che le regole autorizzano, gia' riempite coi numeri."""
    m = misure(esecuzione)
    valori = {
        **m.__dict__,
        "peggiore_valore_testo": _ms(m.peggiore_valore),
        "ttfb_testo": (f"{m.ttfb_min:.0f}-{m.ttfb_max:.0f} ms"
                       if m.ttfb_max > m.ttfb_min else f"{m.ttfb_max:.0f} ms"),
        "quota_testo": f"{m.quota_due_tipi:.0f}%",
        "peso_massimo_testo": _kb(m.peso_massimo),
        "peso_minimo_testo": _kb(m.peso_minimo),
        "fattore_testo": (f"{m.peso_massimo / m.peso_minimo:.0f}"
                          if m.peso_minimo else ""),
    }
    return [modello.format(**valori) for condizione, modello in REGOLE_SINTESI
            if condizione(m)]


# --------------------------------------------------------------------------- #
#  Temi
# --------------------------------------------------------------------------- #

@dataclass
class Tema:
    codice: str
    titolo: str                                     # modello riempito coi dati
    gravita: str
    template: list = field(default_factory=list)    # nomi delle pagine toccate
    audit: list = field(default_factory=list)       # chiavi accorpate
    evidenze: list = field(default_factory=list)    # (etichetta, testo)
    citazioni: list = field(default_factory=list)   # (titolo, testo, url)
    responsabili: list = field(default_factory=list)
    esclusioni: list = field(default_factory=list)  # (titolo audit, motivo)
    byte_sprecati: float = 0.0
    ms_sprecati: float = 0.0
    totale_template: int = 0


# Audit che misurano lo stesso lavoro di un altro con un taglio diverso: sommarli
# conta due volte gli stessi byte o gli stessi millisecondi. `script-treemap-data`
# ripete i byte inutilizzati di `unused-javascript` per file sorgente;
# `mainthread-work-breakdown` ripartisce per categoria il lavoro che `bootup-time`
# attribuisce ai singoli script. Per questo il tema prende il MASSIMO fra i suoi
# audit, non la somma — ed e' anche il modo in cui il numero va letto: "fino a".
def _spreco(problema: dict) -> tuple:
    """(byte, ms) sprecati, dai numeri grezzi che `diagnose` mette nel problema.

    Si legge dai problemi e non da `fatti.opportunita` perche' cosi' la nota si
    genera anche da un run salvato dalla versione web, che le opportunita'
    complete le scarta per stare nel limite del corpo di una richiesta. Sono due
    numeri per problema: 700 byte a pagina invece di 59 KB.
    """
    return (float(problema.get("byte_sprecati") or 0),
            float(problema.get("ms_sprecati") or 0))


def _problemi_per_audit(esecuzione: dict) -> dict:
    """{(template, codice): problema} da tutte le pagine riuscite."""
    fuori = {}
    for pagina in _riuscite(esecuzione):
        for problema in pagina.get("problemi") or []:
            fuori[(pagina.get("template", ""), problema.get("codice"))] = problema
    return fuori


def _gravita_tema(codice: str, gravita_audit: str, esecuzione: dict,
                  byte_pagina_massimo: float, dal_campo: bool) -> str:
    """`bloccante` e' una soglia dichiarata, non un giudizio.

    Il peso della pagina fa scattare la soglia in ogni caso: non e' un Core Web
    Vital, il campo non ha niente da dire su quanti megabyte scarica un utente in
    roaming, e il numero e' misurato.

    L'escalation sulle METRICHE di laboratorio invece vale solo quando il campo
    manca. Con il campo disponibile decide il campo (ADR-001): dichiarare
    BLOCCANTE un LCP che in laboratorio e' 10 s e sugli utenti reali e' 1,1 s
    vorrebbe dire riportare la priorita' al laboratorio dalla porta di servizio.
    """
    if byte_pagina_massimo >= BYTE_BLOCCANTI:
        return "bloccante"
    if dal_campo:
        return gravita_audit
    sigla = METRICA_DEL_TEMA.get(codice)
    soglia = SOGLIA_BUONA_LAB.get(sigla or "")
    if sigla and soglia:
        for pagina in _riuscite(esecuzione):
            valore = ((pagina.get("fatti") or {}).get("metriche_lab") or {}).get(sigla)
            if valore is not None and valore >= soglia * FATTORE_BLOCCANTE:
                return "bloccante"
    return gravita_audit


# Un bersaglio piu' lungo di cosi' non si legge in una nota di poche pagine: i
# selettori DOM generati arrivano a 200 caratteri. L'elenco intero, non tagliato,
# sta nel documento di riferimento (`render_md`).
MASSIMO_BERSAGLIO = 72


def accorcia(nome: str) -> str:
    if len(nome) <= MASSIMO_BERSAGLIO:
        return nome
    return nome[:MASSIMO_BERSAGLIO - 1].rstrip() + "\u2026"


# Cosa sono i millisecondi di un tema. Dichiarato per tema perche' non e'
# deducibile dal numero: 865 ms di font-display sono un risparmio stimato
# sull'FCP, 10,5 s di bootup-time sono lavoro misurato sulla CPU. Scrivere
# "sul thread principale" su entrambi sarebbe falso sul primo.
SUFFISSO_MS = {
    "main-thread": "di lavoro sul thread principale",
    "reflow": "di reflow misurato",
    "server": "di risposta del server",
    "font": "di risparmio stimato sull'FCP",
    "lcp": "di risparmio stimato sull'LCP",
}
# Dove il tema NON e' in tabella i millisecondi non si mostrano affatto. In un
# tema misto arrivano da audit diversi — mainThreadTime di un vendor, wastedMs di
# una risorsa — e non c'e' una frase vera che li descriva tutti: dire "di
# risparmio stimato" sarebbe comodo e falso.


def _titolo(codice_tema: str, titolo_tema: str, tema: Tema) -> str:
    """Il modello del titolo, riempito col dato piu' grosso del tema.

    E' testo nostro: la forma e' fissa, i numeri sono misurati, e nessuna delle
    due parti viene scritta caso per caso. "Fino a" e non un totale, perche' il
    valore e' il massimo fra gli audit del tema e fra i template.
    """
    if tema.byte_sprecati >= 1024 * 100:
        return f"{titolo_tema}: fino a {_kb(tema.byte_sprecati)} per pagina"
    if tema.ms_sprecati >= 100 and codice_tema in SUFFISSO_MS:
        return (f"{titolo_tema}: fino a {_ms(tema.ms_sprecati)} "
                f"{SUFFISSO_MS[codice_tema]}")
    sigla = METRICA_DEL_TEMA.get(codice_tema)
    if sigla and tema.template:
        return f"{titolo_tema} oltre soglia su {len(tema.template)} template"
    quanti = len(tema.audit)
    return f"{titolo_tema}: {quanti} audit non superat{'o' if quanti == 1 else 'i'}"


def temi(esecuzione: dict) -> list:
    """I problemi del sito accorpati per tema, in ordine di gravita'."""
    interventi = raggruppa(esecuzione)
    totale = len(_riuscite(esecuzione))
    per_audit = _problemi_per_audit(esecuzione)
    dal_campo = quadro(esecuzione)["modalita"] == "campo"

    pesi = {p.get("template", ""): ((p.get("fatti") or {}).get("metriche_lab") or {}).get("Peso", 0)
            for p in _riuscite(esecuzione)}
    peso_massimo = max(pesi.values(), default=0)

    gruppi: dict = {}
    for intervento in interventi:
        codice, titolo_tema = tema_di(intervento.codice)
        tema = gruppi.get(codice)
        if tema is None:
            tema = Tema(codice=codice, titolo=titolo_tema, gravita="bassa",
                        totale_template=totale)
            gruppi[codice] = tema

        # Massimo e non somma: audit diversi misurano lo stesso lavoro con tagli
        # diversi, e sommarli lo conterebbe due volte.
        for template in intervento.template:
            problema = per_audit.get((template.nome, intervento.codice))
            if problema is None:
                continue
            byte, ms = _spreco(problema)
            tema.byte_sprecati = max(tema.byte_sprecati, byte)
            tema.ms_sprecati = max(tema.ms_sprecati, ms)
        tema.audit.append(intervento.codice)
        for template in intervento.template:
            if template.etichetta not in tema.template:
                tema.template.append(template.etichetta)
        # Il responsabile e' quello dell'audit messo peggio, non l'unione di
        # tutti: "sviluppo + marketing/tag, sviluppo, marketing/tag" non dice a
        # nessuno di cosa deve occuparsi.
        if (not tema.responsabili
                or ORDINE_GRAVITA.get(intervento.gravita, 3)
                < ORDINE_GRAVITA.get(tema.gravita, 3)):
            tema.responsabili = [intervento.responsabile] if intervento.responsabile else []
        if ORDINE_GRAVITA.get(intervento.gravita, 3) < ORDINE_GRAVITA.get(tema.gravita, 3):
            tema.gravita = intervento.gravita

        # La citazione e' testo di Lighthouse, una per audit accorpato.
        if intervento.azioni:
            tema.citazioni.append((intervento.titolo, intervento.azioni[0],
                                   intervento.documentazione))

        # I bersagli condivisi da tutti i template sono l'informazione piu' densa
        # del tema: un file solo che pesa su tutto il sito.
        for nome in intervento.comuni[:3]:
            _n, misura, _d = intervento.misura_di(nome)
            voce = f"{accorcia(nome)} — {misura}" if misura else accorcia(nome)
            if ("Su tutti i template", voce) not in tema.evidenze:
                tema.evidenze.append(("Su tutti i template", voce))

        for template in intervento.template:
            for nome, misura, _dettaglio in intervento.propri_di(template)[:2]:
                if misura:
                    tema.evidenze.append((template.etichetta,
                                          f"{accorcia(nome)} — {misura}"))

        motivo = _motivo_intervento(esecuzione, intervento.codice)
        if motivo:
            tema.esclusioni.append((intervento.titolo, motivo))

    fuori = []
    for codice, titolo_tema, _frammenti in TEMI + (TEMA_PREDEFINITO + ((),),):
        tema = gruppi.get(codice)
        if tema is None:
            continue
        tema.gravita = _gravita_tema(codice, tema.gravita, esecuzione,
                                     peso_massimo, dal_campo)
        tema.titolo = _titolo(codice, titolo_tema, tema)
        tema.evidenze = raggruppa_evidenze(tema.evidenze)
        fuori.append(tema)

    fuori.sort(key=lambda t: (ORDINE_GRAVITA.get(t.gravita, 3), -len(t.template),
                              -t.byte_sprecati))
    return fuori


def raggruppa_evidenze(evidenze: list, massimo: int = 3) -> list:
    """Una riga per etichetta, non sei righe con la stessa etichetta davanti."""
    per_etichetta: dict = {}
    for etichetta, testo in evidenze:
        voci = per_etichetta.setdefault(etichetta, [])
        if testo not in voci and len(voci) < massimo:
            voci.append(testo)
    return [(etichetta, " · ".join(voci)) for etichetta, voci in per_etichetta.items()]


def _motivo_intervento(esecuzione: dict, codice: str) -> str:
    for pagina in _riuscite(esecuzione):
        for problema in pagina.get("problemi") or []:
            if problema.get("codice") == codice:
                return motivo_esclusione(problema)
    return ""


def evidenza_di_apertura(tema: Tema) -> str:
    """Il dato che giustifica il titolo, in una riga.

    Sono gli stessi numeri del titolo piu' il bersaglio piu' pesante: serve a chi
    legge per capire subito se il tema lo riguarda, senza scorrere l'elenco.
    """
    parti = []
    if tema.byte_sprecati >= 1024:
        parti.append(f"fino a {_kb(tema.byte_sprecati)} recuperabili su una pagina")
    if tema.ms_sprecati >= 100 and tema.codice in SUFFISSO_MS:
        parti.append(f"fino a {_ms(tema.ms_sprecati)} {SUFFISSO_MS[tema.codice]}")
    parti.append(f"{len(tema.template)} template su {tema.totale_template}")
    quanti = len(tema.audit)
    parti.append(f"{quanti} audit non superat{'o' if quanti == 1 else 'i'}")
    return "; ".join(parti) + "."


def ordine_di_lavorazione(temi_ordinati: list) -> list:
    """La tabella finale: cosa si fa, su quali pagine, quanto vale."""
    righe = []
    for indice, tema in enumerate(temi_ordinati, start=1):
        if tema.byte_sprecati >= 1024:
            peso = f"fino a {_kb(tema.byte_sprecati)} per pagina"
        elif tema.ms_sprecati and tema.codice in SUFFISSO_MS:
            peso = f"fino a {_ms(tema.ms_sprecati)} {SUFFISSO_MS[tema.codice]}"
        else:
            peso = (f"{len(tema.audit)} audit non "
                    f"superat{'o' if len(tema.audit) == 1 else 'i'}")
        pagine = ("Tutti" if len(tema.template) == tema.totale_template
                  else ", ".join(tema.template))
        righe.append([f"{indice:02d}", tema.titolo, pagine,
                      ETICHETTA_GRAVITA.get(tema.gravita, tema.gravita), peso])
    return righe


def etichette_metriche() -> dict:
    """Le sigle di campo, per chi impagina. Vengono dal core, non si riscrivono."""
    return dict(ETICHETTE)


def giudizio_di(metrica: str, valore) -> str:
    return giudizio(metrica, valore)


def etichetta_audit(codice: str) -> str:
    return etichetta_problema(codice)
