"""
Confronto fra due scansioni: cosa e' cambiato, e quanto ci si puo' fidare.

Due avvertenze governano la lettura di questo confronto, e vanno nell'OUTPUT e non
solo nel codice — chi legge il risultato non apre il sorgente:

1. **Il campo e' una media mobile a 28 giorni.** Un intervento pubblicato oggi
   entra nei numeri gradualmente e si legge pulito solo dopo quattro settimane.
   Un confronto a distanza di una settimana da un rilascio non dice niente.
2. **I problemi confrontati vengono dal laboratorio, che oscilla fra run.** La
   comparsa o la scomparsa di una singola opportunita' non e' di per se' un
   risultato: puo' essere rumore di misura. Il movimento del p75 di campo si'.

Lo storico non serve accumularlo: CrUX History restituisce 40 settimane a ogni
esecuzione, quindi l'andamento lungo sta gia' dentro ciascuna delle due scansioni.

Funzioni pure: si parte dalla forma JSON di due run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .soglie import CWV, ETICHETTE, SOGLIE, formatta, giudizio

AVVERTENZE = (
    "Il campo e' una media mobile a 28 giorni: un intervento pubblicato oggi si "
    "legge pulito solo dopo quattro settimane.",
    "I problemi confrontati vengono dal laboratorio, che oscilla fra una "
    "misurazione e l'altra: la comparsa o la scomparsa di una singola opportunita' "
    "non e' di per se' un risultato. Il movimento del p75 di campo si'.",
)

# Sotto questa variazione relativa il movimento non si commenta: sarebbe rumore
# spacciato per risultato.
SOGLIA_MOVIMENTO = 0.05


@dataclass
class MovimentoMetrica:
    metrica: str
    prima: float | None
    dopo: float | None

    @property
    def delta(self) -> float | None:
        if self.prima is None or self.dopo is None:
            return None
        return self.dopo - self.prima

    @property
    def verso(self) -> str:
        """migliorato | peggiorato | stabile | sconosciuto. Per tutte le metriche
        di velocita' un valore piu' basso e' migliore."""
        if self.delta is None or not self.prima:
            return "sconosciuto"
        if abs(self.delta) / self.prima < SOGLIA_MOVIMENTO:
            return "stabile"
        return "migliorato" if self.delta < 0 else "peggiorato"

    @property
    def cambia_giudizio(self) -> bool:
        return (giudizio(self.metrica, self.prima) != giudizio(self.metrica, self.dopo)
                and self.prima is not None and self.dopo is not None)

    def descrivi(self) -> str:
        if self.prima is None or self.dopo is None:
            return f"{ETICHETTE[self.metrica]}: dato mancante in una delle due scansioni"
        unita = "" if SOGLIE[self.metrica].unita == "" else " ms"
        freccia = {"migliorato": "->", "peggiorato": "->", "stabile": "="}[self.verso]
        testo = (f"{ETICHETTE[self.metrica]} {formatta(self.metrica, self.prima)} "
                 f"{freccia} {formatta(self.metrica, self.dopo)}")
        if self.verso != "stabile":
            segno = "+" if self.delta > 0 else ""
            testo += f" ({segno}{self.delta:.3f}{unita})" if unita == "" else \
                     f" ({segno}{self.delta:.0f}{unita})"
        if self.cambia_giudizio:
            testo += (f" — da {giudizio(self.metrica, self.prima).replace('_', ' ')} "
                      f"a {giudizio(self.metrica, self.dopo).replace('_', ' ')}")
        return testo


@dataclass
class ConfrontoTemplate:
    template: str
    url: str
    spariti: list = field(default_factory=list)     # (codice, titolo)
    comparsi: list = field(default_factory=list)
    restati: list = field(default_factory=list)
    metriche: list = field(default_factory=list)    # MovimentoMetrica

    @property
    def qualcosa_e_cambiato(self) -> bool:
        return bool(self.spariti or self.comparsi
                    or any(m.verso in ("migliorato", "peggiorato") for m in self.metriche))


@dataclass
class Confronto:
    data_prima: str
    data_dopo: str
    template: list = field(default_factory=list)
    solo_prima: list = field(default_factory=list)   # template spariti dalla config
    solo_dopo: list = field(default_factory=list)


def _per_url(esecuzione: dict) -> dict:
    """Le pagine indicizzate per URL: il nome del template puo' essere cambiato,
    l'indirizzo no — e' quello che identifica la stessa misurazione."""
    return {p["url"]: p for p in esecuzione.get("pagine", []) if p.get("url")}


def _problemi(pagina: dict) -> dict:
    return {p["codice"]: p.get("titolo", p["codice"])
            for p in pagina.get("problemi") or []}


def _metriche(pagina: dict) -> dict:
    return (pagina.get("campo") or {}).get("metriche") or {}


def confronta(prima: dict, dopo: dict) -> Confronto:
    pagine_prima, pagine_dopo = _per_url(prima), _per_url(dopo)
    comuni = [u for u in pagine_dopo if u in pagine_prima]

    risultato = Confronto(
        data_prima=prima.get("data", "?"),
        data_dopo=dopo.get("data", "?"),
        solo_prima=[pagine_prima[u].get("template", u) for u in pagine_prima
                    if u not in pagine_dopo],
        solo_dopo=[pagine_dopo[u].get("template", u) for u in pagine_dopo
                   if u not in pagine_prima],
    )

    for url in comuni:
        vecchia, nuova = pagine_prima[url], pagine_dopo[url]
        p_vecchi, p_nuovi = _problemi(vecchia), _problemi(nuova)
        m_vecchie, m_nuove = _metriche(vecchia), _metriche(nuova)

        risultato.template.append(ConfrontoTemplate(
            template=nuova.get("template", url),
            url=url,
            spariti=[(c, t) for c, t in p_vecchi.items() if c not in p_nuovi],
            comparsi=[(c, t) for c, t in p_nuovi.items() if c not in p_vecchi],
            restati=[(c, t) for c, t in p_nuovi.items() if c in p_vecchi],
            metriche=[MovimentoMetrica(metrica=m, prima=m_vecchie.get(m),
                                       dopo=m_nuove.get(m))
                      for m in CWV
                      if m in m_vecchie or m in m_nuove],
        ))
    return risultato
