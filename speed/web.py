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

import asyncio
from dataclasses import asdict, dataclass, is_dataclass

import httpx

from .core import cascata, consenso, diagnose, extract, thirdparty
from .errori import ErroreSpeed
from .core.soglie import fasi_dal_campo
from .io import crux, psi

LIMITE_URL = 2048
LIMITE_PAGINE = 40
# Quanti concorrenti stanno in un confronto. Il tetto non e' tecnico - le
# chiamate costano 0,2 s l'una - ma di lettura: cinque colonne di numeri sono
# gia' il massimo che si legge senza scorrere, e un confronto che non si legge
# non fa decidere niente.
LIMITE_CONCORRENTI = 4


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

    **Il tetto vero e' il tempo, non il numero di chiamate.** La scadenza passata
    ai client la fa rispettare a ogni tentativo, quindi `psi_chiamate` non e' un
    budget ma un freno: quante volte al massimo ha senso insistere. Quattro,
    perche' i fallimenti rapidi costano poco - un errore di esecuzione di
    Lighthouse torna in una decina di secondi, e su una pagina vera che aveva
    appena fallito in produzione sei chiamate su sei sono poi riuscite - mentre
    le scadenze si mangiano il tempo da sole e la scadenza le ferma.

    Erano due, e due erano poche: sizeate sul costo di una scadenza, spendevano
    un tentativo intero anche per un errore che tornava in dieci secondi.
    """
    psi_chiamate: int = 4
    psi_timeout: float = 120.0
    # Quanto si lascia libero sotto il tetto della piattaforma: avvio a freddo,
    # rete, lettura del JSON (1,1 MB), estrazione e serializzazione della
    # risposta. E' anche il margine che la scadenza passata ai client rispetta.
    margine: float = 40.0
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

    def chiamate_per_giro(self, giri: int = 1) -> int:
        """Quanti tentativi al massimo dentro un giro, dati i giri che si faranno.

        Non e' una spartizione del tempo - quella la fa la scadenza - ma di
        quante volte insistere: su due giri non ha senso che il primo esaurisca
        da solo tutte le insistenze.
        """
        return max(1, self.psi_chiamate // max(1, giri))

    @property
    def campo(self) -> float:
        return (self.crux_tentativi * self.crux_timeout_record
                + self._backoff_totale(self.crux_tentativi, self.crux_backoff)
                + self.crux_tentativi_storico * self.crux_timeout_storico
                + self._backoff_totale(self.crux_tentativi_storico, self.crux_backoff))

    def peggior_caso(self) -> float:
        """Il tempo massimo di una analisi, in secondi.

        Non e' piu' una somma di previsioni ma il tetto stesso meno il margine:
        la scadenza che il percorso web passa ai client viene controllata **prima
        di ogni chiamata**, e una che sforerebbe non comincia. Con la somma il
        conto tornava solo finche' i tentativi erano pochi e tutti costosi;
        bastava ammetterne uno in piu' - per i fallimenti rapidi, che costano
        dieci secondi - e il numero diventava spaventoso senza che il
        comportamento cambiasse di un secondo.
        """
        return MAX_DURATA_VERCEL - self.margine


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
        # Poche righe di testo, e dicono quanto vale il resto del payload: senza,
        # i numeri di una misurazione che Lighthouse stesso ha marcato come
        # incerta arriverebbero indistinguibili dagli altri.
        "avvisi": fatti.avvisi,
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


# --------------------------------------------------------------------------- #
#  Gap competitor
#
#  Il confronto fra siti diversi si fa **sul campo e basta**. Il laboratorio
#  misura da un data center Google con throttling simulato: fra due misurazioni
#  della stessa pagina oscilla, e fra due siti diversi non dice niente di piu'
#  di quanto oscilla. Il campo invece e' cio' che gli utenti di ciascun sito
#  subiscono davvero (ADR-001), ed e' anche l'unica fonte che si puo' chiedere
#  per cinque URL in una richiesta sola: CrUX risponde in 0,2 s, PageSpeed in
#  40 e non ci starebbe nel tetto della piattaforma.
# --------------------------------------------------------------------------- #

async def campo_con_ripiego(client: httpx.AsyncClient, api_key: str, url: str,
                            form_factor: str, budget: Budget = BUDGET) -> dict:
    """Il campo di una pagina, e se non ce l'ha quello del suo dominio.

    Su un concorrente l'URL preciso spesso non ha traffico sufficiente mentre il
    dominio si': misurato il 15/09/2026, `coverflex.com` non aveva dati sulla
    home e li aveva sull'origine. Senza ripiego quel concorrente sparirebbe dal
    confronto pur essendo misurabile.

    Il ripiego pero' cambia **cosa** si sta guardando - il sito invece della
    pagina - quindi la voce lo dichiara in `livello` e chi disegna lo scrive.
    Prenderlo per un dato della pagina e' la stessa trappola dell'`origin_fallback`
    di PageSpeed.
    """
    for origine in (False, True):
        try:
            return await crux.record(
                client, api_key, url, form_factor, origin=origine,
                timeout=budget.crux_timeout_record,
                tentativi=budget.crux_tentativi,
                attesa_iniziale=budget.crux_backoff)
        except crux.CruxNonDisponibile:
            continue
    return {"url": url, "livello": "assente", "metriche": {}}


async def _voce_gap(client, api_key: str, url: str, form_factor: str,
                    budget: Budget) -> dict:
    """Una riga del confronto. Un URL che cade non fa cadere gli altri."""
    try:
        return await campo_con_ripiego(client, api_key, url, form_factor, budget)
    except Exception as guasto:
        return {"url": url, "livello": "errore", "metriche": {},
                "errore": str(guasto).strip() or type(guasto).__name__}


async def gap(api_key: str, url: str, concorrenti: list, form_factor: str = "PHONE",
              budget: Budget = BUDGET) -> dict:
    """La tua pagina e i concorrenti, sul campo, in una richiesta sola.

    In parallelo: sono letture, non misurazioni, e CrUX regge 150 richieste al
    minuto. Cinque URL misurati il 15/09/2026 in 0,9 secondi.
    """
    tutte = [url] + [c for c in concorrenti if c != url][:LIMITE_CONCORRENTI]
    async with httpx.AsyncClient() as client:
        pagine = await asyncio.gather(*(
            _voce_gap(client, api_key, u, form_factor, budget) for u in tutte))
    return {"form_factor": form_factor, "tua": url, "pagine": list(pagine)}


async def analizza_una(api_key: str, url: str, form_factor: str,
                       domini_propri: list, budget: Budget = BUDGET) -> dict:
    """Campo + laboratorio + diagnosi per una singola pagina.

    Il budget e' esplicito e viene passato ai client: senza, il caso peggiore
    superava il tetto di durata della piattaforma e l'utente vedeva un 504
    anonimo al posto dell'errore con rimedio.
    """
    orologio = asyncio.get_event_loop().time
    inizio = orologio()

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

    # Quanto resta davvero, non quanto era previsto: il campo ha gia' consumato
    # la sua parte, e una riprova che sfora il tetto fa uccidere la funzione
    # dalla piattaforma invece di consegnare l'errore con il rimedio.
    strategy = "desktop" if form_factor == "DESKTOP" else "mobile"
    risposte = await psi.analizza_molte(
        api_key, [url], strategy, ripetizioni=ripetizioni,
        attesa_fra_giri=budget.psi_attesa_fra_giri,
        chiamate=budget.chiamate_per_giro(ripetizioni),
        attesa_iniziale=budget.psi_backoff,
        timeout=budget.psi_timeout,
        secondi=MAX_DURATA_VERCEL - budget.margine - (orologio() - inizio))
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
