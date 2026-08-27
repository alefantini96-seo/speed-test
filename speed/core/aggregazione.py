"""
Interventi raggruppati per tipo, non ripetuti per template.

Misurato su una scansione reale a tre template: 10 interventi su 13 comparivano su
tutti e tre, cioe' **20 schede su 37 erano ripetizioni dello stesso titolo**.

Ma i file su cui mettere mano quasi non coincidono. Sulle liste complete di
risorse, non troncate:

    legacy-javascript    3 file in comune su  7   (43%)
    bootup-time          3 su 15                  (20%)
    cache-insight        5 su 27                  (19%)
    unused-javascript    1 su 18                  ( 6%)
    image-delivery       0 su 19                  ( 0%)

E' il comportamento normale di un sito con il codice splittato per rotta: ogni
pagina carica bundle diversi, e le immagini sono contenuto della pagina.

Da qui la forma: **il titolo si dice una volta, i bersagli si raggruppano per
template**. E i file presenti su TUTTI i template dove l'intervento compare si
marcano a parte: sono il bundle comune, e sistemarli una volta vale per tutto il
sito, mentre gli altri sono lavoro per pagina. E' la differenza fra un intervento
e tre.

I Core Web Vitals restano per template: sono numeri diversi per pagina, ed e'
tutto il motivo per cui si misurano i template invece del solo dominio.

Funzioni pure: si parte dalla forma JSON di un run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ORDINE_GRAVITA = {"alta": 0, "media": 1, "bassa": 2}


@dataclass
class PerTemplate:
    nome: str
    url: str
    bersagli: list = field(default_factory=list)   # (nome, misura, dettaglio) — resa
    tutti: list = field(default_factory=list)      # (nome, misura, dettaglio) — confronto


# Le tre forme in cui un problema nomina cio' su cui si mette mano. `bersagli` e'
# gia' la lista corta per la resa (3 voci); `risorse` ed `elementi` ne conservano
# sei ciascuno, con gli stessi nomi, e sono gia' nel JSON: non costano payload.
def _voci_confrontabili(problema: dict) -> list:
    """(nome, misura, dettaglio) per ogni bersaglio noto del problema, senza tagli.

    L'intersezione fra template va fatta qui e non su `bersagli`: quella e' la
    lista troncata a 3, e su tre voci due template non hanno quasi mai un file in
    comune — il bundle condiviso spariva dal report proprio dove c'era.

    Restano fuori le voci senza URL ne' nodo (un vendor, una catena di richieste):
    per quelle il JSON conserva solo i primi tre bersagli, ed e' quanto si puo'
    confrontare. E le righe il cui nome non e' una stringa: la constatazione sulle
    terze parti raggruppa piu' host in una riga sola e li' mette una lista.
    """
    voci, viste = [], set()

    def aggiungi(nome, misura, dettaglio):
        if not isinstance(nome, str) or not nome or nome in viste:
            return
        viste.add(nome)
        voci.append((nome, misura or "", dettaglio or ""))

    for bersaglio in problema.get("bersagli") or []:
        nome, misura, dettaglio = (list(bersaglio) + ["", "", ""])[:3]
        aggiungi(nome, misura, dettaglio)
    for risorsa in problema.get("risorse") or []:
        url, misura = (list(risorsa) + ["", ""])[:2]
        if isinstance(url, str):
            aggiungi(url.split("?")[0].rsplit("/", 1)[-1] or url, misura, url)
    for elemento in problema.get("elementi") or []:
        riferimento, misura, percorso = (list(elemento) + ["", "", ""])[:3]
        aggiungi(riferimento, misura, percorso)
    return voci


@dataclass
class Intervento:
    codice: str
    titolo: str
    gravita: str
    responsabile: str
    fonte: str = "lighthouse"
    guadagno: str = ""
    guadagno_tipo: str = ""
    azioni: list = field(default_factory=list)
    evidenza: list = field(default_factory=list)
    nota: str = ""
    documentazione: str = ""
    azionabile: bool = True
    template: list = field(default_factory=list)   # PerTemplate
    totale_template: int = 0

    @property
    def quanti(self) -> int:
        return len(self.template)

    @property
    def comuni(self) -> list:
        """I bersagli presenti su ogni template dove l'intervento compare.

        Sono il bundle condiviso: sistemarli una volta vale per tutto il sito.
        Con un solo template la nozione non ha senso e resta vuota.

        Si intersecano le liste complete (`tutti`), non quelle di resa: la misura
        che giustifica questa funzione — dal 43% allo 0% di sovrapposizione fra
        template — e' su liste complete, e su liste da tre l'intersezione e' quasi
        sempre vuota. Il troncamento e' compito di chi impagina.
        """
        if self.quanti < 2:
            return []
        insiemi = [{b[0] for b in t.tutti} for t in self.template]
        if not all(insiemi):
            return []
        comuni = set.intersection(*insiemi)
        # Si conserva l'ordine del primo template: e' gia' per impatto decrescente.
        return [b[0] for b in self.template[0].tutti if b[0] in comuni]

    def propri_di(self, template: PerTemplate) -> list:
        """I bersagli specifici di un template: quelli non condivisi con gli altri."""
        comuni = set(self.comuni)
        return [b for b in template.bersagli if b[0] not in comuni]

    def misura_di(self, nome: str) -> tuple:
        """Nome, misura e dettaglio di un bersaglio, cercato ovunque sia noto.

        Cerca in `tutti` e non nella lista di resa: un file comune puo' stare oltre
        il terzo posto su ogni template, ed e' proprio il caso che `comuni` serve
        a trovare. Cercandolo solo fra i primi tre uscirebbe senza impatto.
        """
        for t in self.template:
            for bersaglio in t.tutti:
                if bersaglio[0] == nome:
                    return tuple(bersaglio)
        return (nome, "", "")


def raggruppa(esecuzione: dict) -> list:
    """Le pagine di un run -> un intervento per tipo, ordinato per priorita'."""
    pagine = [p for p in esecuzione.get("pagine", []) if not p.get("errore")]
    totale = len(pagine)
    gruppi: dict = {}

    for pagina in pagine:
        nome = pagina.get("template") or pagina.get("url", "")
        for problema in pagina.get("problemi") or []:
            codice = problema.get("codice", "")
            intervento = gruppi.get(codice)
            if intervento is None:
                intervento = Intervento(
                    codice=codice,
                    titolo=problema.get("titolo", codice),
                    gravita=problema.get("gravita", "bassa"),
                    responsabile=problema.get("responsabile", ""),
                    fonte=problema.get("fonte", "lighthouse"),
                    guadagno=problema.get("guadagno", ""),
                    guadagno_tipo=problema.get("guadagno_tipo", ""),
                    azioni=list(problema.get("azioni") or []),
                    evidenza=list(problema.get("evidenza") or []),
                    nota=problema.get("nota", ""),
                    documentazione=problema.get("documentazione", ""),
                    azionabile=problema.get("azionabile", True),
                    totale_template=totale,
                )
                gruppi[codice] = intervento
            else:
                # Fra due template vale la gravita' peggiore e il guadagno piu' alto
                # gia' calcolato: si sta descrivendo un intervento solo.
                if ORDINE_GRAVITA.get(problema.get("gravita"), 3) < \
                        ORDINE_GRAVITA.get(intervento.gravita, 3):
                    intervento.gravita = problema.get("gravita", intervento.gravita)
                if not intervento.guadagno and problema.get("guadagno"):
                    intervento.guadagno = problema["guadagno"]
                    intervento.guadagno_tipo = problema.get("guadagno_tipo", "")

            intervento.template.append(PerTemplate(
                nome=nome, url=pagina.get("url", ""),
                bersagli=[tuple(b) for b in (problema.get("bersagli") or [])],
                tutti=_voci_confrontabili(problema)))

    lista = list(gruppi.values())
    # Prima cio' che il campo dice piu' grave, poi cio' che tocca piu' template.
    lista.sort(key=lambda i: (ORDINE_GRAVITA.get(i.gravita, 3), -i.quanti, i.titolo))
    return lista
