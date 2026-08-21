"""
Logica della versione online, indipendente dal server che la ospita.

Sta nel pacchetto e non in `app.py` per due ragioni: e' testabile senza alzare un
server, e il giorno che cambia la piattaforma si riscrive solo l'involucro.

La scelta di fondo: si analizza **una URL per richiesta**. Una scansione completa
dura minuti e non sta nei limiti di una funzione serverless; una pagina sola sta
in 20-60 secondi, e il browser puo' mostrare i risultati mano a mano. Nessuna
coda, nessun database, nessun polling.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

import httpx

from .core import consenso, diagnose, extract, thirdparty
from .core.soglie import fasi_dal_campo
from .io import crux, psi

LIMITE_URL = 2048
LIMITE_PAGINE = 40


def serializza(o):
    if is_dataclass(o):
        return asdict(o)
    raise TypeError(f"non serializzabile: {type(o)}")


def valida_url(url: str) -> str | None:
    """Ritorna il messaggio d'errore, o None se l'URL va bene."""
    if not url or not url.startswith(("http://", "https://")):
        return "Serve un indirizzo completo, che inizi con https://"
    if len(url) > LIMITE_URL:
        return "URL troppo lungo."
    return None


def fatti_essenziali(fatti) -> dict:
    """Solo cio' che serve a interfaccia e report.

    La lista completa delle richieste di rete e le opportunita' grezze pesano
    decine di KB a pagina e sono gia' state consumate: le risorse colpevoli sono
    dentro i problemi, il peso dentro il riepilogo. Il browser deve rimandare
    indietro questo payload per generare il Word, e il limite del corpo di una
    richiesta e' 4,5 MB.
    """
    return {
        "lighthouse_version": fatti.lighthouse_version,
        "benchmark_index": fatti.benchmark_index,
        "timestamp": fatti.timestamp,
        "performance_score": fatti.performance_score,
        "lcp_elemento_snippet": fatti.lcp_elemento_snippet,
        "lcp_fasi": fatti.lcp_fasi,
    }


def terze_essenziali(riepilogo) -> dict:
    return {
        "byte_totali": riepilogo.byte_totali,
        "byte_first": riepilogo.byte_first,
        "byte_terzi": riepilogo.byte_terzi,
        "richieste_totali": riepilogo.richieste_totali,
        "entita": [{"nome": e.nome, "byte": e.byte, "richieste": e.richieste,
                    "terza_parte": e.terza_parte} for e in riepilogo.entita[:10]],
    }


async def raccogli_campo(client, api_key: str, url: str, form_factor: str) -> dict:
    """Metriche di campo e andamento, chiesti in due passi SEPARATI.

    Costruire la voce in un'unica espressione che contiene la chiamata allo
    storico faceva perdere tutto: se lo storico falliva, l'eccezione impediva
    l'assegnazione dell'intero dizionario, la pagina restava "assente" anche
    avendo metriche correnti valide, e ogni priorita' ricadeva su "media". Il
    tool smetteva di calibrare sul campo senza dirlo a nessuno.

    Lo storico mancante deve degradare solo lo storico: e' un di piu' che serve
    all'andamento, non alla diagnosi.
    """
    voce = {"livello": "assente", "metriche": {}, "storico": None}
    try:
        record = await crux.record(client, api_key, url, form_factor)
    except crux.CruxNonDisponibile:
        return voce      # resta la sola diagnosi di laboratorio, dichiarata nel report

    voce = {"livello": "url", "metriche": record["metriche"],
            "periodo_a": record["periodo_a"], "storico": None}
    try:
        voce["storico"] = await crux.storico(client, api_key, url, form_factor)
    except Exception:
        pass             # niente andamento, ma le metriche correnti restano
    return voce


async def analizza_una(api_key: str, url: str, form_factor: str,
                       domini_propri: list) -> dict:
    """Campo + laboratorio + diagnosi per una singola pagina."""
    async with httpx.AsyncClient() as client:
        voce_campo = await raccogli_campo(client, api_key, url, form_factor)

    # Se le fasi LCP arrivano dal campo basta una misurazione: il laboratorio
    # serve solo per i fatti diagnostici, che sono stabili fra i run.
    metriche = voce_campo.get("metriche") or {}
    ripetizioni = 1 if fasi_dal_campo(metriche) else 2

    strategy = "desktop" if form_factor == "DESKTOP" else "mobile"
    risposte = await psi.analizza_molte(api_key, [url], strategy,
                                        ripetizioni=ripetizioni, attesa_fra_giri=45.0)
    riuscite = [r for r in risposte[url] if not isinstance(r, Exception)]
    if not riuscite:
        fallita = next((r for r in risposte[url] if isinstance(r, Exception)), None)
        raise RuntimeError(str(fallita) if fallita else "PageSpeed Insights non ha risposto")

    accordo = consenso.combina([extract.estrai(r, url, form_factor, domini_propri)
                                for r in riuscite])
    fatti = accordo.fatti
    riepilogo = thirdparty.riepiloga(fatti.richieste, url, domini_propri)
    problemi = diagnose.diagnostica(fatti, metriche, riepilogo, accordo)

    return {
        "template": url,
        "url": url,
        "fatti": fatti_essenziali(fatti),
        "campo": voce_campo,
        "terze_parti": terze_essenziali(riepilogo),
        "problemi": problemi,
        "misurazioni": accordo.ripetizioni,
        "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }
