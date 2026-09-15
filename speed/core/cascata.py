"""
La cascata delle richieste: dai fatti di `network-requests` alle proporzioni da
disegnare.

Funzioni pure come tutto core/: qui si calcolano posizione e larghezza di ogni
barra, il disegno lo fanno i due renderer — il report HTML e l'interfaccia web —
che partono dalle stesse percentuali e quindi mostrano lo stesso grafico.

Due avvertenze valgono per chi legge il grafico, e i renderer le stampano:

- i tempi sono quelli **osservati** sul trace, non le metriche che Lighthouse
  riporta, che sono simulate con throttling e vivono su un'altra scala. E' la
  stessa cautela gia' dichiarata per le fasi dell'LCP;
- Lighthouse misura da un data center Google. La cascata dice in quale **ordine**
  la pagina si carica e cosa aspetta cosa; quanto ci mette un utente vero lo dice
  il campo (ADR-001).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .thirdparty import _propri, e_prima_parte


@dataclass
class Barra:
    """Una richiesta sulla linea del tempo, gia' in percentuale della scala."""
    nome: str
    url: str
    host: str
    tipo: str
    entita: str
    terza_parte: bool
    stato: int
    protocollo: str
    priorita: str
    byte: int
    inizio_ms: float      # quando e' partita in rete
    coda_ms: float        # quanto e' rimasta ferma prima di partire
    durata_ms: float
    inizio_pc: float      # dove comincia la barra, 0-100 della scala
    coda_pc: float
    durata_pc: float
    completa: bool = True

    @property
    def fine_ms(self) -> float:
        return self.inizio_ms + self.durata_ms


@dataclass
class Riferimento:
    etichetta: str
    ms: float
    pc: float


@dataclass
class Cascata:
    barre: list = field(default_factory=list)
    riferimenti: list = field(default_factory=list)
    scala_ms: float = 0.0

    @property
    def quante(self) -> int:
        return len(self.barre)


def nome_file(url: str) -> str:
    """L'ultimo pezzo del percorso, che e' come chi sviluppa chiama un file.

    Senza percorso resta l'host: la richiesta al documento di una home si legge
    "www.esempio.it/", non una riga vuota.
    """
    pezzi = urlparse(url)
    coda = [p for p in pezzi.path.split("/") if p]
    if not coda:
        return f"{pezzi.netloc}/"
    nome = coda[-1]
    return f"{nome}?…" if pezzi.query else nome


def cascata(richieste: list, tempi_osservati: dict | None = None,
            url_pagina: str = "", domini_propri=()) -> Cascata:
    """Le richieste ordinate nel tempo, con i riferimenti del caricamento.

    Le richieste **vanno ordinate qui**: `network-requests` le consegna quasi in
    ordine ma non del tutto — due inversioni su 126 in una risposta reale.

    La scala arriva all'ultimo evento, richiesta o riferimento che sia: un
    "ultimo cambio visivo" oltre il bordo del grafico non si potrebbe leggere.
    """
    if not richieste:
        return Cascata()

    propri = _propri(url_pagina, domini_propri) if url_pagina else set()
    in_ordine = sorted(richieste, key=lambda r: (r.partita, r.finita))
    tempi = tempi_osservati or {}

    scala = max([r.finita for r in in_ordine] + [v for v in tempi.values() if v] + [1.0])

    barre = []
    for r in in_ordine:
        coda = r.coda if 0 < r.chiesta < r.partita else 0.0
        barre.append(Barra(
            nome=nome_file(r.url),
            url=r.url,
            host=r.host,
            tipo=r.tipo,
            entita=r.entita,
            terza_parte=bool(propri) and not e_prima_parte(r.host, propri),
            stato=r.stato,
            protocollo=r.protocollo,
            priorita=r.priorita,
            byte=r.byte,
            inizio_ms=r.partita,
            coda_ms=coda,
            durata_ms=r.durata,
            inizio_pc=(r.partita - coda) / scala * 100,
            coda_pc=coda / scala * 100,
            durata_pc=r.durata / scala * 100,
            completa=r.completa,
        ))

    riferimenti = [Riferimento(etichetta=et, ms=float(ms), pc=float(ms) / scala * 100)
                   for et, ms in tempi.items() if ms]
    riferimenti.sort(key=lambda x: x.ms)
    return Cascata(barre=barre, riferimenti=riferimenti, scala_ms=scala)


def piu_lente(casc: Cascata, quante: int = 5) -> list:
    """Le richieste che hanno occupato la rete piu' a lungo.

    Nel report stampato la cascata si legge male oltre le prime decine di righe:
    questa lista e' la stessa informazione senza il grafico, ed e' l'ordinamento
    per durata che i tool con l'interfaccia interattiva offrono come bottone.
    """
    return sorted(casc.barre, key=lambda b: -b.durata_ms)[:quante]
