"""
Fatti -> problemi classificati.

Regola del modulo: **non si inventa niente**. Ogni riga del report o e' testo di
Lighthouse (titoli, descrizioni, checklist: con `locale=it` arrivano gia' in
italiano), o e' un dato misurato, o e' una classificazione dichiarata che opera
su dati misurati. Nessuna raccomandazione scritta a mano.

Le tre classificazioni che facciamo, e su cosa poggiano:

1. **Chi interviene** — dalla quota di spreco attribuibile a risorse di terze parti.
   Se il 90% dei byte sprecati sta su script altrui, non e' un lavoro da sviluppo.
2. **Quanto e' prioritario** — dal campo, non dal laboratorio. Lighthouse ordina per
   risparmio stimato in lab; noi riordiniamo su cio' che gli utenti reali subiscono.
3. **Se e' azionabile** — un'opportunita' i cui file sono tutti di terze parti e che
   richiede il controllo del server (cache, compressione) non e' un intervento
   possibile: va detto invece di metterlo in lista.

Funzioni pure.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .extract import FASI_IT, FattiPagina
from .soglie import (CWV, ETICHETTE, fasi_dal_campo, formatta,
                     formatta_risparmio, giudizio)

DEV, CMS, INFRA, MARKETING = "sviluppo", "cms/redazione", "infrastruttura", "marketing/tag"
MISTO = "sviluppo + marketing/tag"

# Metriche di laboratorio dichiarate da Lighthouse -> metrica di campo corrispondente.
LAB_A_CAMPO = {
    "LCP": "largest_contentful_paint",
    "FCP": "first_contentful_paint",
    "CLS": "cumulative_layout_shift",
    "INP": "interaction_to_next_paint",
    "TBT": "interaction_to_next_paint",   # proxy: dichiarato in nota
    "SI": "largest_contentful_paint",     # Speed Index: nessun equivalente di campo,
                                          # si calibra sull'LCP e si dichiara in nota
    "TTFB": "experimental_time_to_first_byte",
}

# Metriche di laboratorio senza un corrispondente diretto nel campo: la priorita'
# calcolata su di esse e' un'approssimazione e va detto.
CALIBRAZIONE_APPROSSIMATA = {
    "TBT": "TBT e' il proxy di laboratorio dell'INP: Lighthouse non misura "
           "l'INP, quindi l'attribuzione qui e' meno precisa.",
    "SI": "Lo Speed Index non ha un equivalente nel campo: la priorita' e' "
          "calibrata sull'LCP, che e' la metrica reale piu' vicina.",
}

# Audit il cui rimedio richiede il controllo del server che serve la risorsa.
# Se le risorse sono tutte di terze parti, l'intervento non e' nelle nostre mani.
RICHIEDE_CONTROLLO_SERVER = ("cache", "compression", "server-response", "text-compression")

# --- chi interviene: due regimi distinti, entrambi dichiarati ---------------- #
#
# 1. Per alcuni audit la responsabilita' NON dipende da chi possiede i file. Le
#    immagini sono contenuto: le carica chi pubblica, ovunque siano ospitate. Un
#    elemento che shifta e' markup. La cache la governa chi amministra il server.
# 2. Per tutti gli altri — byte di JavaScript e CSS — decide la proprieta' delle
#    risorse sprecate, che e' un dato misurato.
#
# Dove nessuno dei due regimi si applica, si dichiara invece di indovinare.
RESPONSABILE_FISSO = {
    "server-response": INFRA,
    "cache": INFRA,
    "redirect": INFRA,
    "document-latency": INFRA,
    "third-parties": MARKETING,          # sono terze parti per definizione dell'audit
    "image-delivery": CMS,               # immagini: contenuto, non codice
    "unsized-images": CMS,
    "cls-culprits": DEV,                 # markup e CSS che fanno ballare la pagina
    "layout-shift": DEV,
    "forced-reflow": DEV,
    "dom-size": DEV,
    "non-composited-animations": DEV,
    "viewport": DEV,
    "network-dependency-tree": DEV,
    "mainthread-work": DEV,
}

NON_DEDUCIBILE = "da assegnare"

GRAVITA_DA_CAMPO = {"scarso": "alta", "da_migliorare": "media", "buono": "bassa",
                    "sconosciuto": "media"}


@dataclass
class Problema:
    codice: str
    titolo: str
    gravita: str                     # alta | media | bassa
    responsabile: str
    fonte: str = "lighthouse"        # lighthouse | classificazione
    evidenza: list = field(default_factory=list)
    azioni: list = field(default_factory=list)
    risorse: list = field(default_factory=list)   # (url, misura, terza_parte)
    elementi: list = field(default_factory=list)  # (riferimento, misura, percorso, snippet)
    documentazione: str = ""
    nota: str = ""
    azionabile: bool = True
    risparmio: float = 0.0


# --------------------------------------------------------------------------- #
#  Classificazioni
# --------------------------------------------------------------------------- #

def responsabile_per(opportunita) -> str:
    """Chi mette mano.

    Prima la natura dell'audit, quando determina la responsabilita' a prescindere
    da dove sono ospitati i file; poi la proprieta' delle risorse sprecate, che e'
    un dato misurato. Se non si applica nessuno dei due, si dichiara `da assegnare`
    invece di attribuire il lavoro a intuito.
    """
    for frammento, fisso in RESPONSABILE_FISSO.items():
        if frammento in opportunita.audit:
            return fisso
    if not opportunita.risorse:
        return NON_DEDUCIBILE
    quota = opportunita.quota_terze_parti
    if quota >= 0.7:
        return MARKETING
    if quota <= 0.25:
        return DEV
    return MISTO


def azionabile(opportunita) -> bool:
    """Falso quando il rimedio richiede il controllo di server che non sono nostri."""
    tocca_server = any(f in opportunita.audit for f in RICHIEDE_CONTROLLO_SERVER)
    return not (tocca_server and opportunita.quota_terze_parti >= 0.95)


# Metrica su cui calibrare la priorita' degli audit che NON dichiarano risparmi.
# Senza questa mappa `cls-culprits-insight` — che nomina gli elementi che fanno
# ballare la pagina — resterebbe a priorita' fissa "media" invece di seguire il
# CLS reale degli utenti.
METRICA_PER_AUDIT = {
    "cls-culprits": "CLS", "layout-shift": "CLS", "unsized-images": "CLS",
    "forced-reflow": "TBT", "third-parties": "TBT", "mainthread-work": "TBT",
    "script-treemap": "LCP", "network-dependency-tree": "LCP",
    "image-delivery": "LCP", "document-latency": "TTFB",
}

ORDINE_GIUDIZIO = {"scarso": 0, "da_migliorare": 1, "buono": 2, "sconosciuto": 3}


def priorita_dal_campo(opportunita, campo: dict):
    """(gravita, spiegazione). La priorita' viene dal campo, non dal laboratorio."""
    verdetti = []
    for metrica_lab in opportunita.risparmi:
        chiave = LAB_A_CAMPO.get(metrica_lab)
        if chiave and chiave in campo:
            verdetti.append((giudizio(chiave, campo[chiave]), chiave, metrica_lab))

    dichiarato = bool(verdetti)
    if not verdetti:
        # Nessun risparmio dichiarato: si usa la metrica di cui l'audit si occupa.
        metrica_lab = next((m for frammento, m in METRICA_PER_AUDIT.items()
                            if frammento in opportunita.audit), None)
        chiave = LAB_A_CAMPO.get(metrica_lab or "")
        if chiave and chiave in campo:
            verdetti = [(giudizio(chiave, campo[chiave]), chiave, metrica_lab)]

    if not verdetti:
        return ("media", "Priorita' non calibrata sul campo: per questo URL mancano "
                         "i dati CrUX sulle metriche interessate.")

    peggiore, chiave, metrica_lab = min(verdetti, key=lambda v: ORDINE_GIUDIZIO[v[0]])
    if dichiarato:
        stima = formatta_risparmio(metrica_lab, opportunita.risparmi[metrica_lab])
        nota = (f"Lighthouse stima {stima} di risparmio su {metrica_lab}; "
                f"il campo dice {ETICHETTE[chiave]} {formatta(chiave, campo[chiave])} "
                f"({peggiore.replace('_', ' ')}).")
    else:
        nota = (f"Lighthouse non dichiara un risparmio per questo audit: la priorita' "
                f"segue la metrica di cui si occupa, {metrica_lab}, che nel campo vale "
                f"{formatta(chiave, campo[chiave])} ({peggiore.replace('_', ' ')}).")
    if metrica_lab in CALIBRAZIONE_APPROSSIMATA:
        nota += " " + CALIBRAZIONE_APPROSSIMATA[metrica_lab]
    if peggiore == "buono":
        nota += " Per gli utenti reali questa metrica e' gia' a posto: priorita' bassa."
    return (GRAVITA_DA_CAMPO[peggiore], nota)


# --------------------------------------------------------------------------- #
#  Opportunita' di Lighthouse -> problemi
# --------------------------------------------------------------------------- #

def _misura(risorsa) -> str:
    if risorsa.ms_sprecati:
        return f"{risorsa.ms_sprecati:.0f} ms"
    if risorsa.byte_sprecati:
        quota = f" ({risorsa.quota_sprecata:.0f}% del file)" if risorsa.quota_sprecata else ""
        return f"{risorsa.byte_sprecati / 1024:.0f} KB{quota}"
    return ""


def _misura_voce(voce) -> str:
    """Le misure di una riga senza URL, ciascuna con la sua unita'."""
    parti = []
    for chiave, valore in voce.misure.items():
        if chiave in ("transferSize", "wastedBytes", "totalBytes",
                      "resourceBytes", "unusedBytes"):
            parti.append(f"{valore / 1024:.0f} KB")
        elif chiave == "score":
            parti.append(f"{valore:.3f}")
        else:
            parti.append(f"{valore:.0f} ms")
    return " · ".join(parti)


def _misura_elemento(elemento) -> str:
    if not elemento.misura:
        return ""
    if elemento.unita == "":
        return f"{elemento.misura:.3f}"
    if elemento.unita == "byte":
        return f"{elemento.misura / 1024:.0f} KB"
    return f"{elemento.misura:.0f} ms"


def da_opportunita(opportunita, campo: dict, massimo_risorse: int = 6) -> Problema:
    gravita, spiegazione = priorita_dal_campo(opportunita, campo)
    puo_agire = azionabile(opportunita)

    evidenza = []
    if opportunita.display:
        evidenza.append(opportunita.display)
    if opportunita.risparmi:
        evidenza.append("Stima Lighthouse: " + ", ".join(
            f"{m} {formatta_risparmio(m, v)}" for m, v in opportunita.risparmi.items()))
    if opportunita.risorse:
        quota = opportunita.quota_terze_parti
        evidenza.append(f"{quota * 100:.0f}% dello spreco e' su risorse di terze parti")
    # Le voci sono righe che non nominano ne' un file ne' un nodo: un vendor con il
    # suo costo di main thread, una categoria di lavoro, l'origine di un reflow.
    for voce in opportunita.voci[:massimo_risorse]:
        misura = _misura_voce(voce)
        if misura:
            evidenza.append(f"{voce.etichetta}: {misura}")
    # I motivi sono testo di Lighthouse, uno per tipo: si riportano una volta sola.
    for motivo in dict.fromkeys(r.motivo for r in opportunita.risorse if r.motivo):
        evidenza.append(motivo)

    # Le voci fallite di una checklist sono gia' istruzioni scritte da Lighthouse.
    azioni = [opportunita.descrizione] if opportunita.descrizione else []
    azioni += [etichetta for _nome, (superato, etichetta)
               in opportunita.controlli.items() if not superato]

    nota = spiegazione
    if not opportunita.descrizione:
        # Alcuni artefatti (script-treemap-data) non hanno un testo di
        # raccomandazione: sono dati grezzi. Dichiararlo evita che il titolo
        # tecnico di Lighthouse sembri un intervento mal scritto.
        nota += (" Lighthouse non allega una raccomandazione a questo audit: sono "
                 "dati di misura, riportati qui perche' nominano i file o gli "
                 "elementi su cui intervenire.")
    if not puo_agire:
        nota += (" Tutte le risorse coinvolte sono di terze parti: l'intervento non e' "
                 "nelle vostre mani se non rimuovendo o sostituendo quegli script.")
    if responsabile_per(opportunita) == NON_DEDUCIBILE:
        nota += (" Chi debba intervenire non e' deducibile: l'audit non nomina risorse "
                 "di cui si possa stabilire la proprieta'.")

    return Problema(
        codice=opportunita.audit,
        titolo=opportunita.titolo,
        gravita=gravita if puo_agire else "bassa",
        responsabile=responsabile_per(opportunita),
        fonte="lighthouse",
        evidenza=evidenza,
        azioni=azioni,
        risorse=[(r.url, _misura(r), r.terza_parte)
                 for r in opportunita.risorse[:massimo_risorse] if _misura(r)],
        elementi=[(e.riferimento, _misura_elemento(e), e.percorso, e.snippet[:160])
                  for e in opportunita.elementi[:massimo_risorse]],
        documentazione=opportunita.documentazione,
        nota=nota,
        azionabile=puo_agire,
        risparmio=opportunita.peso_relativo,
    )


# --------------------------------------------------------------------------- #
#  Classificazioni nostre: la fase LCP e il peso delle terze parti
# --------------------------------------------------------------------------- #

# Cosa significa ogni fase, e chi la governa. Non contiene rimedi: quelli
# arrivano dalle opportunita' di Lighthouse.
SIGNIFICATO_FASI = {
    "timeToFirstByte": ("Il tempo si perde sul server, prima che il browser riceva "
                        "l'HTML", INFRA),
    "resourceLoadDelay": ("Il browser scopre la risorsa LCP tardi: il tempo si perde "
                          "prima ancora che il download inizi", DEV),
    "resourceLoadDuration": ("Il tempo se ne va nel download della risorsa LCP", CMS),
    "elementRenderDelay": ("La risorsa e' scaricata ma il rendering resta bloccato", DEV),
}


def classifica_lcp(fatti: FattiPagina, campo: dict, accordo=None) -> Problema | None:
    """Dove si perde il tempo dell'LCP, e chi se ne occupa.

    La ripartizione si prende **dal campo** quando c'e' (ADR-005): CrUX la espone
    sugli utenti reali, stabile e con lo storico. Il breakdown di laboratorio e' il
    ripiego, e va usato sapendo che oscilla — sulla stessa pagina e' stato visto
    passare da 260 a 3.118 ms sulla stessa fase.

    Le voci della checklist di Lighthouse (`lcp-discovery-insight`) vengono
    riportate testuali: sono gia' istruzioni, e gia' in italiano.
    """
    fasi_campo = fasi_dal_campo(campo)
    dal_campo = bool(fasi_campo)
    fasi = fasi_campo or fatti.lcp_fasi
    if not fasi:
        return None

    totale = sum(fasi.values()) or 1
    fase = max(fasi, key=fasi.get)
    quota = fasi[fase] / totale
    significato, responsabile = SIGNIFICATO_FASI[fase]

    origine = "utenti reali" if dal_campo else "laboratorio"
    evidenza = [
        f"Fase dominante ({origine}): {FASI_IT[fase]} — {quota * 100:.0f}% del tempo LCP",
        "Ripartizione: " + ", ".join(f"{FASI_IT[k]} {v / totale * 100:.0f}%"
                                     for k, v in fasi.items()),
    ]
    if fatti.lcp_elemento_snippet:
        evidenza.append(f"Elemento LCP: {fatti.lcp_elemento_snippet[:160]}")

    # Le voci fallite della checklist sono le istruzioni di Lighthouse, verbatim.
    azioni = [etichetta for chiave, etichetta in fatti.lcp_discovery_label.items()
              if fatti.lcp_discovery.get(chiave) is False]

    lcp_campo = campo.get("largest_contentful_paint")
    if lcp_campo is not None:
        evidenza.append(f"LCP di campo (p75 utenti reali): "
                        f"{formatta('largest_contentful_paint', lcp_campo)} — "
                        f"{giudizio('largest_contentful_paint', lcp_campo).replace('_', ' ')}")

    if dal_campo:
        nota = ("Ripartizione presa dai dati di campo CrUX: sono gli utenti reali su "
                "28 giorni, non una simulazione. I quattro valori sono percentili "
                "indipendenti, quindi non sommano esattamente all'LCP complessivo. "
                "Le voci sopra sono la checklist di Lighthouse riportata testualmente.")
        incerto = False
    else:
        nota = ("Ripartizione dal laboratorio: CrUX non espone le fasi per questa pagina "
                "(le fornisce solo quando l'elemento LCP e' un'immagine e il traffico "
                "basta). Sono proporzioni sul trace osservato, non sommano alla metrica "
                "LCP riportata, e variano fra una misurazione e l'altra. "
                "Le voci sopra sono la checklist di Lighthouse riportata testualmente.")
        if accordo is not None:
            nota += " " + accordo.descrizione
            if not accordo.checklist_stabile:
                nota += (" Attenzione: la checklist non e' identica fra le misurazioni, "
                         "cosa che di norma non accade.")
        # Senza accordo fra le misurazioni la fase dominante non regge, e con essa
        # l'attribuzione della responsabilita': lo dichiariamo invece di nasconderlo.
        incerto = accordo is not None and not accordo.attendibile

    return Problema(
        codice=f"lcp-{fase}",
        titolo=significato + (" [misurazioni discordanti]" if incerto else ""),
        gravita=GRAVITA_DA_CAMPO[giudizio("largest_contentful_paint", lcp_campo)],
        responsabile=f"{responsabile} (da confermare)" if incerto else responsabile,
        fonte="campo" if dal_campo else "classificazione",
        evidenza=evidenza,
        azioni=azioni,
        nota=nota,
    )


def constatazione_terze_parti(riepilogo, soglia: float = 0.40) -> Problema | None:
    """Solo il dato. I rimedi stanno nelle opportunita' di Lighthouse, non qui."""
    if not riepilogo.byte_totali or riepilogo.quota_terzi < soglia:
        return None
    return Problema(
        codice="peso-terze-parti",
        titolo="Composizione del peso della pagina",
        gravita="bassa",
        responsabile=MARKETING,
        fonte="classificazione",
        evidenza=[
            f"Peso totale: {riepilogo.byte_totali / 1024:.0f} KB su "
            f"{riepilogo.richieste_totali} richieste",
            f"Terze parti: {riepilogo.byte_terzi / 1024:.0f} KB "
            f"({riepilogo.quota_terzi * 100:.0f}%)",
        ],
        risorse=[(e.host, f"{e.kb:.0f} KB ({e.richieste} richiest" + ("a" if e.richieste == 1 else "e") + ")", e.terza_parte)
                 for e in riepilogo.top(8)],
        nota=("Ricostruito raggruppando network-requests per host: l'audit "
              "third-parties-insight di Lighthouse non riporta questo dato. "
              "E' una constatazione, non un intervento: gli interventi sono negli "
              "audit qui sopra."),
    )


# --------------------------------------------------------------------------- #
#  Composizione
# --------------------------------------------------------------------------- #

ORDINE_GRAVITA = {"alta": 0, "media": 1, "bassa": 2}


def diagnostica(fatti: FattiPagina, campo: dict | None = None, riepilogo=None,
                accordo=None) -> list:
    """Lista di problemi ordinata: prima cio' che il campo dice davvero rotto.

    `accordo` e' il Consenso fra le ripetizioni della misurazione lab: serve a
    dichiarare quanto e' affidabile la fase LCP dominante.
    """
    campo = campo or {}
    problemi = []

    lcp = classifica_lcp(fatti, campo, accordo)
    if lcp:
        problemi.append(lcp)

    problemi += [da_opportunita(o, campo) for o in fatti.opportunita]

    if riepilogo is not None:
        terze = constatazione_terze_parti(riepilogo)
        if terze:
            problemi.append(terze)

    # A parita' di gravita': prima cio' che e' azionabile, poi il risparmio piu' alto.
    problemi.sort(key=lambda p: (ORDINE_GRAVITA.get(p.gravita, 3), not p.azionabile,
                                 -p.risparmio))
    return problemi


def riepilogo_campo(campo: dict) -> list:
    righe = []
    for metrica in CWV + ("first_contentful_paint", "experimental_time_to_first_byte"):
        if metrica in campo:
            righe.append({
                "metrica": ETICHETTE[metrica],
                "chiave": metrica,
                "valore": campo[metrica],
                "giudizio": giudizio(metrica, campo[metrica]),
            })
    return righe
