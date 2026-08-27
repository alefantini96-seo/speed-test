"""
Run -> frammento `masterplan.json` per lo script che impagina l'xlsx.

Il deliverable operativo di un audit tecnico in questo workspace e' un xlsx
generato da uno script **esterno a questo repo**, che consuma un audit.json. Qui
non si scrive nessun xlsx: si emette il frammento che quello script impagina.

Tre scelte che governano il modulo:

**Si aggrega per sito, non per template.** N template per M problemi darebbero
centinaia di righe che nessuno legge. Una riga per tipo di intervento, con quanti
template ne sono toccati.

**Ogni riga deve avere un intervento eseguibile.** Le righe non azionabili e le
constatazioni restano fuori, e il motivo si dichiara a chi ha lanciato il comando
invece di sparire.

**Registro telegrafico.** Il dato e basta: niente conseguenze ("altrimenti Google
penalizza"), niente metodo o data ("verificato il 19/08"), niente confronto con
misure precedenti, niente elenco di pagine quando c'e' gia' un tab. Una frase,
un fatto.

Funzioni pure: si parte dalla forma JSON di un run, quindi funziona anche su una
scansione salvata mesi prima.
"""
from __future__ import annotations

import re

from .soglie import ETICHETTE, SOGLIE, giudizio

PRIORITA = {"alta": "Alta", "media": "Media", "bassa": "Bassa"}
ORDINE_GRAVITA = {"alta": 0, "media": 1, "bassa": 2}

# Come si chiama il PROBLEMA, dove il titolo di Lighthouse dice l'INTERVENTO.
# E' una classificazione nostra — l'unica riga del frammento che non sia testo di
# Lighthouse o un numero misurato — e serve perche' "Riduci il codice JavaScript
# inutilizzato" e' un'istruzione, non la descrizione di cio' che non va.
ETICHETTA_PROBLEMA = {
    "lcp-timeToFirstByte": "LCP: tempo perso sul server",
    "lcp-resourceLoadDelay": "LCP: risorsa scoperta tardi",
    "lcp-resourceLoadDuration": "LCP: risorsa troppo pesante",
    "lcp-elementRenderDelay": "LCP: rendering bloccato",
    "unused-javascript": "JavaScript inutilizzato",
    "unused-css": "CSS inutilizzato",
    "legacy-javascript": "JavaScript per browser vecchi",
    "duplicated-javascript": "JavaScript duplicato fra bundle",
    "unminified": "Codice non minificato",
    "bootup-time": "Tempo di esecuzione JavaScript",
    "mainthread-work": "Lavoro sul main thread",
    "long-tasks": "Attivita' lunghe sul main thread",
    "forced-reflow": "Reflow forzato da JavaScript",
    "cache": "Cache del browser breve",
    "server-response": "Risposta del server lenta",
    "document-latency": "Latenza del documento",
    "redirect": "Redirect in catena",
    "render-blocking": "Risorse che bloccano il rendering",
    "network-dependency-tree": "Catena critica di richieste",
    "total-blocking": "Blocco del main thread",
    "font-display": "Font senza font-display",
    "image-delivery": "Immagini troppo pesanti",
    "unsized-images": "Immagini senza dimensioni",
    "cls-culprits": "Elementi che spostano il layout",
    "layout-shift": "Spostamenti di layout",
    "script-treemap": "Byte di script inutilizzati",
    "third-parties": "Peso delle terze parti",
    "total-byte-weight": "Peso totale della pagina",
    "dom-size": "DOM troppo grande",
    "viewport": "Viewport non configurato",
    "non-composited-animations": "Animazioni non composte",
}

# Insight il cui titolo Lighthouse e' un sostantivo e non un'istruzione. Per questi
# l'intervento si prende dall'etichetta del link nella descrizione, dove Lighthouse
# scrive l'azione all'imperativo. Resta testo suo: si sceglie quale, non si riscrive.
TITOLO_DESCRITTIVO = frozenset({
    "third-parties-insight",           # "Terze parti"
    "network-dependency-tree-insight", # "Albero delle dipendenze di rete"
    "cls-culprits-insight",            # "Responsabili delle variazioni del layout"
})

# Audit dove il titolo NON e' un'istruzione e la descrizione non ne offre una:
# il primo link markdown cade in mezzo alla frase e rende un termine, non un
# imperativo. Il ripiego su `azione_breve` qui produceva "font-display" e
# "di base" (<- baseline), che in una colonna "intervento" non dicono cosa fare.
#
# Qui l'azione la scriviamo NOI: e' la quarta origine del testo prevista da
# ADR-004, limitata a questa tabella ed enumerata per audit. Vale per la sola
# cella `intervento` del master plan — il titolo di Lighthouse resta invariato
# ovunque nel report — e ogni riga del frammento dichiara da dove viene il suo
# intervento nel campo `fonte_intervento`.
AZIONE_PER_AUDIT = {
    # sostituisce "Carattere visualizzato" (font-display): un sostantivo, e il
    # primo link della descrizione e' il termine "font-display" a meta' frase.
    "font-display-insight":
        "Imposta font-display su swap o optional sui font della pagina",
    # sostituisce "JavaScript precedente" (legacy JavaScript): il primo link
    # della descrizione e' "di base", cioe' l'etichetta di baseline nella frase.
    "legacy-javascript-insight":
        "Escludi polyfill e transpilazione per i browser moderni dalla build JavaScript",
}

# Non tutte le etichette di link sono interventi: quelle che iniziano con "Scopri"
# sono inviti alla documentazione ("Scopri come ridurre le dimensioni dei payload").
# In quel caso il titolo, per quanto descrittivo, dice piu' cose di un rimando.
INVITI_ALLA_DOCUMENTAZIONE = ("scopri", "learn", "guarda", "leggi")

LARGHEZZE_URL = [24, 74, 14]     # Template | URL | valore
MASSIMO_TAB = 5
MASSIMO_RIGHE_TAB = 60


def _numero(valore: float, decimali: int = 0) -> str:
    """Migliaia col punto, come si scrive in italiano: 4.180 ms."""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", ".") if decimali == 0 else \
        testo.replace(",", "@").replace(".", ",").replace("@", ".")


def _valore_campo(metrica: str, valore) -> str:
    if valore is None:
        return ""
    if SOGLIE.get(metrica) and SOGLIE[metrica].unita == "":
        return _numero(valore, 3)
    return f"{_numero(valore)} ms"


def etichetta_problema(codice: str) -> str:
    for frammento, etichetta in ETICHETTA_PROBLEMA.items():
        if codice.startswith(frammento) or frammento in codice:
            return etichetta
    return codice.replace("-insight", "").replace("-", " ").capitalize()


def intervento_di(problema: dict) -> str:
    """L'istruzione da mettere in colonna. Vedi `fonte_intervento_di` per l'origine.

    Quattro casi, in quest'ordine:

    - titolo gia' imperativo ("Riduci il codice JavaScript inutilizzato"): si usa;
    - titolo descrittivo ("Terze parti"): si usa l'etichetta del link, dove
      Lighthouse scrive l'azione ("Riduci e posticipa il caricamento del codice
      di terze parti");
    - titolo descrittivo senza imperativo da nessuna parte: si usa la voce di
      AZIONE_PER_AUDIT, che e' testo nostro e viene dichiarato;
    - classificazione nostra (la fase LCP): si usa la voce di checklist, che e'
      scritta da Lighthouse ed e' gia' un'istruzione.
    """
    codice = problema.get("codice", "")
    if problema.get("fonte") == "lighthouse":
        if codice in AZIONE_PER_AUDIT:
            return AZIONE_PER_AUDIT[codice]
        breve = problema.get("azione_breve") or ""
        if codice in TITOLO_DESCRITTIVO and breve and                 not breve.lower().startswith(INVITI_ALLA_DOCUMENTAZIONE):
            return breve
        return problema.get("titolo", "")
    azioni = problema.get("azioni") or []
    return azioni[0] if azioni else ""


def fonte_intervento_di(problema: dict) -> str:
    """"nostra" | "lighthouse". Chi ha scritto la cella `intervento` di questa riga.

    Serve a chi impagina l'xlsx e a chi difende il documento davanti al cliente:
    ADR-004 vuole che l'origine del testo sia dichiarata, non dedotta.
    """
    if problema.get("fonte") == "lighthouse" and             problema.get("codice", "") in AZIONE_PER_AUDIT:
        return "nostra"
    return "lighthouse"


# Un displayValue che e' soltanto una quantita': "1,7 s", "2,8 s", "0,095". In una
# cella di audit un numero nudo non dice di cosa sia, e la colonna accanto dice
# cosa fare, non cosa si e' misurato. Quelli che si descrivono da soli —
# "Risparmio stimato di 97 KiB", "15 attivita' lunghe trovate" — non rientrano.
_SOLA_QUANTITA = re.compile(r"^[\d.,]+\s*(ms|s|byte|KiB|KB|MiB|MB)?$", re.IGNORECASE)


def _cella(riga: str, codice: str) -> str:
    """Una riga di evidenza ridotta a cella di audit: dato e numero, niente altro.

    Due riscritture, entrambe su testo gia' misurato:

    - la **fase dominante** perde il prefisso e il trattino, non il nome della
      fase. Tagliare sull'em dash lasciava "39% del tempo LCP", che non dice di
      quale fase sia quel 39% — e la fase e' tutto il contenuto della riga;
    - un **displayValue che e' solo una quantita'** si qualifica con l'etichetta
      del problema, che e' gia' una classificazione nostra dichiarata.
    """
    if riga.startswith("Fase dominante"):
        return re.sub(r"\s*—\s*", " ", riga.split(":", 1)[-1]).strip()
    if _SOLA_QUANTITA.match(riga.strip()):
        return f"{etichetta_problema(codice)} {riga.strip()}"
    return riga


def _evidenza(problema: dict, campo: dict) -> str:
    """Dati misurati: il p75 di campo, piu' il dato di laboratorio piu' concreto.

    La fonte resta implicita nel numero, che e' come si scrive una cella di audit:
    "LCP p75 4.180 ms" non ha bisogno di "secondo CrUX". Dove il numero da solo
    non dice cosa misura, lo qualifica l'etichetta del problema: vedi `_cella`.
    """
    parti = []
    metrica = problema.get("metrica")
    if metrica and metrica in ETICHETTE:
        valore = (campo or {}).get(metrica)
        if valore is not None:
            parti.append(f"{ETICHETTE[metrica]} p75 {_valore_campo(metrica, valore)}")

    # Fra le righe di evidenza si prende la prima che porta un numero e non e' una
    # nostra parafrasi: sono il displayValue di Lighthouse e la fase dominante.
    for riga in problema.get("evidenza") or []:
        if not any(c.isdigit() for c in riga):
            continue
        # "Stima Lighthouse: ..." e la quota di terze parti servono a stabilire
        # priorita' e responsabile, non descrivono il problema: in una cella di
        # audit sarebbero rumore.
        if riga.startswith("Stima Lighthouse") or "dello spreco" in riga:
            continue
        parti.append(_cella(riga, problema.get("codice", "")).rstrip("."))
        break

    return ". ".join(p for p in parti if p) + ("." if parti else "")


def _nome_tab(codice: str, problema_etichetta: str, con_elementi: bool) -> str:
    if codice.startswith("lcp-"):
        return "URL - LCP oltre soglia"
    prefisso = "Elementi" if con_elementi else "Risorse"
    return f"{prefisso} - {problema_etichetta}"


def _righe_url(pagine: list, metrica: str) -> list:
    righe = []
    for pagina in pagine:
        valore = ((pagina.get("campo") or {}).get("metriche") or {}).get(metrica)
        if valore is None:
            continue
        righe.append([pagina.get("template", ""), pagina.get("url", ""),
                      _valore_campo(metrica, valore)])
    return righe


def _tab_metrica(pagine: list, metrica: str) -> dict | None:
    """Un tab con il valore di campo per template. Si crea solo se almeno un
    template e' oltre soglia: la lista di una metrica sana non serve a nessuno."""
    righe = _righe_url(pagine, metrica)
    if not righe:
        return None
    fuori = [p for p in pagine
             if giudizio(metrica, ((p.get("campo") or {}).get("metriche") or {})
                         .get(metrica)) in ("da_migliorare", "scarso")]
    if not fuori:
        return None
    return {"nome": f"URL - {ETICHETTE[metrica]} oltre soglia",
            "intestazioni": ["Template", "URL", f"{ETICHETTE[metrica]} p75"],
            "larghezze": LARGHEZZE_URL,
            "righe": righe}


def _tab_risorse(nome: str, membri: list) -> dict | None:
    """Le risorse o gli elementi nominati dall'audit, con il template di provenienza.

    E' la lista che serve a chi implementa: senza, il master plan dice cosa fare
    ma non su quali file.
    """
    righe, viste = [], set()
    con_elementi = any(m["problema"].get("elementi") for m in membri)
    for membro in membri:
        problema, template = membro["problema"], membro["template"]
        voci = (problema.get("elementi") or []) if con_elementi \
            else (problema.get("risorse") or [])
        for voce in voci:
            riferimento, misura = str(voce[0]), str(voce[1])
            if riferimento in viste:
                continue
            viste.add(riferimento)
            righe.append([template, riferimento, misura])
    if not righe:
        return None
    return {"nome": nome,
            "intestazioni": ["Template", "Elemento" if con_elementi else "Risorsa",
                             "Impatto"],
            "larghezze": LARGHEZZE_URL,
            "righe": righe[:MASSIMO_RIGHE_TAB]}


def motivo_esclusione(problema: dict) -> str:
    """Perche' questo problema non produce una riga di master plan, o "" se la produce.

    Pubblica perche' la usa anche il documento tecnico: allo sviluppatore serve
    sapere che `cache-insight` non gli e' stato assegnato perche' e' tutto su
    terze parti, non trovarselo sparito. La ragione dev'essere una sola e detta
    con le stesse parole nei due documenti.
    """
    if not problema.get("azionabile", True):
        return "non azionabile: le risorse coinvolte non sono sotto controllo"
    if problema.get("fonte") == "lighthouse" and not (problema.get("azioni") or []):
        # Artefatti di dati (script-treemap-data): Lighthouse non allega nessuna
        # raccomandazione, e il titolo tecnico non e' un intervento.
        return "artefatto di dati: Lighthouse non allega una raccomandazione"
    if not intervento_di(problema):
        return "constatazione senza intervento eseguibile"
    return ""


def costruisci(esecuzione: dict):
    """(frammento, esclusi). `esclusi` sono (template, titolo, motivo)."""
    pagine = [p for p in esecuzione.get("pagine", []) if not p.get("errore")]
    totale_template = len(pagine)

    gruppi: dict = {}
    esclusi = []
    for pagina in pagine:
        campo = (pagina.get("campo") or {}).get("metriche") or {}
        for problema in pagina.get("problemi") or []:
            motivo = motivo_esclusione(problema)
            if motivo:
                esclusi.append((pagina.get("template", ""),
                                problema.get("titolo", ""), motivo))
                continue
            gruppi.setdefault(problema["codice"], []).append(
                {"problema": problema, "template": pagina.get("template", ""),
                 "url": pagina.get("url", ""), "campo": campo})

    voci = []
    for codice, membri in gruppi.items():
        # Il punteggio somma i membri: tiene insieme gravita', peso di traffico e
        # quanti template ne sono toccati, che sono le tre cose che decidono
        # l'ordine con cui si mette mano.
        punteggio = sum(_punteggio(m["problema"]) for m in membri)
        peggiore = min(membri, key=lambda m: ORDINE_GRAVITA.get(
            m["problema"].get("gravita", "bassa"), 3))
        etichetta = etichetta_problema(codice)
        voci.append({
            "codice": codice,
            "punteggio": punteggio,
            "gravita": peggiore["problema"].get("gravita", "bassa"),
            "problema": f"{etichetta} su {len(membri)} template su {totale_template}",
            "evidenza": _evidenza(peggiore["problema"], peggiore["campo"]),
            "intervento": intervento_di(peggiore["problema"]),
            "fonte_intervento": fonte_intervento_di(peggiore["problema"]),
            "etichetta": etichetta,
            "membri": membri,
        })

    voci.sort(key=lambda v: (-v["punteggio"], ORDINE_GRAVITA.get(v["gravita"], 3)))

    tab = _costruisci_tab(pagine, voci)
    nomi_tab = {t["nome"] for t in tab}

    masterplan = []
    for indice, voce in enumerate(voci, start=1):
        con_elementi = any(m["problema"].get("elementi") for m in voce["membri"])
        atteso = _nome_tab(voce["codice"], voce["etichetta"], con_elementi)
        masterplan.append({
            "id": indice,
            "problema": voce["problema"],
            "priorita": PRIORITA.get(voce["gravita"], "Bassa"),
            "evidenza": voce["evidenza"],
            "intervento": voce["intervento"],
            "fonte_intervento": voce["fonte_intervento"],
            "tab": atteso if atteso in nomi_tab else "",
        })

    return ({"masterplan": masterplan, "tab": tab}, esclusi)


def _punteggio(problema: dict) -> float:
    valori = {"alta": 3.0, "media": 2.0, "bassa": 1.0}
    return valori.get(problema.get("gravita", "bassa"), 1.0) * float(problema.get("peso", 1.0))


def _costruisci_tab(pagine: list, voci: list) -> list:
    """Un tab si crea solo quando la lista serve a chi implementa.

    Il crawl completo e le liste informative non sono tab: meglio quattro tab
    utili che otto di cui meta' nessuno apre. Da qui il tetto e le due regole —
    una metrica entra solo se almeno un template e' oltre soglia, e le risorse
    solo per gli interventi in cima all'ordine.
    """
    tab = []
    for metrica in ("largest_contentful_paint", "interaction_to_next_paint",
                    "cumulative_layout_shift"):
        voce = _tab_metrica(pagine, metrica)
        if voce:
            tab.append(voce)

    for voce in voci:
        if len(tab) >= MASSIMO_TAB:
            break
        if voce["codice"].startswith("lcp-"):
            continue      # l'LCP ha gia' il suo tab di metrica
        con_elementi = any(m["problema"].get("elementi") for m in voce["membri"])
        nome = _nome_tab(voce["codice"], voce["etichetta"], con_elementi)
        if any(t["nome"] == nome for t in tab):
            continue
        voce_tab = _tab_risorse(nome, voce["membri"])
        if voce_tab:
            tab.append(voce_tab)
    return tab
