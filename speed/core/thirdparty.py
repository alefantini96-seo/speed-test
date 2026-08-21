"""
Aggregazione delle richieste di rete, e separazione first / third party.

Perche' in casa e non da Lighthouse: l'audit `third-parties-insight` restituisce
score=1 e tabella vuota anche su pagine con 1,3 MB di terze parti. La lista
`network-requests` invece e' affidabile, e porta con se' un campo `entity` che
Lighthouse usa per dare un nome ai provider noti — "Optimizely" al posto di tre
host separati, "Google/Doubleclick Ads" al posto di `pagead2.googlesyndication.com`.
Quel nome lo usiamo; l'attribuzione first/third no.

Il motivo e' che l'attribuzione automatica sbaglia sui domini fratelli. Su bbc.com
gli asset stanno su `bbci.co.uk`: dominio registrabile diverso, stessa
organizzazione. Sia la regola sul dominio sia il campo `entity` di Lighthouse li
classificano come terze parti, e il tool finirebbe per assegnare a "marketing/tag"
il CDN del cliente. Non esiste un modo automatico di saperlo: si dichiara nella
configurazione del cliente, con `domini_propri`.

Funzioni pure.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class Entita:
    nome: str                # nome del provider secondo Lighthouse, o l'host
    byte: int
    richieste: int
    terza_parte: bool
    host: tuple = ()         # host effettivi raggruppati sotto questo nome

    @property
    def kb(self) -> float:
        return self.byte / 1024


@dataclass
class RiepilogoTerzeParti:
    entita: list
    byte_totali: int
    byte_first: int
    byte_terzi: int
    richieste_totali: int

    @property
    def quota_terzi(self) -> float:
        return self.byte_terzi / self.byte_totali if self.byte_totali else 0.0

    def top(self, n: int = 10) -> list:
        return [e for e in self.entita if e.terza_parte][:n]


def dominio_registrabile(host: str) -> str:
    """Ultimi due label dell'host. Sufficiente per i domini che trattiamo
    (.it, .com); non gestisce i suffissi a due livelli tipo .co.uk, per i quali
    va usato `domini_propri` nella configurazione."""
    parti = [p for p in host.split(".") if p]
    return ".".join(parti[-2:]) if len(parti) >= 2 else host


def _propri(url_pagina: str, domini_propri) -> set:
    insieme = {dominio_registrabile(urlparse(url_pagina).netloc)}
    for dominio in domini_propri or ():
        pulito = dominio.strip().lower()
        if not pulito:
            continue
        # accetta sia "bbci.co.uk" sia "https://static.bbci.co.uk/"
        host = urlparse(pulito).netloc or pulito
        insieme.add(host)
        insieme.add(dominio_registrabile(host))
    return insieme


def e_prima_parte(host: str, propri: set) -> bool:
    host = host.lower()
    return host in propri or dominio_registrabile(host) in propri or \
        any(host.endswith("." + p) for p in propri)


def riepiloga(richieste: list, url_pagina: str, domini_propri=()) -> RiepilogoTerzeParti:
    """Raggruppa per entita' (nome Lighthouse quando c'e', altrimenti host)."""
    propri = _propri(url_pagina, domini_propri)
    gruppi: dict = {}

    for richiesta in richieste:
        if not richiesta.host:
            continue
        nome = richiesta.entita or richiesta.host
        voce = gruppi.setdefault(nome, {"byte": 0, "richieste": 0, "host": set(),
                                        "byte_propri": 0})
        voce["byte"] += richiesta.byte
        voce["richieste"] += 1
        voce["host"].add(richiesta.host)
        if e_prima_parte(richiesta.host, propri):
            voce["byte_propri"] += richiesta.byte

    entita = []
    for nome, voce in gruppi.items():
        # Un'entita' e' di prima parte se la maggior parte del suo peso lo e'.
        prima = voce["byte_propri"] * 2 >= voce["byte"] if voce["byte"] else \
            all(e_prima_parte(h, propri) for h in voce["host"])
        entita.append(Entita(nome=nome, byte=voce["byte"], richieste=voce["richieste"],
                             terza_parte=not prima, host=tuple(sorted(voce["host"]))))
    entita.sort(key=lambda e: -e.byte)

    byte_totali = sum(e.byte for e in entita)
    byte_terzi = sum(e.byte for e in entita if e.terza_parte)
    return RiepilogoTerzeParti(
        entita=entita,
        byte_totali=byte_totali,
        byte_first=byte_totali - byte_terzi,
        byte_terzi=byte_terzi,
        richieste_totali=sum(e.richieste for e in entita),
    )


def peso_per_tipo(richieste: list) -> dict:
    out: dict = {}
    for richiesta in richieste:
        out[richiesta.tipo] = out.get(richiesta.tipo, 0) + richiesta.byte
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
