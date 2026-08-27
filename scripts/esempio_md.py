"""
Rigenera l'esempio di documento tecnico committato in docs/.

    python scripts/esempio_md.py

L'esempio serve a vedere com'e' fatto il deliverable senza lanciare una scansione
e senza una chiave API: si compone dai fixture, con la stessa sequenza della CLI.
Un test verifica che il file committato sia allineato al renderer, quindi dopo
ogni modifica a render_md.py questo script va rilanciato.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from speed.cli import _serializza                      # noqa: E402
from speed.core import consenso, diagnose, extract, thirdparty   # noqa: E402
from speed.io import crux, render_md                   # noqa: E402

FIXTURES = RADICE / "fixtures"
DESTINAZIONE = RADICE / "docs" / "esempio-interventi-tecnici.md"

PROPRI = ["bbci.co.uk"]
TEMPLATE = (("Home", "https://www.bbc.com/", "psi-bbc-mobile-it.json"),
            ("Articolo", "https://www.bbc.com/news", "psi-bbc-mobile-it-2.json"))


def _carica(nome):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def _campo(url: str) -> dict:
    record = crux.leggi_record(_carica("crux-bbc.json"))
    storico = crux.leggi_storico(_carica("crux-history-bbc.json"))
    return {"livello": "url", "metriche": record["metriche"],
            "periodo_a": record["periodo_a"], "storico": {"url": url} | storico}


def esecuzione_di_prova() -> dict:
    """Un run a due template piu' una pagina fallita, dai soli fixture."""
    pagine = []
    for nome, url, fixture in TEMPLATE:
        accordo = consenso.combina([extract.estrai(_carica(fixture), url, "PHONE", PROPRI)])
        fatti = accordo.fatti
        campo = _campo(url)
        riepilogo = thirdparty.riepiloga(fatti.richieste, url, PROPRI)
        pagine.append({
            "template": nome, "url": url, "fatti": fatti, "campo": campo,
            "terze_parti": riepilogo,
            "peso_per_tipo": thirdparty.peso_per_tipo(fatti.richieste),
            "problemi": diagnose.diagnostica(fatti, campo["metriche"], riepilogo, accordo),
            "misurazioni": accordo.ripetizioni, "concordi": accordo.concordi,
            "consenso": accordo.descrizione,
        })
    # Una pagina fallita: nel documento dev'esserci, dichiarata, non sparita.
    pagine.append({"template": "Video", "url": "https://www.bbc.com/video",
                   "errore": "PageSpeed Insights: non e' riuscito ad analizzare la pagina."})

    esecuzione = {"cliente": "Esempio", "sito": "https://www.bbc.com",
                  "data": "2026-08-20", "form_factor": "PHONE",
                  "ordinamento_pesato": False, "pagine": pagine}
    return json.loads(json.dumps(esecuzione, default=_serializza, ensure_ascii=False))


def main() -> int:
    testo = render_md.markdown_report(esecuzione_di_prova())
    DESTINAZIONE.parent.mkdir(parents=True, exist_ok=True)
    DESTINAZIONE.write_text(testo, encoding="utf-8")
    print(f"  {DESTINAZIONE}  ({len(testo.splitlines())} righe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
