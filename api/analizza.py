"""
Endpoint Vercel: analizza UNA singola URL.

Perche' una alla volta e non tutta la lista: una scansione completa dura minuti e
non sta nei 300 secondi di una funzione Vercel. Una URL sola sta in ~60 secondi,
e il browser puo' mostrare i risultati mano a mano invece di far aspettare in
bianco. Nessuna coda, nessun database, nessun polling.

La chiave Google resta lato server, in variabile d'ambiente: non passa mai dal
browser. L'accesso e' protetto da SPEED_PASSWORD, altrimenti chiunque abbia il
link consuma la quota.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# La funzione gira da api/: il pacchetto sta nella radice del progetto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from speed.core import consenso, diagnose, extract, thirdparty  # noqa: E402
from speed.core.soglie import fasi_dal_campo  # noqa: E402
from speed.io import crux, psi  # noqa: E402

LIMITE_URL = 2048


def _serializza(o):
    if is_dataclass(o):
        return asdict(o)
    raise TypeError(f"non serializzabile: {type(o)}")


async def analizza_una(api_key: str, url: str, form_factor: str,
                       domini_propri: list) -> dict:
    """Campo + laboratorio + diagnosi per una singola pagina."""
    voce_campo = {"livello": "assente", "metriche": {}, "storico": None}
    async with httpx.AsyncClient() as client:
        try:
            record = await crux.record(client, api_key, url, form_factor)
            voce_campo = {"livello": "url", "metriche": record["metriche"],
                          "periodo_a": record["periodo_a"],
                          "storico": await crux.storico(client, api_key, url, form_factor)}
        except crux.CruxNonDisponibile:
            pass   # resta la sola diagnosi di laboratorio, dichiarata nel report

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
        "fatti": _fatti_essenziali(fatti),
        "campo": voce_campo,
        "terze_parti": _terze_essenziali(riepilogo),
        "problemi": problemi,
        "misurazioni": accordo.ripetizioni,
        "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }


def _fatti_essenziali(fatti) -> dict:
    """Solo cio' che serve a interfaccia e report.

    La lista completa delle richieste di rete e le opportunita' grezze pesano
    decine di KB a pagina e sono gia' state consumate: le risorse colpevoli sono
    dentro i problemi, il peso dentro il riepilogo. Il browser deve rimandare
    indietro questo payload per generare il Word, e il limite del corpo di una
    richiesta Vercel e' 4,5 MB.
    """
    return {
        "lighthouse_version": fatti.lighthouse_version,
        "benchmark_index": fatti.benchmark_index,
        "timestamp": fatti.timestamp,
        "performance_score": fatti.performance_score,
        "lcp_elemento_snippet": fatti.lcp_elemento_snippet,
        "lcp_fasi": fatti.lcp_fasi,
    }


def _terze_essenziali(riepilogo) -> dict:
    return {
        "byte_totali": riepilogo.byte_totali,
        "byte_first": riepilogo.byte_first,
        "byte_terzi": riepilogo.byte_terzi,
        "richieste_totali": riepilogo.richieste_totali,
        "entita": [{"nome": e.nome, "byte": e.byte, "richieste": e.richieste,
                    "terza_parte": e.terza_parte} for e in riepilogo.entita[:10]],
    }


class handler(BaseHTTPRequestHandler):

    def _rispondi(self, codice: int, corpo: dict):
        testo = json.dumps(corpo, default=_serializza, ensure_ascii=False).encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(testo)))
        self.end_headers()
        self.wfile.write(testo)

    def do_POST(self):
        try:
            lunghezza = int(self.headers.get("Content-Length") or 0)
            richiesta = json.loads(self.rfile.read(lunghezza) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._rispondi(400, {"errore": "Richiesta non valida."})

        attesa = os.getenv("SPEED_PASSWORD")
        if attesa and richiesta.get("password") != attesa:
            return self._rispondi(401, {"errore": "Password non valida."})

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return self._rispondi(500, {
                "errore": "GOOGLE_API_KEY non configurata sul server.",
                "rimedio": "Impostala nelle variabili d'ambiente del progetto Vercel."})

        url = (richiesta.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or len(url) > LIMITE_URL:
            return self._rispondi(400, {
                "errore": "URL non valido.",
                "rimedio": "Serve un indirizzo completo, che inizi con https://"})

        form_factor = "DESKTOP" if richiesta.get("desktop") else "PHONE"
        domini = [d for d in (richiesta.get("domini_propri") or []) if isinstance(d, str)]

        try:
            risultato = asyncio.run(analizza_una(api_key, url, form_factor, domini))
        except Exception as exc:
            return self._rispondi(502, {"errore": str(exc)[:400], "url": url})

        self._rispondi(200, risultato)

    def do_GET(self):
        self._rispondi(200, {"stato": "ok", "metodo": "usa POST con {url, password}"})
