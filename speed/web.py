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

from .core import cascata, consenso, diagnose, extract, thirdparty
from .errori import ErroreSpeed
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
#  Il tetto sta sulle CHIAMATE a PageSpeed, non sui giri: due giri da un
#  tentativo e un giro da due tentativi costano lo stesso e stanno nello stesso
#  budget. Contarli separatamente — due giri PER due tentativi — obbligava a
#  stringere il timeout a 55 s per far tornare il conto, e 55 s sono pochi:
#  misurate il 15/09/2026 nove chiamate su tre URL di www.pluxee.it, mediana
#  33,9 s e massima 50,9 s, cioe' il 93% del tetto; e un percorso completo con
#  tre misurazioni in parallelo sulla stessa chiave ha impiegato 101,6 s. Quando
#  la misurazione sforava, sforava anche il giro successivo, e all'utente
#  arrivava "Errore 502" senza causa.
#
#  La CLI non ha limiti di durata e non passa nessun budget: tiene i valori
#  predefiniti, piu' generosi.
# --------------------------------------------------------------------------- #

MAX_DURATA_VERCEL = 300      # deve restare uguale a maxDuration in vercel.json


@dataclass(frozen=True)
class Budget:
    """Timeout e chiamate del percorso web, con il conto del caso peggiore.

    Una chiamata PSI impiega di norma 30-60 s e sotto carico anche il doppio:
    120 s la coprono, e sono il massimo che lascia in piedi i 30 s di margine
    sul tetto della piattaforma. CrUX risponde in un paio di secondi - misurati
    0,2 - e 8 s sono gia' abbondanti.

    `psi_chiamate` e' il tetto vero — quante volte si chiama PageSpeed per una
    pagina, comunque le si distribuisca. Con due giri ciascuno ha un tentativo
    solo, perche' il secondo giro **fa gia' da riprova**: se il primo torna un
    500 transitorio, il secondo ci riprova comunque. Con un giro solo i due
    tentativi restano dentro quel giro.
    """
    psi_chiamate: int = 2
    psi_timeout: float = 120.0
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

    def tentativi(self, giri: int = 1) -> int:
        """Quanti tentativi dentro un giro, sapendo quanti giri si faranno."""
        return max(1, self.psi_chiamate // max(1, giri))

    def giro_psi(self, giri: int = 1) -> float:
        """Il caso peggiore di UN giro, quando i giri in tutto saranno `giri`."""
        tentativi = self.tentativi(giri)
        return (tentativi * self.psi_timeout
                + self._backoff_totale(tentativi, self.psi_backoff))

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
        uno = self.giro_psi(giri)
        lab = uno if giri <= 1 else max(uno, self.psi_attesa_fra_giri) + uno * (giri - 1)
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
        # Nove numeri: sono il quadro di sintesi della nota tecnica, e senza di
        # loro dal browser quel documento uscirebbe senza tabella in testa.
        "metriche_lab": fatti.metriche_lab,
    }


def caricamento(fatti, url: str, domini_propri) -> dict:
    """Cio' che si vede del caricamento: fotogrammi, cascata, redirect, punteggi.

    Sta **fuori** da `fatti_essenziali` apposta. Il browser lo usa per disegnare
    e non lo rimanda indietro: i soli fotogrammi sono 250 KB a pagina, e a
    quaranta pagine sarebbero 10 MB contro i 4,5 del corpo di una richiesta.

    La cascata si calcola qui e non nel browser: le proporzioni sono le stesse
    del report HTML perche' le produce la stessa funzione, e non c'e' una
    seconda versione della logica da tenere allineata.
    """
    disegno = cascata.cascata(fatti.richieste, fatti.tempi_osservati, url, domini_propri)
    return {
        "tempi": fatti.tempi_osservati,
        "redirect": [asdict(salto) for salto in fatti.redirect],
        "filmstrip": [asdict(f) for f in fatti.filmstrip],
        "screenshot": asdict(fatti.screenshot) if fatti.screenshot else None,
        "categorie": [asdict(c) for c in fatti.categorie],
        "cascata": {
            "scala_ms": disegno.scala_ms,
            "riferimenti": [asdict(r) for r in disegno.riferimenti],
            "barre": [asdict(b) for b in disegno.barre],
        },
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
        tentativi=budget.tentativi(ripetizioni), attesa_iniziale=budget.psi_backoff,
        timeout=budget.psi_timeout)
    riuscite = [r for r in risposte[url] if not isinstance(r, Exception)]
    if not riuscite:
        fallita = next((r for r in risposte[url] if isinstance(r, Exception)), None)
        # Un ErroreSpeed porta gia' il suo rimedio: appiattirlo in un RuntimeError
        # lo perdeva per strada, e chi legge restava senza l'azione che risolve.
        if isinstance(fallita, ErroreSpeed):
            raise fallita
        raise RuntimeError(str(fallita).strip() if fallita and str(fallita).strip()
                           else "PageSpeed Insights non ha risposto")

    accordo = consenso.combina([extract.estrai(r, url, form_factor, domini_propri)
                                for r in riuscite])
    fatti = accordo.fatti
    riepilogo = thirdparty.riepiloga(fatti.richieste, url, domini_propri)
    problemi = diagnose.diagnostica(fatti, metriche, riepilogo, accordo)

    return {
        "template": url,
        "url": url,
        "fatti": fatti_essenziali(fatti),
        "caricamento": caricamento(fatti, url, domini_propri),
        "campo": voce_campo,
        "terze_parti": terze_essenziali(riepilogo),
        "peso_per_tipo": thirdparty.peso_per_tipo(fatti.richieste),
        "problemi": problemi,
        "misurazioni": accordo.ripetizioni,
        "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }
