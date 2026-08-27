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

from dataclasses import asdict, dataclass, is_dataclass

import httpx

from .core import consenso, diagnose, extract, thirdparty
from .core.soglie import fasi_dal_campo
from .io import crux, psi

LIMITE_URL = 2048
LIMITE_PAGINE = 40


# --------------------------------------------------------------------------- #
#  Budget di tempo
#
#  Vercel uccide la funzione a `maxDuration` secondi (vercel.json) e restituisce
#  un 504 anonimo: l'utente perde l'errore con rimedio di errori.py, che e' tutto
#  cio' che gli direbbe cosa fare. Quindi il caso peggiore va tenuto sotto, e il
#  budget lo decide chi chiama invece di essere sparso nei client.
#
#  Con i valori predefiniti dei client — 3 tentativi PSI da 120 s, 2 giri, 45 s
#  di attesa, piu' 75 s di CrUX — il caso peggiore era 852 s: quasi il triplo.
#
#  La CLI non ha limiti di durata e non passa nessun budget: tiene i valori
#  predefiniti, piu' generosi.
# --------------------------------------------------------------------------- #

MAX_DURATA_VERCEL = 300      # deve restare uguale a maxDuration in vercel.json


@dataclass(frozen=True)
class Budget:
    """Timeout e tentativi del percorso web, con il conto del caso peggiore.

    I numeri sono stretti apposta. Una chiamata PSI impiega di norma 30-60 s:
    55 s la copre, e il secondo tentativo c'e' per i codici transitori, che
    arrivano subito e non consumano il timeout. CrUX risponde in un paio di
    secondi: 8 s sono gia' abbondanti.
    """
    psi_tentativi: int = 2
    psi_timeout: float = 55.0
    psi_backoff: float = 2.0
    psi_attesa_fra_giri: float = 45.0
    psi_giri_massimi: int = 2
    crux_timeout_record: float = 8.0
    crux_timeout_storico: float = 8.0
    crux_tentativi: int = 2
    crux_tentativi_storico: int = 1
    crux_backoff: float = 1.0

    @staticmethod
    def _backoff_totale(tentativi: int, iniziale: float) -> float:
        """Le attese fra un tentativo e l'altro: iniziale, poi il doppio, ecc."""
        return iniziale * (2 ** (tentativi - 1) - 1) if tentativi > 1 else 0.0

    @property
    def giro_psi(self) -> float:
        return (self.psi_tentativi * self.psi_timeout
                + self._backoff_totale(self.psi_tentativi, self.psi_backoff))

    @property
    def campo(self) -> float:
        return (self.crux_tentativi * self.crux_timeout_record
                + self._backoff_totale(self.crux_tentativi, self.crux_backoff)
                + self.crux_tentativi_storico * self.crux_timeout_storico
                + self._backoff_totale(self.crux_tentativi_storico, self.crux_backoff))

    def peggior_caso(self, giri: int | None = None) -> float:
        """Il tempo massimo di una analisi, in secondi.

        L'attesa fra i giri non si somma: `analizza_molte` aspetta il residuo,
        cioe' solo cio' che manca ad `attesa_fra_giri` dall'inizio del giro. Se
        il giro e' durato piu' dell'attesa, non aspetta affatto.
        """
        giri = self.psi_giri_massimi if giri is None else giri
        lab = self.giro_psi if giri <= 1 else             max(self.giro_psi, self.psi_attesa_fra_giri) + self.giro_psi * (giri - 1)
        return self.campo + lab


BUDGET = Budget()


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


async def analizza_una(api_key: str, url: str, form_factor: str,
                       domini_propri: list, budget: Budget = BUDGET) -> dict:
    """Campo + laboratorio + diagnosi per una singola pagina.

    Il budget e' esplicito e viene passato ai client: senza, il caso peggiore
    superava il tetto di durata della piattaforma e l'utente vedeva un 504
    anonimo al posto dell'errore con rimedio.
    """
    async with httpx.AsyncClient() as client:
        voce_campo = await crux.raccogli(
            client, api_key, url, form_factor,
            timeout_record=budget.crux_timeout_record,
            timeout_storico=budget.crux_timeout_storico,
            tentativi=budget.crux_tentativi,
            tentativi_storico=budget.crux_tentativi_storico,
            attesa_iniziale=budget.crux_backoff)

    # Se le fasi LCP arrivano dal campo basta una misurazione: il laboratorio
    # serve solo per i fatti diagnostici, che sono stabili fra i run.
    metriche = voce_campo.get("metriche") or {}
    ripetizioni = 1 if fasi_dal_campo(metriche) else budget.psi_giri_massimi

    strategy = "desktop" if form_factor == "DESKTOP" else "mobile"
    risposte = await psi.analizza_molte(
        api_key, [url], strategy, ripetizioni=ripetizioni,
        attesa_fra_giri=budget.psi_attesa_fra_giri,
        tentativi=budget.psi_tentativi, attesa_iniziale=budget.psi_backoff,
        timeout=budget.psi_timeout)
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
        "peso_per_tipo": thirdparty.peso_per_tipo(fatti.richieste),
        "problemi": problemi,
        "misurazioni": accordo.ripetizioni,
        "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }
