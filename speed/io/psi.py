"""
Client PageSpeed Insights.

Da PSI prendiamo i fatti diagnostici del lab E il testo delle raccomandazioni:
con `locale=it` Lighthouse restituisce titoli, descrizioni e checklist gia' in
italiano, con i link alla documentazione Google. Quel testo va nel report cosi'
com'e' (ADR-004): non lo riscriviamo.

Del lab non prendiamo il punteggio (ADR-001): quale elemento e' l'LCP,
in quale fase si perde il tempo, cosa blocca il rendering, quanto pesa la pagina.
Il punteggio non viene analizzato ne' messo in serie storica: e' rumoroso e cambia
fra due chiamate identiche. Lo riportiamo una volta sola come "numero vetrina",
quello che il cliente vede aprendo pagespeed.web.dev.

Una chiamata puo' impiegare 30-60 secondi. Le pagine vengono misurate in parallelo.
"""
from __future__ import annotations

import asyncio

import httpx

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def analizza(client: httpx.AsyncClient, api_key: str, url: str,
                   strategy: str = "mobile", locale: str = "it") -> dict:
    r = await client.get(ENDPOINT, params={
        "url": url,
        "strategy": strategy,
        "category": "performance",
        "locale": locale,      # titoli, descrizioni e checklist gia' in italiano
        "key": api_key,
    }, timeout=120)
    dati = r.json()
    if "error" in dati:
        err = dati["error"]
        raise RuntimeError(f"PSI {err.get('code')}: {err.get('message', '')[:160]}")
    return dati


async def analizza_molte(api_key: str, urls: list, strategy: str = "mobile",
                         parallelismo: int = 4, locale: str = "it",
                         ripetizioni: int = 3, attesa_fra_giri: float = 90.0,
                         avviso=None) -> dict:
    """Ritorna {url: [risposta | Exception, ...]}.

    Le ripetizioni servono perche' la ripartizione in fasi dell'LCP e' instabile
    fra run (vedi core/consenso.py). Ma **PSI serve risultati dalla cache**: tre
    chiamate ravvicinate alla stessa URL tornano identiche, stesso
    `analysisUTCTimestamp`. Per ottenere misurazioni davvero distinte le
    ripetizioni sono organizzate in giri distanziati nel tempo.

    Con molti template un giro dura gia' piu' della cache e l'attesa e' nulla:
    il costo si paga solo quando i template sono pochi.

    Il parallelismo resta basso: la quota non e' il vincolo (240 richieste al
    minuto), lo e' la pazienza di PSI.
    """
    sem = asyncio.Semaphore(parallelismo)
    risultati: dict = {u: [] for u in urls}

    async with httpx.AsyncClient() as client:
        async def uno(url: str):
            async with sem:
                try:
                    risultati[url].append(await analizza(client, api_key, url, strategy, locale))
                except Exception as exc:   # la singola pagina non deve fermare il run
                    risultati[url].append(exc)

        orologio = asyncio.get_event_loop().time
        for giro in range(ripetizioni):
            inizio = orologio()
            if avviso:
                avviso(giro + 1, ripetizioni, 0.0)
            await asyncio.gather(*(uno(u) for u in urls))

            if giro == ripetizioni - 1:
                break
            residuo = attesa_fra_giri - (orologio() - inizio)
            if residuo > 0:
                if avviso:
                    avviso(giro + 1, ripetizioni, residuo)
                await asyncio.sleep(residuo)

    return risultati
