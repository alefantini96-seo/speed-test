"""Configurazione per cliente: un file YAML, un URL per template."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errori import configurazione


@dataclass
class Template:
    nome: str
    url: str
    note: str = ""


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
        raise configurazione(f"{percorso}: un template ha campi non previsti.",
                             "Un template accetta solo `nome`, `url` e `note`.") from exc
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
