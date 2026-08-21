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
    risparmi: list = field(default_factory=list)
    opportunita: list = field(default_factory=list)
    richieste: list = field(default_factory=list)
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


def estrai_risparmi(psi: dict) -> list:
    """Tutti gli audit che dichiarano `metricSavings`, ordinati per risparmio LCP.

    Volutamente generico: regge l'aggiunta di nuovi insight da parte di Lighthouse
    senza dover mappare ogni singolo audit a mano.
    """
    out = []
    for aid, a in _audits(psi).items():
        ms = a.get("metricSavings") or {}
        ms = {k: v for k, v in ms.items() if isinstance(v, (int, float)) and v > 0}
        if not ms:
            continue
        out.append({
            "audit": aid,
            "titolo": a.get("title", aid),
            "score": a.get("score"),
            "display": a.get("displayValue", ""),
            "risparmi": ms,
        })
    return sorted(out, key=lambda x: -x["risparmi"].get("LCP", 0))


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

    @property
    def spreco(self) -> float:
        """Metrica unica per ordinare: ms se ci sono, altrimenti byte."""
        return self.ms_sprecati or self.byte_sprecati


@dataclass
class Opportunita:
    audit: str
    titolo: str            # testo di Lighthouse
    descrizione: str       # testo di Lighthouse, senza il link markdown
    documentazione: str    # URL estratto dalla descrizione
    display: str           # es. "Risparmio stimato di 508 KiB"
    score: float | None
    risparmi: dict         # metricSavings: {LCP: ms, FCP: ms, TBT: ms, CLS: ...}
    risorse: list = field(default_factory=list)

    @property
    def risparmio_massimo(self) -> float:
        return max(self.risparmi.values()) if self.risparmi else 0.0

    @property
    def quota_terze_parti(self) -> float:
        """Quota dello spreco attribuibile a risorse di terze parti.
        Serve a stabilire chi deve intervenire, sul dato invece che a intuito."""
        totale = sum(r.spreco for r in self.risorse)
        if not totale:
            return 0.0
        return sum(r.spreco for r in self.risorse if r.terza_parte) / totale


_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _scomponi_descrizione(testo: str):
    """Lighthouse inserisce link markdown anche in mezzo alla frase.

    Il link va sostituito con la sua etichetta, non rimosso: togliere tutto
    mutilava frasi come "impostare [font-display](...) su swap".
    """
    link = _LINK.search(testo or "")
    pulito = _LINK.sub(lambda c: c.group(1), testo or "").strip()
    return (pulito, link.group(2) if link else "")


def _righe_con_url(audit: dict) -> list:
    """Righe che nominano una risorsa, ovunque siano annidate nei details.

    Lighthouse usa `type: opportunity` per le vecchie opportunita' e `type: table`
    dentro `type: list` per gli insight nuovi: raccogliamo entrambe.
    """
    righe = []
    dettagli = audit.get("details", {}) or {}
    for item in dettagli.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        if "url" in item:
            righe.append(item)
        for annidato in item.get("items", []) or []:
            if isinstance(annidato, dict) and "url" in annidato:
                righe.append(annidato)
    return righe


def estrai_opportunita(psi: dict, dominio_sito: str = "", domini_propri=()) -> list:
    """Audit falliti con risparmio dichiarato, con le risorse che li causano."""
    from .thirdparty import _propri, e_prima_parte   # import locale: evita il ciclo

    propri = _propri(dominio_sito, domini_propri) if dominio_sito else set()
    out = []
    for aid, audit in _audits(psi).items():
        risparmi = {k: float(v) for k, v in (audit.get("metricSavings") or {}).items()
                    if isinstance(v, (int, float)) and v > 0}
        if not risparmi:
            continue
        descrizione, documentazione = _scomponi_descrizione(audit.get("description", ""))
        risorse = []
        for riga in _righe_con_url(audit):
            url = riga.get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            host = urlparse(url).netloc
            risorse.append(Risorsa(
                url=url,
                byte_totali=int(riga.get("totalBytes") or 0),
                byte_sprecati=int(riga.get("wastedBytes") or 0),
                ms_sprecati=float(riga.get("wastedMs") or riga.get("duration") or 0.0),
                quota_sprecata=float(riga.get("wastedPercent") or 0.0),
                terza_parte=bool(propri) and not e_prima_parte(host, propri),
            ))
        risorse.sort(key=lambda r: -r.spreco)
        out.append(Opportunita(
            audit=aid,
            titolo=audit.get("title", aid),
            descrizione=descrizione,
            documentazione=documentazione,
            display=audit.get("displayValue", ""),
            score=audit.get("score"),
            risparmi=risparmi,
            risorse=risorse,
        ))
    return sorted(out, key=lambda o: -o.risparmio_massimo)


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
        risparmi=estrai_risparmi(psi),
        opportunita=estrai_opportunita(psi, url, domini_propri),
        richieste=estrai_richieste(psi),
        campo_psi=campo.get("metrics", {}) or {},
        campo_psi_origin_fallback=bool(campo.get("origin_fallback")),
    )
