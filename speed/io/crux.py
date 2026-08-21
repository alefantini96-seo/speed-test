"""
Client CrUX API + CrUX History API.

Il campo e' l'unica metrica che mettiamo in serie storica (ADR-001), e viene da qui,
non da `loadingExperience` di PSI (ADR-002): Google ha annunciato che dismettera'
i dati CrUX dalla risposta PSI.

Nota sulla forma della risposta history: la serie sta in
`record.metrics.<metrica>.percentilesTimeseries.p75s`, NON in `metricTimeseries`.
Verificato su risposta reale.
"""
from __future__ import annotations

import httpx

from ..errori import da_risposta_google

BASE = "https://chromeuxreport.googleapis.com/v1/records"
METRICHE = [
    "largest_contentful_paint",
    "interaction_to_next_paint",
    "cumulative_layout_shift",
    "first_contentful_paint",
    "experimental_time_to_first_byte",
    # Ripartizione dell'LCP sugli utenti reali: e' la sorgente da preferire al
    # breakdown di laboratorio, che e' instabile. Presenti solo con LCP immagine.
    "largest_contentful_paint_image_time_to_first_byte",
    "largest_contentful_paint_image_resource_load_delay",
    "largest_contentful_paint_image_resource_load_duration",
    "largest_contentful_paint_image_element_render_delay",
]


class CruxNonDisponibile(Exception):
    """L'URL (o l'origin) non ha dati sufficienti in CrUX."""


def _data(d: dict) -> str:
    return f"{d['year']}-{d['month']:02d}-{d['day']:02d}"


# Parsing puro, separato dalla rete: la stessa funzione la usano i test sui fixture.
# CrUX restituisce anche metriche senza percentili (`navigation_types`,
# `largest_contentful_paint_resource_type`): vanno saltate, non fatte esplodere.

def leggi_record(dati: dict) -> dict:
    rec = dati["record"]
    periodo = rec["collectionPeriod"]
    metriche = {}
    for nome, valore in rec.get("metrics", {}).items():
        p75 = (valore or {}).get("percentiles", {}).get("p75")
        if p75 is not None:
            metriche[nome] = float(p75)
    return {
        "periodo_da": _data(periodo["firstDate"]),
        "periodo_a": _data(periodo["lastDate"]),
        "metriche": metriche,
    }


def leggi_storico(dati: dict) -> dict:
    rec = dati["record"]
    periodi = [_data(p["lastDate"]) for p in rec["collectionPeriods"]]
    serie = {}
    for nome, valore in rec.get("metrics", {}).items():
        p75s = (valore or {}).get("percentilesTimeseries", {}).get("p75s")
        if not p75s:
            continue
        serie[nome] = [None if v is None else float(v) for v in p75s]
    return {"periodi": periodi, "serie": serie}


def _payload(url: str, form_factor: str, origin: bool) -> dict:
    chiave = "origin" if origin else "url"
    return {chiave: url, "formFactor": form_factor, "metrics": METRICHE}


async def record(client: httpx.AsyncClient, api_key: str, url: str,
                 form_factor: str = "PHONE", origin: bool = False) -> dict:
    """p75 correnti. Solleva CruxNonDisponibile se l'URL non ha dati."""
    r = await client.post(f"{BASE}:queryRecord", params={"key": api_key},
                          json=_payload(url, form_factor, origin), timeout=30)
    dati = r.json()
    if "error" in dati:
        err = dati["error"]
        if err.get("code") == 404:
            raise CruxNonDisponibile(url)
        raise da_risposta_google("CrUX", err.get("code"), err.get("message", ""), url)

    return {"url": url, "livello": "origin" if origin else "url"} | leggi_record(dati)


async def storico(client: httpx.AsyncClient, api_key: str, url: str,
                  form_factor: str = "PHONE", periodi: int = 40,
                  origin: bool = False) -> dict:
    """Fino a 40 settimane. Ogni punto e' una media mobile a 28 giorni: un evento
    istantaneo appare spalmato su circa quattro punti."""
    payload = _payload(url, form_factor, origin) | {"collectionPeriodCount": periodi}
    r = await client.post(f"{BASE}:queryHistoryRecord", params={"key": api_key},
                          json=payload, timeout=45)
    dati = r.json()
    if "error" in dati:
        err = dati["error"]
        if err.get("code") == 404:
            raise CruxNonDisponibile(url)
        raise da_risposta_google("CrUX History", err.get("code"),
                                 err.get("message", ""), url)

    return {"url": url} | leggi_storico(dati)


async def raccogli(client: httpx.AsyncClient, api_key: str, url: str,
                   form_factor: str = "PHONE") -> dict:
    """Metriche di campo e andamento di una pagina, in due passi SEPARATI.

    Chiedere record e storico in un'unica espressione faceva perdere tutto: se lo
    storico falliva, l'eccezione impediva l'assegnazione dell'intero risultato, la
    pagina restava "assente" pur avendo metriche correnti valide, e ogni priorita'
    ricadeva su "media". Il tool smetteva di calibrare sul campo senza dirlo.

    Lo storico e' un di piu' che serve all'andamento, non alla diagnosi: se manca,
    degrada solo se stesso.

    Vive qui e non nei chiamanti perche' CLI e versione web ne avevano una copia
    a testa, e solo una delle due era corretta.
    """
    voce = {"livello": "assente", "metriche": {}, "storico": None}
    try:
        rec = await record(client, api_key, url, form_factor)
    except CruxNonDisponibile:
        return voce      # resta la sola diagnosi di laboratorio, dichiarata nel report

    voce = {"livello": "url", "metriche": rec["metriche"],
            "periodo_a": rec["periodo_a"], "storico": None}
    try:
        voce["storico"] = await storico(client, api_key, url, form_factor)
    except Exception:
        pass             # niente andamento, ma le metriche correnti restano
    return voce


async def disponibilita(client: httpx.AsyncClient, api_key: str, url: str,
                        form_factor: str = "PHONE") -> dict:
    """Usata da `check-config`: dice se l'URL ha dati di campo a livello di pagina."""
    try:
        r = await record(client, api_key, url, form_factor)
        return {"url": url, "campo_url": True, "metriche": r["metriche"],
                "periodo_a": r["periodo_a"]}
    except CruxNonDisponibile:
        return {"url": url, "campo_url": False, "metriche": {}, "periodo_a": None}
