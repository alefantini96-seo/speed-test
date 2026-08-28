"""
Run -> documento tecnico in Markdown, per chi mette mano al codice.

E' il terzo deliverable, e ha un lettore diverso dagli altri due. Il report al
cliente dice se il sito e' lento e quanto costa sistemarlo; qui servono il file,
la riga di configurazione, il nodo del DOM, e il link alla pagina di Google che
spiega quell'audit. Markdown perche' finisce in un ticket o in una PR: si diffa,
si greppa, non ha dipendenze.

Tre scelte che governano il modulo.

**Si legge da `fatti.opportunita`, non da `problemi`.** Le liste dentro i problemi
sono gia' troncate a sei da `diagnose.da_opportunita`: bastano a una scheda, non a
chi deve aprire i file. Qui sono intere — `cache-insight` porta 24 risorse,
`script-treemap-data` 83 — e le lunghe si chiudono in un `<details>` invece di
essere tagliate. Le classificazioni (chi interviene, priorita', azionabilita')
arrivano invece da `problemi`, unite per chiave di audit.

**Si raggruppa per template, non per sito.** E' una divergenza deliberata dal
report al cliente, che raggruppa per sito perche' su tre template 20 schede su 37
erano ripetizioni dello stesso titolo. Ma i file su cui agire quasi non
coincidono — dal 43% allo 0% di sovrapposizione, misurato — e chi sviluppa lavora
per rotta, non per sito.

**ADR-004 vale qui piu' che altrove.** Nessuna raccomandazione scritta da noi:
ogni frase e' testo di Lighthouse, un numero misurato, o una classificazione
nostra marcata come tale. I link alla documentazione sono quelli che Lighthouse
mette nella descrizione; dove non ce n'e' uno, non se ne cerca un sostituto.

Funzioni pure sulla forma JSON di un run: `speed report --formato md` lo rigenera
da una scansione di mesi fa senza rifare nessuna chiamata.
"""
from __future__ import annotations

from ..core.aggregazione import etichetta_pagina
from ..core.extract import FASI_IT
from ..core.masterplan import motivo_esclusione
from ..core.soglie import (fasi_dal_campo, formatta, formatta_risparmio,
                           giudizio)
from ..core.thirdparty import etichetta_tipo

# Oltre questa lunghezza una lista si chiude in un `<details>`. Non si tronca:
# `script-treemap-data` ha 83 righe e chi cerca la sua la deve trovare.
SOGLIA_DETTAGLIO = 8

GIUDIZIO_IT = {"buono": "buono", "da_migliorare": "da migliorare",
               "scarso": "scarso", "sconosciuto": "n/d"}

LIVELLO_CAMPO = {"url": "URL", "origin": "origine", "assente": "assente"}

# I limiti che il README dichiara, ripetuti una volta in testata. Uno sviluppatore
# che rilancia Lighthouse per conto suo e ottiene numeri diversi deve poter capire
# perche' prima di aprire un ticket contro la misurazione.
LIMITI = (
    "Un URL per template: il documento non distingue un problema del template da "
    "un problema di quella specifica pagina.",
    "Le fasi LCP sono proporzioni, non millisecondi confrontabili: il breakdown e' "
    "sul trace osservato, la metrica riportata e' simulata con throttling.",
    "L'INP non e' misurabile in laboratorio: Lighthouse da' solo TBT e long task "
    "come proxy, e l'attribuzione e' meno precisa che sull'LCP.",
    "Il campo e' una media mobile a 28 giorni: un intervento messo online oggi si "
    "legge pulito solo dopo quattro settimane.",
    "Il punteggio PageSpeed non entra in nessuna valutazione (ADR-001): e' rumoroso "
    "e cambia fra due chiamate identiche. Sta in fondo come numero di vetrina.",
)


# --------------------------------------------------------------------------- #
#  Utilita' di scrittura
# --------------------------------------------------------------------------- #

def _pulisci(testo) -> str:
    """Su una riga sola e senza pipe: e' quanto serve a stare in una tabella."""
    return str(testo if testo is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _testo(testo) -> str:
    """Testo di Lighthouse fuori da un code span, reso inerte.

    Gli snippet che Lighthouse allega sono markup vero — `<img srcset=...>` — e in
    Markdown l'HTML inline viene interpretato: la riga spariva dal documento e al
    suo posto compariva l'immagine. Si neutralizza l'apertura del tag, che e'
    quanto basta, invece di riscrivere il testo.
    """
    return str(testo if testo is not None else "").replace("<", "&lt;")


def _cella(testo) -> str:
    """Una cella di tabella: su una riga, senza pipe, e senza HTML attivo."""
    return _testo(_pulisci(testo))


def _codice(testo) -> str:
    """Un code span che regge anche i backtick dentro il testo di Lighthouse.

    Gli snippet HTML e le regole CSS arrivano da Lighthouse cosi' come sono: non
    si riscrivono per farli stare in un code span, si allunga il recinto. Qui NON
    si scappa il minore: dentro un code span il markup e' gia' inerte, e scaparlo
    farebbe comparire `&lt;` nel documento.
    """
    testo = _pulisci(testo)
    if not testo:
        return ""
    recinto = "`"
    while recinto in testo:
        recinto += "`"
    bordo = " " if testo.startswith("`") or testo.endswith("`") else ""
    return f"{recinto}{bordo}{testo}{bordo}{recinto}"


def _tabella(intestazioni: list, righe: list) -> list:
    if not righe:
        return []
    fuori = ["| " + " | ".join(intestazioni) + " |",
             "|" + "|".join("---" for _ in intestazioni) + "|"]
    fuori += ["| " + " | ".join(_cella(c) for c in riga) + " |" for riga in righe]
    return fuori + [""]


def _forse_dettaglio(righe: list, quante: int, sommario: str) -> list:
    """Le liste lunghe si chiudono, non si tagliano.

    La riga vuota dopo `<summary>` non e' decorativa: senza, il Markdown dentro il
    blocco non viene interpretato e la tabella esce come testo grezzo.
    """
    if quante <= SOGLIA_DETTAGLIO:
        return righe
    return ["<details>", f"<summary>{sommario}</summary>", ""] + righe + ["</details>", ""]


def _kb(byte) -> str:
    return f"{float(byte or 0) / 1024:.0f} KB"


def _plurale(quante: int, uno: str, molti: str) -> str:
    return f"{quante} {uno if quante == 1 else molti}"


# --------------------------------------------------------------------------- #
#  Testata
# --------------------------------------------------------------------------- #

def _testata(esecuzione: dict) -> list:
    pagine = esecuzione.get("pagine") or []
    riuscite = [p for p in pagine if not p.get("errore")]
    primo = (riuscite[0].get("fatti") or {}) if riuscite else {}

    strategy = "desktop" if esecuzione.get("form_factor") == "DESKTOP" else "mobile"
    fuori = [
        f"# Interventi tecnici — {esecuzione.get('cliente', 'sito')}",
        "",
        f"Sito: {esecuzione.get('sito', '')}  ",
        f"Scansione del {esecuzione.get('data', '')}  ",
        f"Template misurati: {len(riuscite)}" +
        (f" (piu' {len(pagine) - len(riuscite)} non riuscit"
         f"{'a' if len(pagine) - len(riuscite) == 1 else 'e'})"
         if len(pagine) > len(riuscite) else ""),
        "",
        "## Come e' stato misurato",
        "",
        f"- Laboratorio: PageSpeed Insights, strategia **{strategy}**, "
        f"rete e CPU **simulate con throttling**.",
    ]
    if primo.get("lighthouse_version"):
        fuori.append(f"- Lighthouse {primo['lighthouse_version']}, benchmark index "
                     f"{primo.get('benchmark_index', 0):.0f} "
                     f"(velocita' della macchina che ha misurato: numeri diversi su "
                     f"macchine diverse sono attesi).")

    righe = []
    for pagina in riuscite:
        fatti = pagina.get("fatti") or {}
        campo = pagina.get("campo") or {}
        righe.append([
            etichetta_pagina(pagina),
            _codice(fatti.get("timestamp", "")) or "n/d",
            _plurale(pagina.get("misurazioni", 1), "distinta", "distinte") + ", " +
            _plurale(pagina.get("concordi", 1), "concorde", "concordi"),
            campo.get("periodo_a") or "n/d",
        ])
    if righe:
        fuori += ["- Per template, quando e' stata misurata e su quante misurazioni "
                  "di laboratorio distinte poggia la ripartizione dell'LCP:", ""]
        fuori += _tabella(["Template", "analysisUTCTimestamp", "Misurazioni lab",
                           "Campo fino al"], righe)
    fuori += ["- Il p75 di campo e' CrUX: utenti reali, media mobile a 28 giorni.", ""]

    fuori += ["### Limiti dichiarati", ""]
    fuori += [f"- {limite}" for limite in LIMITI]
    fuori.append("")
    return fuori


# --------------------------------------------------------------------------- #
#  Elenco delle pagine
# --------------------------------------------------------------------------- #

def _metrica(campo: dict, metrica: str) -> str:
    valore = (campo.get("metriche") or {}).get(metrica)
    if valore is None:
        return "n/d"
    return f"{formatta(metrica, valore)} ({GIUDIZIO_IT[giudizio(metrica, valore)]})"


def _elenco_pagine(esecuzione: dict) -> list:
    righe = []
    for pagina in esecuzione.get("pagine") or []:
        if pagina.get("errore"):
            # Il messaggio sta nella sezione della pagina: qui allargherebbe una
            # colonna di metriche fino a rendere illeggibile tutta la tabella.
            righe.append([etichetta_pagina(pagina), _codice(pagina.get("url", "")),
                          "**non riuscita**", "—", "—", "—", "—", "—"])
            continue
        campo = pagina.get("campo") or {}
        terze = pagina.get("terze_parti") or {}
        totali = terze.get("byte_totali") or 0
        quota = (terze.get("byte_terzi", 0) / totali * 100) if totali else 0
        righe.append([
            etichetta_pagina(pagina),
            _codice(pagina.get("url", "")),
            LIVELLO_CAMPO.get(campo.get("livello", "assente"), campo.get("livello", "")),
            _metrica(campo, "largest_contentful_paint"),
            _metrica(campo, "interaction_to_next_paint"),
            _metrica(campo, "cumulative_layout_shift"),
            f"{_kb(totali)} ({quota:.0f}% 3P)" if totali else "n/d",
            len(pagina.get("problemi") or []),
        ])
    if not righe:
        return []
    return ["## Pagine analizzate", ""] + _tabella(
        ["Template", "URL", "Campo", "LCP p75", "INP p75", "CLS p75",
         "Peso", "Interventi"], righe)


# --------------------------------------------------------------------------- #
#  Contesto di una pagina
# --------------------------------------------------------------------------- #

def _contesto_lcp(fatti: dict, campo: dict) -> list:
    """Ripartizione delle fasi con l'origine dichiarata.

    La distinzione fra campo e laboratorio decide chi interviene ed e' la ragione
    di ADR-005: la stessa scelta la fa `diagnose.classifica_lcp`, e si appoggia
    alla stessa funzione del core invece di rifarla.
    """
    metriche = campo.get("metriche") or {}
    dal_campo = fasi_dal_campo(metriche)
    fasi = dal_campo or (fatti.get("lcp_fasi") or {})
    if not fasi:
        return []

    origine = ("campo CrUX (utenti reali)" if dal_campo
               else "laboratorio (trace osservato, oscilla fra un run e l'altro)")
    totale = sum(fasi.values()) or 1
    righe = [[FASI_IT.get(fase, fase), f"{valore / totale * 100:.0f}%", f"{valore:.0f} ms"]
             for fase, valore in sorted(fasi.items(), key=lambda v: -v[1])]
    return [f"**Ripartizione LCP** — origine: {origine}.", ""] + _tabella(
        ["Fase", "Quota", "Durata"], righe)


def _contesto(pagina: dict) -> list:
    fatti = pagina.get("fatti") or {}
    campo = pagina.get("campo") or {}
    fuori = []

    selettore = fatti.get("lcp_elemento_selettore") or ""
    snippet = fatti.get("lcp_elemento_snippet") or ""
    if selettore or snippet:
        fuori.append("**Elemento LCP**")
        if selettore:
            fuori.append(f"- selettore: {_codice(selettore)}")
        if snippet:
            fuori.append(f"- markup: {_codice(snippet)}")
        fuori.append("")

    fuori += _contesto_lcp(fatti, campo)

    controlli = fatti.get("lcp_discovery") or {}
    etichette = fatti.get("lcp_discovery_label") or {}
    if controlli:
        righe = [["superato" if superato else "**fallito**",
                  etichette.get(nome, nome), _codice(nome)]
                 for nome, superato in controlli.items()]
        fuori += ["**Scopribilita' della risorsa LCP** — checklist di Lighthouse.", ""]
        fuori += _tabella(["Esito", "Controllo", "Chiave"], righe)

    per_tipo = pagina.get("peso_per_tipo") or {}
    if per_tipo:
        # Sommato per etichetta, non per tipo grezzo: `Fetch` e `XHR` sono due tipi
        # di Lighthouse che `etichetta_tipo` chiama entrambi "Chiamate XHR", e
        # senza la somma la riga mostrava due volte la stessa voce con numeri diversi.
        per_etichetta: dict = {}
        for tipo, byte in per_tipo.items():
            if byte:
                etichetta = etichetta_tipo(tipo)
                per_etichetta[etichetta] = per_etichetta.get(etichetta, 0) + byte
        voci = " · ".join(f"{nome} {_kb(byte)}" for nome, byte in
                          sorted(per_etichetta.items(), key=lambda kv: -kv[1]))
        fuori += [f"**Peso per tipo di risorsa** — {voci}", ""]

    entita = (pagina.get("terze_parti") or {}).get("entita") or []
    if entita:
        righe = [[e.get("nome", ""), "3P" if e.get("terza_parte") else "1P",
                  _kb(e.get("byte")), e.get("richieste", "")] for e in entita[:10]]
        fuori += ["**Entita' per peso**", ""]
        fuori += _tabella(["Entita'", "Parte", "Peso", "Richieste"], righe)

    consenso = pagina.get("consenso")
    if consenso:
        fuori += [f"> {_testo(consenso)}", ""]
    return fuori


# --------------------------------------------------------------------------- #
#  Un intervento
# --------------------------------------------------------------------------- #

def _classificazione(problema: dict) -> list:
    """La riga marcata come nostra: ADR-004 vuole che si distingua dal resto."""
    parti = [f"priorita' **{problema.get('gravita', 'n/d')}**",
             f"interviene: {problema.get('responsabile', 'n/d')}"]
    if problema.get("guadagno"):
        parti.append(f"guadagno stimato in lab: {problema['guadagno']}")
    motivo = motivo_esclusione(problema)
    if motivo:
        parti.append(f"**fuori dal master plan** — {motivo}")
    return [f"> **Classificazione nostra** — {' · '.join(parti)}.", ""]


def _colonne_risorse(risorse: list) -> list:
    """Solo le colonne che questo audit riempie davvero.

    Lighthouse popola chiavi diverse a seconda dell'audit: una tabella con tre
    colonne di zeri costringe a cercare il numero che conta.
    """
    presenti = [("Peso", lambda r: r.get("byte_totali")),
                ("Sprecati", lambda r: r.get("byte_sprecati")),
                ("Quota", lambda r: r.get("quota_sprecata")),
                ("Tempo", lambda r: r.get("ms_sprecati")),
                ("Motivo", lambda r: r.get("motivo"))]
    return [(nome, leggi) for nome, leggi in presenti
            if any(leggi(r) for r in risorse)]


def _tabella_risorse(risorse: list) -> list:
    if not risorse:
        return []
    colonne = _colonne_risorse(risorse)
    intestazioni = ["#", "Risorsa", "Parte"] + [nome for nome, _ in colonne]

    def valore(nome, leggi, risorsa):
        grezzo = leggi(risorsa)
        if nome in ("Peso", "Sprecati"):
            return _kb(grezzo) if grezzo else ""
        if nome == "Quota":
            return f"{grezzo:.0f}%" if grezzo else ""
        if nome == "Tempo":
            return f"{grezzo:.0f} ms" if grezzo else ""
        return grezzo or ""

    # Ordine per spreco decrescente: e' la proprieta' `spreco` del core, ms se ci
    # sono e byte altrimenti. Decide da dove si comincia.
    ordinate = sorted(risorse, key=lambda r: -(r.get("ms_sprecati")
                                               or r.get("byte_sprecati") or 0))
    righe = []
    for indice, risorsa in enumerate(ordinate, start=1):
        nome = risorsa.get("etichetta") or risorsa.get("url", "")
        righe.append([indice, _codice(nome), "3P" if risorsa.get("terza_parte") else "1P"]
                     + [valore(n, leggi, risorsa) for n, leggi in colonne])

    return _forse_dettaglio(
        _tabella(intestazioni, righe), len(righe),
        f"{len(righe)} file — 1P sono vostri, 3P di terze parti")


def _tabella_elementi(elementi: list) -> list:
    if not elementi:
        return []
    righe = []
    for indice, elemento in enumerate(elementi, start=1):
        misura = elemento.get("misura") or 0
        unita = elemento.get("unita") or ""
        if not misura:
            testo = ""
        elif unita == "byte":
            testo = _kb(misura)
        elif unita == "ms":
            testo = f"{misura:.0f} ms"
        else:
            testo = f"{misura:.3f}"
        righe.append([indice,
                      _codice(elemento.get("selettore") or elemento.get("etichetta", "")),
                      _codice(elemento.get("percorso", "")),
                      _codice(elemento.get("snippet", "")),
                      testo])
    return _forse_dettaglio(
        _tabella(["#", "Selettore", "Percorso DOM", "Markup", "Misura"], righe),
        len(righe), f"{len(righe)} elementi del DOM")


def _voci(voci: list) -> list:
    """Righe che non nominano ne' un file ne' un nodo: un vendor, una categoria di
    lavoro, un anello della catena di rete.

    L'indentazione dell'etichetta e' informazione — nella catena critica dice la
    profondita' della dipendenza — quindi va conservata: qui diventa un code span,
    che in Markdown non collassa gli spazi.
    """
    if not voci:
        return []
    chiavi = []
    for voce in voci:
        for chiave in (voce.get("misure") or {}):
            if chiave not in chiavi:
                chiavi.append(chiave)

    def formatta_misura(chiave, valore):
        if valore is None:
            return ""
        if chiave in ("transferSize", "wastedBytes", "totalBytes",
                      "resourceBytes", "unusedBytes"):
            return _kb(valore)
        if chiave == "score":
            return f"{valore:.3f}"
        return f"{valore:.0f} ms"

    righe = [[_codice(voce.get("etichetta", ""))]
             + [formatta_misura(c, (voce.get("misure") or {}).get(c)) for c in chiavi]
             for voce in voci]
    return _forse_dettaglio(_tabella(["Voce"] + chiavi, righe), len(righe),
                            f"{len(righe)} voci")


def _controlli(controlli: dict) -> list:
    if not controlli:
        return []
    # Dopo il passaggio da JSON la coppia (superato, etichetta) e' una lista.
    righe = [["superato" if voce[0] else "**fallito**", voce[1], _codice(nome)]
             for nome, voce in controlli.items()]
    return _tabella(["Esito", "Controllo", "Chiave"], righe)


def _intervento(problema: dict, opportunita: dict | None) -> list:
    """Un blocco per audit. Il titolo porta la chiave: e' quella che serve a
    rilanciare Lighthouse e a cercare nei changelog quando un audit cambia nome."""
    codice = problema.get("codice", "")
    titolo = problema.get("titolo", codice)
    fuori = [f"#### `{codice}` — {_testo(titolo)}", ""]
    fuori += _classificazione(problema)

    if opportunita is None:
        # Il problema LCP e la constatazione sulle terze parti non nascono da un
        # audit: i loro dati stanno nel contesto della pagina, gia' scritto sopra.
        evidenza = problema.get("evidenza") or []
        fuori += [f"- {_testo(riga)}" for riga in evidenza]
        fuori += [""] if evidenza else []
        azioni = problema.get("azioni") or []
        if azioni:
            fuori += ["Voci di checklist non superate, testuali da Lighthouse:", ""]
            fuori += [f"- {_testo(a)}" for a in azioni] + [""]
        return fuori

    sintesi = []
    if opportunita.get("display"):
        sintesi.append(opportunita["display"])
    risparmi = opportunita.get("risparmi") or {}
    if risparmi:
        sintesi.append("risparmio dichiarato: " + ", ".join(
            f"{m} {formatta_risparmio(m, v)}" for m, v in risparmi.items()))
    if opportunita.get("score") is not None:
        sintesi.append(f"score {opportunita['score']:.2f}")
    if sintesi:
        fuori += [" · ".join(sintesi), ""]

    if opportunita.get("descrizione"):
        fuori += [_testo(opportunita["descrizione"]), ""]
    if opportunita.get("documentazione"):
        fuori += [f"[Documentazione Google]({opportunita['documentazione']})", ""]

    fuori += _tabella_risorse(opportunita.get("risorse") or [])
    fuori += _tabella_elementi(opportunita.get("elementi") or [])
    fuori += _voci(opportunita.get("voci") or [])
    fuori += _controlli(opportunita.get("controlli") or {})
    return fuori


# --------------------------------------------------------------------------- #
#  Composizione
# --------------------------------------------------------------------------- #

def _pagina(pagina: dict) -> list:
    titolo = etichetta_pagina(pagina) or pagina.get("url", "")
    if pagina.get("errore"):
        return [f"## {titolo}", "", _codice(pagina.get("url", "")), "",
                f"**Misurazione non riuscita.** {_testo(pagina['errore'])}", ""]

    fuori = [f"## {titolo}", "", _codice(pagina.get("url", "")), ""]
    fuori += _contesto(pagina)

    problemi = pagina.get("problemi") or []
    per_audit = {o.get("audit"): o
                 for o in ((pagina.get("fatti") or {}).get("opportunita") or [])}
    if not problemi:
        return fuori + ["Nessun intervento oltre soglia su questa pagina.", ""]

    fuori += ["### Interventi", ""]
    if not per_audit:
        # Un run salvato dalla versione web: `fatti_essenziali` scarta le
        # opportunita' per stare nel limite del corpo di una richiesta Vercel.
        fuori += ["> Questo run non porta le opportunita' complete: e' stato salvato "
                  "dalla versione web, che le scarta per stare nel limite di 4,5 MB "
                  "del corpo di una richiesta. Restano le classificazioni e le liste "
                  "gia' troncate a sei. Per il documento intero serve una scansione "
                  "da riga di comando.", ""]
    for problema in problemi:
        fuori += _intervento(problema, per_audit.get(problema.get("codice")))
    return fuori


def markdown_report(esecuzione: dict) -> str:
    """La forma JSON di un run -> il documento tecnico, come stringa."""
    righe = _testata(esecuzione)
    righe += _elenco_pagine(esecuzione)
    for pagina in esecuzione.get("pagine") or []:
        righe += _pagina(pagina)

    vetrina = ", ".join(
        f"{p['template']} {(p.get('fatti') or {}).get('performance_score')}"
        for p in (esecuzione.get("pagine") or [])
        if (p.get("fatti") or {}).get("performance_score") is not None)
    righe += ["---", "",
              f"Punteggi PageSpeed Insights al momento della rilevazione: "
              f"{vetrina or 'n/d'}. Numero di vetrina: non entra in nessuna "
              f"valutazione di questo documento (ADR-001).", ""]
    return "\n".join(righe).rstrip() + "\n"


def scrivi_markdown(esecuzione: dict, percorso):
    percorso.write_text(markdown_report(esecuzione), encoding="utf-8")
    return percorso
