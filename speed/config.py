"""Configurazione per cliente: un file YAML, un URL per template."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


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
    dati = yaml.safe_load(Path(percorso).read_text(encoding="utf-8"))
    template = [Template(**t) for t in dati.get("template", [])]
    if not template:
        raise ValueError(f"{percorso}: nessun template definito")
    doppi = {t.url for t in template}
    if len(doppi) != len(template):
        raise ValueError(f"{percorso}: URL duplicati fra i template")
    return Config(
        cliente=dati["cliente"],
        sito=dati["sito"],
        template=template,
        form_factor=dati.get("form_factor", "PHONE"),
        output=dati.get("output", ""),
        domini_propri=dati.get("domini_propri") or [],
    )
