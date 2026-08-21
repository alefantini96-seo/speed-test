"""
Consenso fra piu' misurazioni della stessa pagina.

Perche' esiste questo modulo. Su misurazioni indipendenti della stessa URL la
ripartizione dell'LCP in fasi si e' mossa cosi':

    resourceLoadDelay:  260 ms   1204 ms   1238 ms   3118 ms

Un fattore dodici. La fase dominante decide chi deve intervenire: dichiararla da
una sola misurazione significa presentare come fatto qualcosa che non lo e'.

Due trappole, entrambe verificate sul campo:

1. **PSI restituisce risultati dalla cache.** Tre chiamate ravvicinate hanno dato
   tre risposte identiche al millisecondo, stesso `analysisUTCTimestamp`. Contarle
   come tre misurazioni concordi sarebbe una falsa sicurezza: qui si deduplica per
   timestamp, e il conteggio riporta solo le misurazioni davvero distinte.
2. **La dispersione va detta.** Anche con misurazioni indipendenti lo scarto resta
   ampio, quindi riportiamo minimo e massimo della fase dominante e non solo la
   mediana.

Cosa e' stabile e cosa no, verificato sugli stessi run:

| dato                                    | stabile |
|-----------------------------------------|---------|
| elemento LCP (selettore, snippet)       | si'     |
| checklist di scopribilita' (lazy, ecc.) | si'     |
| durate e proporzioni delle fasi         | NO      |

Funzioni pure.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from statistics import median

from .extract import FASI_LCP, FattiPagina


@dataclass
class Consenso:
    fatti: FattiPagina                  # misurazione rappresentativa
    ripetizioni: int = 1                # misurazioni DISTINTE (dedotte per timestamp)
    richieste: int = 1                  # chiamate effettuate, cache inclusa
    fasi_mediane: dict = field(default_factory=dict)
    fase_dominante: str = ""
    concordi: int = 0
    dispersione: tuple = (0.0, 0.0)     # min e max della fase dominante
    elemento_stabile: bool = True
    checklist_stabile: bool = True

    @property
    def cache_rilevata(self) -> bool:
        return self.richieste > self.ripetizioni

    @property
    def attendibile(self) -> bool:
        """Serve piu' di una misurazione distinta, e la maggioranza d'accordo."""
        return self.ripetizioni > 1 and self.concordi * 2 > self.ripetizioni

    @property
    def descrizione(self) -> str:
        if self.ripetizioni == 1:
            testo = ("Una sola misurazione di laboratorio distinta: la ripartizione in "
                     "fasi dell'LCP varia molto fra run, quindi la fase dominante qui e' "
                     "indicativa e non un risultato consolidato.")
            if self.cache_rilevata:
                testo += (f" Delle {self.richieste} chiamate effettuate, PSI ne ha servite "
                          f"{self.richieste - self.ripetizioni} dalla cache: non sono "
                          f"misurazioni aggiuntive.")
            return testo

        testo = (f"{self.concordi} misurazioni distinte su {self.ripetizioni} concordano "
                 f"sulla fase dominante; i valori riportati sono la mediana.")
        minimo, massimo = self.dispersione
        if massimo > 0:
            testo += (f" La fase dominante ha oscillato fra {minimo:.0f} e {massimo:.0f} ms "
                      f"fra le misurazioni: l'ordine di grandezza e' indicativo, la "
                      f"classificazione della fase no.")
        if self.cache_rilevata:
            testo += (f" {self.richieste - self.ripetizioni} chiamate su {self.richieste} "
                      f"sono state servite dalla cache di PSI e non contano.")
        if not self.attendibile:
            testo += (" Le misurazioni NON concordano: la fase dominante non e' un "
                      "risultato affidabile e l'attribuzione della responsabilita' va "
                      "presa con cautela.")
        return testo


def _dominante(fasi: dict) -> str:
    return max(fasi, key=fasi.get) if fasi else ""


def deduplica(misurazioni: list) -> list:
    """Scarta le risposte servite dalla cache: stesso analysisUTCTimestamp.

    Le misurazioni senza timestamp (fixture di test) vengono tenute tutte.
    """
    viste, distinte = set(), []
    for m in misurazioni:
        if not m.timestamp:
            distinte.append(m)
            continue
        if m.timestamp in viste:
            continue
        viste.add(m.timestamp)
        distinte.append(m)
    return distinte


def combina(misurazioni: list) -> Consenso:
    """Una o piu' FattiPagina della stessa URL -> misurazione rappresentativa."""
    ricevute = [m for m in misurazioni if m is not None]
    if not ricevute:
        raise ValueError("nessuna misurazione")
    distinte = deduplica(ricevute)

    if len(distinte) == 1:
        solo = distinte[0]
        return Consenso(fatti=solo, ripetizioni=1, richieste=len(ricevute),
                        fasi_mediane=dict(solo.lcp_fasi),
                        fase_dominante=_dominante(solo.lcp_fasi), concordi=1)

    con_fasi = [m for m in distinte if m.lcp_fasi]
    mediane = {}
    for fase in FASI_LCP:
        valori = [m.lcp_fasi.get(fase, 0.0) for m in con_fasi]
        if valori:
            mediane[fase] = float(median(valori))

    dominante = _dominante(mediane)
    concordi = sum(1 for m in con_fasi if _dominante(m.lcp_fasi) == dominante)
    osservate = [m.lcp_fasi.get(dominante, 0.0) for m in con_fasi] or [0.0]

    candidate = [m for m in con_fasi if _dominante(m.lcp_fasi) == dominante] or con_fasi
    candidate.sort(key=lambda m: sum(m.lcp_fasi.values()))
    # Copia con le fasi sostituite dalle mediane, non mutazione dell'originale:
    # era l'unica funzione del core dichiarata pura che modificava un oggetto
    # ricevuto in ingresso, e chi passava le sue misurazioni se le ritrovava
    # cambiate sotto i piedi.
    rappresentativa = replace(candidate[len(candidate) // 2], lcp_fasi=dict(mediane))

    elementi = {m.lcp_elemento_snippet for m in distinte if m.lcp_elemento_snippet}
    checklist = {tuple(sorted(m.lcp_discovery.items())) for m in distinte if m.lcp_discovery}

    return Consenso(
        fatti=rappresentativa,
        ripetizioni=len(distinte),
        richieste=len(ricevute),
        fasi_mediane=mediane,
        fase_dominante=dominante,
        concordi=concordi,
        dispersione=(min(osservate), max(osservate)),
        elemento_stabile=len(elementi) <= 1,
        checklist_stabile=len(checklist) <= 1,
    )
