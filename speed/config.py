"""Configurazione per cliente: un file YAML, un URL per template."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errori import configurazione


@dataclass
class Template:
    """Un template del sito, rappresentato da una pagina.

    `sessioni` e `quota_traffico` sono alternativi e facoltativi: servono a pesare
    l'ordine degli interventi. Senza, tutti i template pesano uguale — che e' il
    comportamento storico, ed e' il difetto piu' vistoso di un master plan: un
    template da 200.000 sessioni e uno da 400 producono lo stesso ordine.
    """
    nome: str
    url: str
    note: str = ""
    sessioni: float | None = None          # valore assoluto, qualunque unita' coerente
    quota_traffico: float | None = None    # frazione del traffico del sito (0-1)

    @property
    def traffico(self) -> float | None:
        """Il valore grezzo di traffico, comunque sia stato dichiarato."""
        if self.sessioni is not None:
            return float(self.sessioni)
        if self.quota_traffico is not None:
            return float(self.quota_traffico)
        return None


@dataclass
class Config:
    cliente: str
    sito: str
    template: list
    form_factor: str = "PHONE"        # PHONE | DESKTOP
    output: str = ""                  # cartella di destinazione dei report
    domini_propri: list = None         # domini del cliente serviti da host diversi

    def __post_init__(self):
        if self.domini_propri is None:
            self.domini_propri = []

    @property
    def strategy(self) -> str:
        return "desktop" if self.form_factor == "DESKTOP" else "mobile"

    @property
    def urls(self) -> list:
        return [t.url for t in self.template]

    def template_per_url(self, url: str) -> str:
        for t in self.template:
            if t.url == url:
                return t.nome
        return url

    @property
    def traffico_dichiarato(self) -> bool:
        return any(t.traffico is not None for t in self.template)

    def pesi(self) -> dict:
        """{url: peso 0-1}, normalizzato sul template piu' trafficato.

        Il peso moltiplica la gravita' nell'ordinamento degli interventi. La
        normalizzazione e' sul MASSIMO e non sulla somma: cosi' il template
        principale vale 1 e gli altri una frazione di quello, che e' come si legge
        un master plan — "quanto conta rispetto alla pagina che conta di piu'".

        Senza traffico dichiarato tutti valgono 1: l'ordine resta identico a prima,
        e il report dichiara che non e' pesato.

        Un template senza traffico dichiarato in un file dove gli altri ce l'hanno
        prende 1: meglio sovrastimarlo e vederlo in cima che perderlo in fondo per
        un dato che manca.
        """
        valori = [t.traffico for t in self.template if t.traffico is not None]
        if not valori:
            return {t.url: 1.0 for t in self.template}
        massimo = max(valori) or 1.0
        return {t.url: (t.traffico / massimo) if t.traffico is not None else 1.0
                for t in self.template}


def carica(percorso: str | Path) -> Config:
    """Legge il YAML di un cliente.

    Gli errori escono come ErroreSpeed con il rimedio dentro: un file di
    configurazione sbagliato lo scrive una persona, e un KeyError secco non le
    dice quale chiave manca ne' dove.
    """
    file = Path(percorso)
    if not file.exists():
        raise configurazione(f"il file {percorso} non esiste.",
                             "Vedi clienti/esempio.yaml per la struttura attesa.")
    try:
        dati = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise configurazione(f"{percorso} non e' un YAML valido.",
                             str(exc)[:200]) from exc
    if not isinstance(dati, dict):
        raise configurazione(f"{percorso} non contiene una mappa di chiavi.",
                             "Vedi clienti/esempio.yaml per la struttura attesa.")

    mancanti = [chiave for chiave in ("cliente", "sito") if not dati.get(chiave)]
    if mancanti:
        raise configurazione(f"{percorso}: manca {', '.join(mancanti)}.",
                             "Servono almeno `cliente`, `sito` e un `template`.")
    try:
        template = [Template(**t) for t in dati.get("template", [])]
    except TypeError as exc:
        raise configurazione(
            f"{percorso}: un template ha campi non previsti.",
            "Un template accetta `nome`, `url`, `note`, e in alternativa fra loro "
            "`sessioni` o `quota_traffico`.") from exc
    entrambi = [t.nome for t in template
                if t.sessioni is not None and t.quota_traffico is not None]
    if entrambi:
        raise configurazione(
            f"{percorso}: {', '.join(entrambi)} dichiara sia `sessioni` sia "
            f"`quota_traffico`.",
            "Sono alternativi: uno dei due, non tutti e due.")
    negativi = [t.nome for t in template
                if t.traffico is not None and t.traffico < 0]
    if negativi:
        raise configurazione(f"{percorso}: traffico negativo in {', '.join(negativi)}.",
                             "Il traffico e' un conteggio o una frazione: non puo' "
                             "essere negativo.")
    if not template:
        raise configurazione(f"{percorso}: nessun template definito.",
                             "Serve almeno una voce sotto `template`, con `nome` e `url`.")
    senza_url = [t.nome for t in template if not (t.url or "").startswith("http")]
    if senza_url:
        raise configurazione(f"{percorso}: URL mancante o non valido in "
                             f"{', '.join(senza_url)}.",
                             "Serve un indirizzo completo, che inizi con https://")
    doppi = {t.url for t in template}
    if len(doppi) != len(template):
        raise configurazione(f"{percorso}: due template puntano allo stesso URL.",
                             "Ogni template va misurato su una pagina diversa.")
    return Config(
        cliente=dati["cliente"],
        sito=dati["sito"],
        template=template,
        form_factor=dati.get("form_factor", "PHONE"),
        output=dati.get("output", ""),
        domini_propri=dati.get("domini_propri") or [],
    )
