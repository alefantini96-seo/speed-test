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

from ..errori import da_risposta_google

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


# Codici su cui vale la pena riprovare: sono transitori. PSI risponde "Unable to
# process" con regolarita', e su venti template una risposta persa e' un buco
# silenzioso nel report — un template che non compare, senza che nessuno lo noti.
CODICI_RIPROVABILI = (429, 500, 502, 503, 504)


def _json_sicuro(risposta) -> dict | None:
    """Il corpo come dizionario, o None se non e' JSON.

    Un 502 del gateway o una pagina di quota tornano HTML: chiamare `.json()`
    alla cieca faceva esplodere JSONDecodeError, che non dice niente a nessuno.
    """
    try:
        dati = risposta.json()
    except ValueError:
        return None
    return dati if isinstance(dati, dict) else None


async def analizza(client: httpx.AsyncClient, api_key: str, url: str,
                   strategy: str = "mobile", locale: str = "it",
                   tentativi: int = 3, attesa_iniziale: float = 2.0) -> dict:
    """Una misurazione di laboratorio, con riprova sui codici transitori."""
    risposta = None
    for tentativo in range(1, tentativi + 1):
        risposta = await client.get(ENDPOINT, params={
            "url": url,
            "strategy": strategy,
            "category": "performance",
            "locale": locale,      # titoli, descrizioni e checklist gia' in italiano
            "key": api_key,
        }, timeout=120)
        if risposta.status_code not in CODICI_RIPROVABILI or tentativo == tentativi:
            break
        # Backoff esponenziale: 2s, 4s. Su 429 riprovare subito peggiora le cose.
        await asyncio.sleep(attesa_iniziale * 2 ** (tentativo - 1))

    dati = _json_sicuro(risposta)
    if dati is not None and "error" in dati:
        err = dati["error"]
        raise da_risposta_google("PageSpeed Insights", err.get("code"),
                                 err.get("message", ""), url)
    if risposta.status_code >= 400:
        raise da_risposta_google("PageSpeed Insights", risposta.status_code,
                                 (risposta.text or "")[:200], url)
    if dati is None:
        raise da_risposta_google(
            "PageSpeed Insights", risposta.status_code,
            "la risposta non e' in formato JSON", url)
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
