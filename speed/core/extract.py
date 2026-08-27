"""
JSON PageSpeed Insights -> fatti tipizzati.

Le chiavi degli audit sono fissate su risposte REALI (Lighthouse 13.x, agosto 2026),
non sulla documentazione: Lighthouse 13 ha sostituito i vecchi audit diagnostici
(`largest-contentful-paint-element`, `third-party-summary`) con gli "Insights".
Se Lighthouse cambia ancora, i test su fixtures/ falliscono qui, che e' il punto giusto.

Funzioni pure: nessuna rete, nessun filesystem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

FASI_LCP = ("timeToFirstByte", "resourceLoadDelay", "resourceLoadDuration", "elementRenderDelay")

FASI_IT = {
    "timeToFirstByte": "Risposta del server (TTFB)",
    "resourceLoadDelay": "Attesa prima del download",
    "resourceLoadDuration": "Download della risorsa",
    "elementRenderDelay": "Rendering dell'elemento",
}


@dataclass
class Richiesta:
    url: str
    host: str
    byte: int
    tipo: str
    entita: str = ""      # nome del provider secondo Lighthouse, quando lo riconosce
    stato: int = 0        # statusCode: 206 su piu' richieste dello stesso file dice
                          # che una risorsa e' servita a pezzi, ed e' un fatto che
                          # nessun audit riporta


@dataclass
class FattiPagina:
    url: str
    form_factor: str
    lighthouse_version: str = ""
    benchmark_index: float = 0.0
    timestamp: str = ""          # analysisUTCTimestamp: identifica la misurazione
    performance_score: float | None = None
    lcp_elemento_selettore: str = ""
    lcp_elemento_snippet: str = ""
    lcp_fasi: dict = field(default_factory=dict)
    lcp_discovery: dict = field(default_factory=dict)
    lcp_discovery_label: dict = field(default_factory=dict)
    opportunita: list = field(default_factory=list)
    richieste: list = field(default_factory=list)
    metriche_lab: dict = field(default_factory=dict)
    campo_psi: dict = field(default_factory=dict)
    campo_psi_origin_fallback: bool = False

    @property
    def lcp_fase_dominante(self):
        """Ritorna (fase, quota 0-1).

        ATTENZIONE: le durate delle fasi NON sono confrontabili con la metrica LCP
        riportata da Lighthouse. Il breakdown e' sul trace osservato, la metrica e'
        simulata con throttling: sulla homepage di prova le fasi sommavano 3,4 s
        contro un LCP dichiarato di 10,9 s. Vanno lette come PROPORZIONI.
        """
        if not self.lcp_fasi:
            return ("", 0.0)
        totale = sum(self.lcp_fasi.values()) or 1.0
        fase = max(self.lcp_fasi, key=self.lcp_fasi.get)
        return (fase, self.lcp_fasi[fase] / totale)


def _audits(psi: dict) -> dict:
    return psi.get("lighthouseResult", {}).get("audits", {})


def _righe_tabella(audit: dict) -> list:
    """Righe di tutte le sotto-tabelle di un audit insight."""
    righe = []
    for item in audit.get("details", {}).get("items", []):
        if isinstance(item, dict) and item.get("type") == "table":
            righe += item.get("items", [])
    return righe


def estrai_fasi_lcp(psi: dict) -> dict:
    fasi = {}
    for riga in _righe_tabella(_audits(psi).get("lcp-breakdown-insight", {})):
        sub = riga.get("subpart")
        if sub in FASI_LCP:
            fasi[sub] = float(riga.get("duration") or 0.0)
    return fasi


def estrai_elemento_lcp(psi: dict):
    audit = _audits(psi).get("lcp-breakdown-insight", {})
    for item in audit.get("details", {}).get("items", []):
        if isinstance(item, dict) and item.get("type") == "node":
            return (item.get("selector", ""), item.get("snippet", ""))
    return ("", "")


def estrai_discovery(psi: dict):
    """Checklist di scopribilita' della risorsa LCP: lazy, fetchpriority, discoverable."""
    valori, etichette = {}, {}
    audit = _audits(psi).get("lcp-discovery-insight", {})
    for item in audit.get("details", {}).get("items", []):
        if isinstance(item, dict) and item.get("type") == "checklist":
            for nome, chk in (item.get("items") or {}).items():
                valori[nome] = bool(chk.get("value"))
                etichette[nome] = chk.get("label", nome)
    return valori, etichette


# --------------------------------------------------------------------------- #
#  Opportunita': il testo delle raccomandazioni viene da Lighthouse, non da noi.
#  Con locale=it arriva gia' in italiano, con il link alla documentazione Google.
# --------------------------------------------------------------------------- #

@dataclass
class Risorsa:
    url: str
    byte_totali: int = 0
    byte_sprecati: int = 0
    ms_sprecati: float = 0.0
    quota_sprecata: float = 0.0
    terza_parte: bool = False
    motivo: str = ""      # testo di Lighthouse sul perche' (es. image-delivery)
    # Nome dichiarato da noi quando la riga non porta un URL ma un blocco di
    # codice inline. Vuoto per tutte le risorse che un file ce l'hanno.
    etichetta: str = ""

    @property
    def spreco(self) -> float:
        """Metrica unica per ordinare: ms se ci sono, altrimenti byte."""
        return self.ms_sprecati or self.byte_sprecati

    @property
    def nome(self) -> str:
        """Come si nomina in una lista corta: il file, o l'etichetta se e' inline."""
        return self.etichetta or self.url.split("?")[0].rsplit("/", 1)[-1] or self.url

    @property
    def riferimento(self) -> str:
        """Come si nomina in una tabella di risorse.

        Per un file e' l'URL. Per un blocco inline e' l'etichetta con l'estratto
        che Lighthouse mette al posto dell'indirizzo: senza l'estratto la riga
        direbbe "CSS inline" e basta, e il blocco resterebbe da cercare a mano.
        """
        return f"{self.etichetta}: {self.url}" if self.etichetta else self.url


@dataclass
class Elemento:
    """Un nodo del DOM che Lighthouse indica come responsabile.

    Selettore, snippet e percorso sono la prima cosa che cerca chi deve mettere
    mano al codice, quindi restano campi distinti e non una stringa da riparsare.
    Senza di loro un audit sul CLS dice che la pagina balla ma non quale elemento.
    """
    selettore: str = ""
    snippet: str = ""
    percorso: str = ""      # path DOM: "1,HTML,1,BODY,0,DIV,..."
    etichetta: str = ""     # nodeLabel: il testo visibile, utile a riconoscerlo
    misura: float = 0.0
    unita: str = ""         # dichiarata dall'audit, non dedotta

    @property
    def riferimento(self) -> str:
        """Come lo si nomina in un report: il selettore se c'e', altrimenti il DOM."""
        return self.selettore or self.etichetta or self.snippet[:80] or self.percorso


@dataclass
class Voce:
    """Riga che non nomina ne' un URL ne' un nodo: un vendor, una sorgente di reflow.

    E' il caso di `third-parties-insight`, dove la riga e' un'entita' con il suo
    costo di main thread: informazione che non ha altro posto dove stare.
    """
    etichetta: str
    misure: dict = field(default_factory=dict)


@dataclass
class Opportunita:
    audit: str
    titolo: str            # testo di Lighthouse
    descrizione: str       # testo di Lighthouse, senza il link markdown
    documentazione: str    # URL estratto dalla descrizione
    display: str           # es. "Risparmio stimato di 508 KiB"
    score: float | None
    risparmi: dict         # metricSavings: {LCP: ms, FCP: ms, TBT: ms, CLS: adimensionale}
    # Etichetta del link nella descrizione: Lighthouse ci mette l'imperativo dove
    # il titolo e' un sostantivo ("Terze parti" -> "Riduci e posticipa il
    # caricamento del codice di terze parti").
    etichetta_azione: str = ""
    risorse: list = field(default_factory=list)
    elementi: list = field(default_factory=list)
    voci: list = field(default_factory=list)
    controlli: dict = field(default_factory=dict)      # nome -> (superato, etichetta)

    @property
    def risparmio_massimo(self) -> float:
        return max(self.risparmi.values()) if self.risparmi else 0.0

    @property
    def peso_relativo(self) -> float:
        """Risparmio normalizzato sulla soglia della sua metrica.

        Ordinare per valore grezzo confronterebbe 0,095 di CLS con 600 ms di TBT
        e metterebbe ogni intervento sul CLS in fondo per pura questione di scala.
        Normalizzando su cio' che Google considera accettabile, i due diventano
        confrontabili: 0,095/0,10 = 0,95 contro 600/200 = 3,0.
        """
        from .soglie import SOGLIA_BUONA_LAB
        pesi = [valore / SOGLIA_BUONA_LAB[metrica]
                for metrica, valore in self.risparmi.items()
                if metrica in SOGLIA_BUONA_LAB and SOGLIA_BUONA_LAB[metrica]]
        return max(pesi) if pesi else 0.0

    @property
    def ha_contenuto(self) -> bool:
        return bool(self.risorse or self.elementi or self.voci or self.controlli)

    @property
    def quota_terze_parti(self) -> float:
        """Quota dello spreco attribuibile a risorse di terze parti.
        Serve a stabilire chi deve intervenire, sul dato invece che a intuito."""
        totale = sum(r.spreco for r in self.risorse)
        if not totale:
            return 0.0
        return sum(r.spreco for r in self.risorse if r.terza_parte) / totale


_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def etichetta_documentazione(testo: str) -> str:
    """L'etichetta del primo link markdown nella descrizione.

    Serve perche' alcuni insight hanno un titolo descrittivo — "Terze parti",
    "Albero delle dipendenze di rete" — mentre l'etichetta del link porta l'azione
    all'imperativo: "Riduci e posticipa il caricamento del codice di terze parti".
    E' testo di Lighthouse in entrambi i casi: si sceglie quale, non si riscrive.
    """
    trovato = _LINK.search(testo or "")
    return trovato.group(1) if trovato else ""


def _scomponi_descrizione(testo: str):
    """Lighthouse inserisce link markdown anche in mezzo alla frase.

    Il link va sostituito con la sua etichetta, non rimosso: togliere tutto
    mutilava frasi come "impostare [font-display](...) su swap".
    """
    link = _LINK.search(testo or "")
    pulito = _LINK.sub(lambda c: c.group(1), testo or "").strip()
    return (pulito, link.group(2) if link else "")


# --------------------------------------------------------------------------- #
#  Lettori per forma di `details`.
#
#  Lighthouse 13 incapsula le stesse informazioni in quattro modi diversi, e
#  leggerne uno solo — come faceva la versione precedente, che cercava chiavi
#  `url` scendendo di due livelli — butta via il materiale piu' utile: gli
#  elementi che shiftano nel CLS, il costo di main thread per vendor, l'origine
#  di un reflow forzato.
# --------------------------------------------------------------------------- #

# Chiavi numeriche che Lighthouse usa nelle righe, con l'unita' che gli compete.
MISURE_NOTE = {
    "wastedMs": "ms", "duration": "ms", "mainThreadTime": "ms", "blockingTime": "ms",
    "reflowTime": "ms", "navStartToEndTime": "ms",
    # bootup-time misura il costo CPU per script con chiavi tutte sue.
    "total": "ms", "scripting": "ms", "scriptParseCompile": "ms",
    "transferSize": "byte", "wastedBytes": "byte",
    "totalBytes": "byte", "resourceBytes": "byte", "unusedBytes": "byte",
    "score": "",        # CLS: adimensionale
}

# Etichette possibili per una riga che non nomina un URL.
ETICHETTE_RIGA = ("entity", "source", "origin", "name", "label", "groupLabel")

# Audit dove la cella `url` puo' portare un blocco di codice inline invece di un
# indirizzo: Lighthouse ci mette l'estratto del `<style>` o dello `<script>`.
#
# Senza queste etichette la riga non produceva nulla — `_classifica_riga` chiede
# un url che cominci per http, non c'e' un `node`, e `url` non e' fra
# ETICHETTE_RIGA — quindi `ha_contenuto` era falso e l'audit intero spariva dal
# report. Sul fixture BBC `unminified-css` ha score 0,5 e "Risparmio stimato di
# 2 KiB" e non compariva da nessuna parte, nemmeno fra i "fuori master plan".
#
# L'etichetta e' una classificazione nostra (ADR-004, terza origine), dichiarata
# nella nota del problema. Il numero e l'estratto restano di Lighthouse. Sono
# elencati per audit e non dedotti da "l'url non e' un url": su `bootup-time` la
# stessa cella porta "Unattributable", che e' lavoro non attribuito, non un
# blocco inline, e chiamarlo "script inline" sarebbe un'informazione inventata.
ETICHETTA_INLINE = {
    "unminified-css": "CSS inline",
    "unminified-javascript": "script inline",
    "unused-css-rules": "CSS inline",
    "render-blocking-resources": "risorsa inline",
    "render-blocking-insight": "risorsa inline",
}


def _tabelle(audit: dict):
    """Ogni tabella dell'audit, ovunque sia annidata.

    I tre incapsulamenti visti su risposte reali:
      details.type == "table" | "opportunity"  -> righe in details.items
      details.type == "list"   con items di type table
      details.type == "list"   con items list-section il cui `value` e' una table
    """
    dettagli = audit.get("details") or {}
    if dettagli.get("type") in ("table", "opportunity"):
        yield dettagli.get("items") or []
    for item in dettagli.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "table":
            yield item.get("items") or []
        valore = item.get("value")
        if isinstance(valore, dict) and valore.get("type") == "table":
            yield valore.get("items") or []


def _sotto_righe(riga: dict) -> list:
    """`subItems` e' un dict con dentro `items`, non una lista: e' li' che
    `third-parties-insight` tiene il dettaglio per singolo file."""
    sotto = riga.get("subItems")
    if isinstance(sotto, dict):
        return sotto.get("items") or []
    return sotto if isinstance(sotto, list) else []


def _testo(valore) -> str:
    """Una cella puo' essere una stringa o un dict {type: text, value: ...}."""
    if isinstance(valore, str):
        return valore
    if isinstance(valore, dict):
        v = valore.get("text") or valore.get("value")
        return v if isinstance(v, str) else ""
    return ""


def leggi_nodo(valore) -> "Elemento | None":
    """Un `node` di Lighthouse -> Elemento, o None se non e' un nodo del DOM.

    Le tabelle del CLS aprono con una riga di totale il cui `node` e'
    `{type: text, value: "Totale"}`: e' un riepilogo, non un elemento, e va
    scartato o finirebbe nel report come se fosse un selettore.
    """
    if not isinstance(valore, dict) or valore.get("type") == "text":
        return None
    if not any(valore.get(k) for k in ("selector", "snippet", "path")):
        return None
    return Elemento(
        selettore=str(valore.get("selector") or ""),
        snippet=str(valore.get("snippet") or ""),
        percorso=str(valore.get("path") or ""),
        etichetta=str(valore.get("nodeLabel") or ""),
    )


def leggi_checklist(audit: dict) -> dict:
    """Ogni checklist dell'audit -> {nome: (superato, etichetta)}.

    Generalizzata da `lcp-discovery-insight`: la forma e' la stessa ovunque, e le
    etichette sono gia' istruzioni in italiano scritte da Lighthouse.
    """
    out = {}
    for item in (audit.get("details") or {}).get("items") or []:
        if isinstance(item, dict) and item.get("type") == "checklist":
            for nome, controllo in (item.get("items") or {}).items():
                out[nome] = (bool(controllo.get("value")), controllo.get("label", nome))
    return out


def leggi_treemap(audit: dict) -> list:
    """`script-treemap-data` -> una Risorsa per file sorgente.

    Si leggono solo i nodi radice: ognuno e' un file servito, che e' la
    granularita' su cui si interviene. I figli sono i moduli interni del bundle
    e sarebbero centinaia di righe che nessuno puo' cancellare singolarmente.
    """
    nodi = (audit.get("details") or {}).get("nodes") or []
    out = []
    for nodo in nodi:
        if not isinstance(nodo, dict):
            continue
        nome = str(nodo.get("name") or "")
        if not nome:
            continue
        out.append(Risorsa(
            url=nome,
            byte_totali=int(nodo.get("resourceBytes") or 0),
            byte_sprecati=int(nodo.get("unusedBytes") or 0),
        ))
    return out


def leggi_catena_rete(audit: dict) -> list:
    """`network-dependency-tree-insight` -> le richieste della catena critica.

    La catena non e' una tabella: e' un albero di nodi indicizzati per hash, con
    i figli in un altro dizionario. Nessuno dei lettori per tabella la raggiunge,
    ed e' il motivo per cui l'audit risultava senza contenuto pur essendo fallito.

    Si restituisce come sequenza di voci perche' l'ordine e' l'informazione: sono
    richieste che si aspettano l'una con l'altra prima che la pagina possa dipingere.
    """
    voci = []

    def scendi(nodi: dict, profondita: int = 0):
        for nodo in (nodi or {}).values():
            if not isinstance(nodo, dict):
                continue
            url = nodo.get("url")
            if isinstance(url, str) and url:
                misure = {chiave: float(nodo[chiave])
                          for chiave in ("navStartToEndTime", "transferSize")
                          if isinstance(nodo.get(chiave), (int, float))}
                if misure:
                    voci.append(Voce(etichetta=("  " * profondita) + url, misure=misure))
            scendi(nodo.get("children"), profondita + 1)

    for item in (audit.get("details") or {}).get("items") or []:
        valore = item.get("value") if isinstance(item, dict) else None
        if isinstance(valore, dict) and valore.get("type") == "network-tree":
            scendi(valore.get("chains"))
    return voci


def _classifica_riga(riga: dict, propri: set, e_prima_parte, audit: str = "") -> tuple:
    """Una riga -> (Risorsa | None, Elemento | None, Voce | None).

    Una riga puo' dare piu' cose insieme: `image-delivery-insight` porta URL e
    nodo nella stessa riga, e servono entrambi — l'uno per il peso, l'altro per
    trovare l'immagine nel markup.
    """
    risorsa = elemento = voce = None

    url = riga.get("url")
    inline = "" if not isinstance(url, str) or url.startswith("http")         else ETICHETTA_INLINE.get(audit, "")
    if isinstance(url, str) and (url.startswith("http") or inline):
        motivi = [_testo(s.get("reason")) for s in _sotto_righe(riga) if s.get("reason")]
        risorsa = Risorsa(
            url=url,
            byte_totali=int(riga.get("totalBytes") or riga.get("transferSize") or 0),
            byte_sprecati=int(riga.get("wastedBytes") or 0),
            # `total` e' la chiave di bootup-time: il costo CPU per script. Senza,
            # quell'intervento nominava i file senza dire quanto costano.
            ms_sprecati=float(riga.get("wastedMs") or riga.get("duration")
                              or riga.get("mainThreadTime") or riga.get("total") or 0.0),
            quota_sprecata=float(riga.get("wastedPercent") or 0.0),
            # Un blocco inline sta nel documento: la proprieta' non e' da dedurre
            # dal dominio, e' prima parte per costruzione.
            terza_parte=(not inline and bool(propri)
                         and not e_prima_parte(urlparse(url).netloc, propri)),
            motivo=motivi[0] if motivi else "",
            etichetta=inline,
        )

    elemento = leggi_nodo(riga.get("node"))
    if elemento is not None:
        for chiave, unita in MISURE_NOTE.items():
            if isinstance(riga.get(chiave), (int, float)):
                elemento.misura = float(riga[chiave])
                elemento.unita = unita
                break

    if risorsa is None and elemento is None:
        etichetta = next((_testo(riga.get(k)) for k in ETICHETTE_RIGA if riga.get(k)), "")
        misure = {k: float(v) for k, v in riga.items()
                  if k in MISURE_NOTE and isinstance(v, (int, float))}
        if etichetta and misure:
            voce = Voce(etichetta=etichetta, misure=misure)

    return (risorsa, elemento, voce)


# Insight senza esito negativo ne' risparmio dichiarato, ma con il materiale piu'
# concreto della risposta. Ammessi per nome: senza, due Core Web Vitals su tre
# resterebbero senza diagnosi.
# Artefatti di dati, non audit con una raccomandazione. La loro `description` e'
# una nota interna di Lighthouse non localizzata ("Used for treemap app"): riportarla
# come azione nel report al cliente sarebbe fedele ma incomprensibile.
ARTEFATTI_DATI = frozenset({"script-treemap-data"})

INSIGHT_INFORMATIVI = frozenset({
    "cls-culprits-insight",             # gli elementi che fanno ballare la pagina
    "third-parties-insight",            # costo di main thread per vendor
    "script-treemap-data",              # byte inutilizzati per file sorgente
    "forced-reflow-insight",            # origine del reflow forzato
    "network-dependency-tree-insight",  # catena critica delle richieste
})


# Audit gia' consumati altrove: la fase LCP e la checklist di scopribilita' sono
# il materiale di `classifica_lcp`. Ammetterli qui li farebbe comparire due volte
# nello stesso report, con la seconda copia priva del contesto sul campo.
GIA_CONSUMATI = frozenset({"lcp-breakdown-insight", "lcp-discovery-insight"})

# Gli audit che riportano il VALORE di una metrica di laboratorio. Non sono
# interventi — non nominano niente su cui mettere le mani — e restano fuori dalla
# lista dei problemi, ma il numero serve: e' il quadro di sintesi che si mette in
# testa a una nota tecnica, ed e' l'unico ordinamento possibile su un ambiente
# senza dati di campo (staging). Si estraggono a parte, non si promuovono a
# problemi.
METRICHE_LAB = {
    "first-contentful-paint": "FCP",
    "largest-contentful-paint": "LCP",
    "speed-index": "SI",
    "total-blocking-time": "TBT",
    "interactive": "TTI",
    "cumulative-layout-shift": "CLS",
    "max-potential-fid": "FID max",
    "server-response-time": "TTFB",
    "total-byte-weight": "Peso",
}


def estrai_metriche_lab(psi: dict) -> dict:
    """{sigla: valore numerico} dagli audit che riportano solo una misura.

    `numericValue` e non `displayValue`: il secondo e' gia' formattato ("1,7 s")
    e non si puo' confrontare con una soglia.
    """
    fuori = {}
    for aid, sigla in METRICHE_LAB.items():
        valore = (_audits(psi).get(aid) or {}).get("numericValue")
        if isinstance(valore, (int, float)):
            fuori[sigla] = float(valore)
    return fuori


# Audit che riportano il valore di una metrica invece di un intervento:
# `largest-contentful-paint`, `speed-index`, `interactive`... Hanno un punteggio,
# spesso basso, ma niente su cui mettere le mani. Il valore della metrica lo
# prendiamo dal campo, non da qui.
def _e_audit_metrica(aid: str, ha_contenuto: bool, risparmi: dict) -> bool:
    return not ha_contenuto and not risparmi


def ammesso(aid: str, score, risparmi: dict, ha_contenuto: bool) -> bool:
    """Un audit entra nel report per il suo ESITO, non per il risparmio dichiarato.

    Il criterio precedente — solo `metricSavings > 0` — teneva fuori
    `cls-culprits-insight` (savings CLS 0, ma con gli elementi che shiftano) e
    `image-delivery-insight` (savings 0, ma "Risparmio stimato di 225 KiB" e otto
    immagini nominate), e faceva entrare `layout-shifts` e `long-tasks` che su
    quella pagina erano audit SUPERATI: interventi da fare su cose che gia'
    funzionano.

    Restano fuori, oltre ai superati, gli audit che non nominano nulla: senza
    risorse, nodi, voci o checklist non c'e' un intervento da consegnare.
    """
    if aid in GIA_CONSUMATI:
        return False
    if aid in INSIGHT_INFORMATIVI:
        return ha_contenuto
    if _e_audit_metrica(aid, ha_contenuto, risparmi):
        return False
    if score is not None:
        return score < 1          # superato = non e' un intervento
    return bool(risparmi)         # audit senza esito: vale il risparmio


def estrai_opportunita(psi: dict, dominio_sito: str = "", domini_propri=()) -> list:
    """Audit da portare nel report, con le risorse, i nodi e le voci che li causano."""
    from .thirdparty import _propri, e_prima_parte   # import locale: evita il ciclo

    propri = _propri(dominio_sito, domini_propri) if dominio_sito else set()
    out = []
    for aid, audit in _audits(psi).items():
        risparmi = {k: float(v) for k, v in (audit.get("metricSavings") or {}).items()
                    if isinstance(v, (int, float)) and v > 0}

        risorse, elementi, voci = [], [], []
        for righe in _tabelle(audit):
            for riga in righe:
                if not isinstance(riga, dict):
                    continue
                risorsa, elemento, voce = _classifica_riga(
                    riga, propri, e_prima_parte, aid)
                if risorsa is not None:
                    risorse.append(risorsa)
                if elemento is not None:
                    elementi.append(elemento)
                if voce is not None:
                    voci.append(voce)
        if aid == "script-treemap-data":
            risorse += leggi_treemap(audit)
        if aid == "network-dependency-tree-insight":
            voci += leggi_catena_rete(audit)
        controlli = leggi_checklist(audit)

        opportunita = Opportunita(
            audit=aid,
            titolo=audit.get("title", aid),
            descrizione="",
            documentazione="",
            display=audit.get("displayValue", ""),
            score=audit.get("score"),
            etichetta_azione=etichetta_documentazione(audit.get("description", "")),
            risparmi=risparmi,
            risorse=sorted(risorse, key=lambda r: -r.spreco),
            elementi=sorted(elementi, key=lambda e: -e.misura),
            voci=sorted(voci, key=lambda v: -max(v.misure.values(), default=0.0)),
            controlli=controlli,
        )
        if not ammesso(aid, opportunita.score, risparmi, opportunita.ha_contenuto):
            continue
        if aid not in ARTEFATTI_DATI:
            opportunita.descrizione, opportunita.documentazione = _scomponi_descrizione(
                audit.get("description", ""))
        out.append(opportunita)

    # Il risparmio resta criterio di ordinamento, normalizzato per rendere
    # confrontabili metriche con scale diverse.
    return sorted(out, key=lambda o: -o.peso_relativo)


def estrai_richieste(psi: dict) -> list:
    items = _audits(psi).get("network-requests", {}).get("details", {}).get("items", [])
    out = []
    for r in items:
        if not isinstance(r, dict):
            continue
        url = r.get("url", "")
        entita = r.get("entity")
        if isinstance(entita, dict):
            entita = entita.get("text", "")
        out.append(Richiesta(
            url=url,
            host=urlparse(url).netloc,
            byte=int(r.get("transferSize") or 0),
            tipo=str(r.get("resourceType") or "?"),
            entita=str(entita or ""),
            stato=int(r.get("statusCode") or 0),
        ))
    return out


def estrai(psi: dict, url: str, form_factor: str, domini_propri=()) -> FattiPagina:
    lr = psi.get("lighthouseResult", {})
    selettore, snippet = estrai_elemento_lcp(psi)
    discovery, etichette = estrai_discovery(psi)
    campo = psi.get("loadingExperience") or {}
    score = lr.get("categories", {}).get("performance", {}).get("score")
    return FattiPagina(
        url=url,
        form_factor=form_factor,
        lighthouse_version=lr.get("lighthouseVersion", ""),
        timestamp=psi.get("analysisUTCTimestamp", ""),
        benchmark_index=float(lr.get("environment", {}).get("benchmarkIndex") or 0),
        performance_score=None if score is None else round(score * 100),
        lcp_elemento_selettore=selettore,
        lcp_elemento_snippet=snippet,
        lcp_fasi=estrai_fasi_lcp(psi),
        lcp_discovery=discovery,
        lcp_discovery_label=etichette,
        opportunita=estrai_opportunita(psi, url, domini_propri),
        richieste=estrai_richieste(psi),
        metriche_lab=estrai_metriche_lab(psi),
        campo_psi=campo.get("metrics", {}) or {},
        campo_psi_origin_fallback=bool(campo.get("origin_fallback")),
    )
