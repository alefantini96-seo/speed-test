"""
Test del contratto fra browser e server nella versione online.

L'endpoint restituisce una versione ridotta dei fatti: il browser deve rimandarla
indietro per generare il Word, e il corpo di una richiesta Vercel non puo' superare
i 4,5 MB. Se qualcuno aggiunge un campo al report senza aggiungerlo alla riduzione,
il documento esce mutilo: questi test lo intercettano.
"""
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest
from docx import Document

from speed.core import consenso, diagnose, extract, thirdparty
from speed.io import crux, render, render_docx

RADICE = Path(__file__).resolve().parent.parent
FIXTURES = RADICE / "fixtures"
URL = "https://www.bbc.com/"
PROPRI = ["bbci.co.uk"]


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location("analizza", RADICE / "api" / "analizza.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def pagina(api):
    """Compone la risposta dell'endpoint dai fixture, senza toccare la rete."""
    misurazioni = [
        extract.estrai(json.loads((FIXTURES / nome).read_text(encoding="utf-8")),
                       URL, "PHONE", PROPRI)
        for nome in ("psi-bbc-mobile-it.json", "psi-bbc-mobile-it-2.json")
    ]
    accordo = consenso.combina(misurazioni)
    fatti = accordo.fatti
    campo = crux.leggi_record(json.loads((FIXTURES / "crux-bbc.json").read_text(encoding="utf-8")))
    storico = crux.leggi_storico(
        json.loads((FIXTURES / "crux-history-bbc.json").read_text(encoding="utf-8")))
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    problemi = diagnose.diagnostica(fatti, campo["metriche"], riepilogo, accordo)

    risposta = {
        "template": URL, "url": URL,
        "fatti": api._fatti_essenziali(fatti),
        "campo": {"livello": "url", "metriche": campo["metriche"],
                  "storico": {"url": URL} | storico},
        "terze_parti": api._terze_essenziali(riepilogo),
        "problemi": problemi,
        "misurazioni": accordo.ripetizioni, "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }
    # Come arriva al browser e come torna indietro: passata da JSON.
    return json.loads(json.dumps(risposta, default=api._serializza, ensure_ascii=False))


def _esecuzione(pagina):
    return {"cliente": "bbc.com", "sito": URL, "data": date.today().isoformat(),
            "form_factor": "PHONE", "pagine": [pagina]}


def test_il_payload_resta_piccolo(pagina):
    peso = len(json.dumps(pagina, ensure_ascii=False).encode("utf-8"))
    assert peso < 40_000, "oltre questa soglia 40 pagine sfondano il limite di Vercel"


def test_la_riduzione_non_porta_le_liste_pesanti(pagina):
    for scartato in ("richieste", "opportunita", "risparmi", "campo_psi"):
        assert scartato not in pagina["fatti"], f"{scartato} non serve a valle: va scartato"


def test_la_riduzione_conserva_cio_che_serve_al_report(pagina):
    for necessario in ("lcp_fasi", "lcp_elemento_snippet", "performance_score"):
        assert necessario in pagina["fatti"]
    for necessario in ("byte_totali", "byte_terzi", "richieste_totali"):
        assert necessario in pagina["terze_parti"]


def test_le_risorse_colpevoli_sopravvivono_dentro_i_problemi(pagina):
    """Le richieste di rete si scartano, ma i file da sistemare devono restare."""
    con_risorse = [p for p in pagina["problemi"] if p.get("risorse")]
    assert con_risorse, "senza risorse il report non e' azionabile"
    url, misura, _terza = con_risorse[0]["risorse"][0]
    assert url.startswith("http") and misura


def test_il_word_si_genera_dal_payload_ridotto(pagina, tmp_path):
    percorso = render_docx.docx_report(_esecuzione(pagina), tmp_path / "r.docx")
    doc = Document(str(percorso))
    testo = "\n".join(p.text for p in doc.paragraphs)
    for tabella in doc.tables:
        for riga in tabella.rows:
            testo += "\n" + " | ".join(c.text for c in riga.cells)
    for atteso in ("p75 reale", "Dove si perde il tempo dell'LCP", "Interventi",
                   "testo di Lighthouse", "Peso della pagina"):
        assert atteso in testo, f"manca nel Word generato dal payload ridotto: {atteso}"


def test_anche_l_html_si_genera_dal_payload_ridotto(pagina):
    h = render.html_report(_esecuzione(pagina))
    assert "<svg" in h and "testo di Lighthouse" in h
