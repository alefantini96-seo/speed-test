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

from ..core.extract import CATEGORIE
from ..errori import da_attesa_scaduta, da_rete, da_risposta_google
from .google import CODICI_RIPROVABILI, richiedi

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Timeout di una singola chiamata. Una misurazione impiega 30-60 secondi: la CLI
# puo' permettersi di aspettare, il percorso web no e passa il suo (vedi web.py).
TIMEOUT = 120.0

# Sotto questa soglia non si tenta nemmeno: la misurazione piu' rapida mai vista
# su una pagina vera e' stata 24,3 s, quindi con meno tempo di cosi' si
# spenderebbe l'attesa per un fallimento sicuro.
MINIMO_UTILE = 30.0


async def analizza(client: httpx.AsyncClient, api_key: str, url: str,
                   strategy: str = "mobile", locale: str = "it",
                   chiamate: int = 3, attesa_iniziale: float = 2.0,
                   timeout: float = TIMEOUT, categorie=CATEGORIE,
                   scadenza: float | None = None) -> dict:
    """Una misurazione di laboratorio, con al massimo `chiamate` tentativi.

    Il budget e' sulle **chiamate**, non sul motivo per cui una e' andata male:
    una risposta transitoria (500, 503) e una scadenza costano uguale e pescano
    dallo stesso gruzzolo. Contarle separatamente faceva sprecare il tentativo
    piu' utile — dopo uno scadere non si riprovava affatto, e la pagina falliva
    con meta' del tempo ancora disponibile.

    **Riprovare dopo uno scadere e' un secondo sorteggio, non il recupero del
    primo.** Misurato il 15/09/2026: abbandonata una chiamata a 15 s e richiesta
    la stessa URL dopo 45 e dopo 90 secondi, la risposta e' arrivata in 41,0 e
    32,5 s, con una marca temporale nuova. PSI non tiene il lavoro che nessuno ha
    ritirato. Il sorteggio pero' conviene lo stesso: su nove misurazioni di tre
    URL la mediana era 33,9 s e nessuna oltre i 51, quindi una lenta oltre ogni
    misura e' l'eccezione e la seconda pesca quasi sempre meglio.

    `scadenza` e' il tempo del ciclo di eventi oltre il quale non si comincia una
    chiamata nuova: chi gira in una funzione serverless ha un tetto di durata, e
    una riprova che sfora fa uccidere la funzione invece di consegnare l'errore.

    Le categorie chieste sono quattro. Accessibilita', best practice e SEO non
    entrano in nessuna valutazione — valgono quanto il punteggio prestazioni,
    cioe' come riferimento (ADR-001) — ma sono gia' dentro la stessa risposta e
    sono il numero che il cliente vede aprendo pagespeed.web.dev.

    Non costano un'altra misurazione: Lighthouse riusa il trace che ha gia'
    raccolto e calcola audit in piu'. Misurato su www.pluxee.it: 46 s con la sola
    performance, 32 s con tutte e quattro — la variabilita' fra due run supera il
    costo delle categorie. Cresce invece il corpo della risposta, da 874 KB a
    1,1 MB, che e' traffico del server e non del browser.
    """
    orologio = asyncio.get_event_loop().time
    scaduta = None

    for numero in range(1, max(1, chiamate) + 1):
        quanto = timeout
        if scadenza is not None:
            quanto = min(timeout, scadenza - orologio())
            if quanto < MINIMO_UTILE:
                # La prima si tenta comunque, col tempo che c'e': l'errore dira'
                # quanto si e' aspettato davvero. E' la riprova che non comincia,
                # perche' sforerebbe il tetto e la funzione verrebbe uccisa dalla
                # piattaforma prima di consegnare l'errore con il rimedio.
                if numero > 1:
                    break
                quanto = max(quanto, 1.0)

        try:
            risposta, dati = await richiedi(lambda: client.get(ENDPOINT, params={
                "url": url,
                "strategy": strategy,
                "category": list(categorie),
                "locale": locale,   # titoli, descrizioni e checklist gia' in italiano
                "key": api_key,
            }, timeout=quanto), 1, 0.0)
        except httpx.TimeoutException:
            scaduta = quanto
            continue          # un secondo sorteggio, se il budget lo paga ancora
        except httpx.HTTPError as guasto:
            # La rete caduta non e' la pagina lenta, e non si riprova: sarebbe lo
            # stesso guasto un istante dopo.
            raise da_rete("PageSpeed Insights", guasto, url) from None

        codice = risposta.status_code
        messaggio = ""
        if dati is not None and "error" in dati:
            codice = dati["error"].get("code", codice)
            messaggio = dati["error"].get("message", "")
        elif codice < 400 and dati is not None:
            return dati
        elif codice < 400:
            messaggio = "la risposta non e' in formato JSON"

        if codice in CODICI_RIPROVABILI and numero < chiamate:
            await asyncio.sleep(attesa_iniziale * 2 ** (numero - 1))
            continue
        raise da_risposta_google("PageSpeed Insights", codice,
                                 messaggio or (risposta.text or "")[:200], url)

    if scaduta is not None:
        raise da_attesa_scaduta("PageSpeed Insights", scaduta, url)
    raise da_attesa_scaduta("PageSpeed Insights", timeout, url)


async def analizza_molte(api_key: str, urls: list, strategy: str = "mobile",
                         parallelismo: int = 4, locale: str = "it",
                         ripetizioni: int = 3, attesa_fra_giri: float = 90.0,
                         avviso=None, chiamate: int = 3,
                         attesa_iniziale: float = 2.0,
                         timeout: float = TIMEOUT, categorie=CATEGORIE,
                         secondi: float | None = None) -> dict:
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

    `chiamate`, `attesa_iniziale` e `timeout` valgono per la singola misurazione e
    li decide il chiamante: chi gira dentro una funzione serverless ha un tetto di
    durata e deve stare sotto (vedi `web.Budget`), la CLI no.

    `secondi` e' quanto tempo c'e' in tutto: da li' esce la scadenza che le
    chiamate rispettano, e un giro nuovo non comincia se non ci sta.
    """
    sem = asyncio.Semaphore(parallelismo)
    risultati: dict = {u: [] for u in urls}
    orologio = asyncio.get_event_loop().time
    scadenza = orologio() + secondi if secondi is not None else None

    async with httpx.AsyncClient() as client:
        async def uno(url: str):
            async with sem:
                try:
                    risultati[url].append(await analizza(
                        client, api_key, url, strategy, locale,
                        chiamate, attesa_iniziale, timeout, categorie, scadenza))
                except Exception as exc:   # la singola pagina non deve fermare il run
                    risultati[url].append(exc)

        for giro in range(ripetizioni):
            inizio = orologio()
            if avviso:
                avviso(giro + 1, ripetizioni, 0.0)
            await asyncio.gather(*(uno(u) for u in urls))

            if giro == ripetizioni - 1:
                break
            # Un giro in piu' serve al consenso sulle fasi LCP, ma vale meno di
            # una misurazione consegnata: se non ci sta nella scadenza si tiene
            # quello che c'e' e il report dichiara "una misurazione".
            if scadenza is not None and orologio() + MINIMO_UTILE > scadenza:
                break
            residuo = attesa_fra_giri - (orologio() - inizio)
            if residuo > 0:
                if avviso:
                    avviso(giro + 1, ripetizioni, residuo)
                await asyncio.sleep(residuo)

    return risultati
