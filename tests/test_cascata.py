"""
Test della cascata: ordinamento, scala, proporzioni.

Le barre finiscono dentro un'immagine, e un'immagine sbagliata non si nota. Qui
si presidia che le percentuali stiano dentro la scala e che nessuna richiesta
esca dal grafico.
"""
import json
from pathlib import Path

import pytest

from speed.core import cascata, extract

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PAGINA = "https://www.bbc.com/"


@pytest.fixture(scope="module")
def fatti():
    psi = json.loads((FIXTURES / "psi-bbc-redirect-categorie.json").read_text(encoding="utf-8"))
    return extract.estrai(psi, "http://bbc.com/", "PHONE")


@pytest.fixture(scope="module")
def disegno(fatti):
    return cascata.cascata(fatti.richieste, fatti.tempi_osservati, PAGINA)


def test_le_barre_sono_in_ordine_di_tempo(disegno):
    inizi = [b.inizio_ms for b in disegno.barre]
    assert inizi == sorted(inizi)


def test_nessuna_barra_esce_dal_grafico(disegno):
    for b in disegno.barre:
        assert 0 <= b.inizio_pc <= 100
        assert b.inizio_pc + b.coda_pc + b.durata_pc <= 100.001


def test_la_scala_contiene_anche_i_riferimenti(fatti):
    """"Caricata" cade dopo l'ultima richiesta finita: se la scala si fermasse
    alle richieste, il riferimento cadrebbe fuori dal grafico."""
    disegno = cascata.cascata(fatti.richieste, fatti.tempi_osservati, PAGINA)
    assert disegno.scala_ms >= max(r.ms for r in disegno.riferimenti)
    assert all(0 <= r.pc <= 100 for r in disegno.riferimenti)


def test_i_riferimenti_sono_in_ordine(disegno):
    assert [r.etichetta for r in disegno.riferimenti][:3] == [
        "FCP osservato", "LCP osservato", "DOM pronto"]


def test_le_terze_parti_sono_marcate(disegno):
    assert not disegno.barre[0].terza_parte, "il documento e' prima parte"
    assert any(b.terza_parte for b in disegno.barre)


def test_i_redirect_restano_nella_cascata(disegno):
    """Sono le prime due richieste, e senza di loro il grafico comincerebbe da
    un documento gia' a 48 ms senza dire da dove arriva quel tempo."""
    assert [b.stato for b in disegno.barre[:3]] == [301, 301, 200]


def test_senza_richieste_non_si_disegna_niente():
    vuota = cascata.cascata([], {})
    assert vuota.barre == [] and vuota.riferimenti == [] and vuota.scala_ms == 0


def test_nome_file():
    assert cascata.nome_file("https://www.esempio.it/") == "www.esempio.it/"
    assert cascata.nome_file("https://cdn.it/a/b/app.min.js") == "app.min.js"
    assert cascata.nome_file("https://cdn.it/f.js?v=3") == "f.js?…"


def test_piu_lente(disegno):
    lente = cascata.piu_lente(disegno, 5)
    assert len(lente) == 5
    assert [b.durata_ms for b in lente] == sorted((b.durata_ms for b in lente), reverse=True)
    assert lente[0].durata_ms == max(b.durata_ms for b in disegno.barre)
