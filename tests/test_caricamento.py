"""
Test di cio' che il JSON di PSI portava gia' e il tool non leggeva: i tempi
osservati, la catena di redirect, i fotogrammi, le categorie, e i tempi delle
singole richieste su cui si disegna la cascata.

La fixture `psi-bbc-redirect-categorie.json` e' una risposta reale a
`http://bbc.com/` chiesta con tutte e quattro le categorie: e' l'unica che
contiene insieme una catena di redirect vera e i punteggi di accessibilita',
best practice e SEO.
"""
import json
from pathlib import Path

import pytest

from speed.core import extract

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="module")
def psi():
    return json.loads((FIXTURES / "psi-bbc-redirect-categorie.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def storico():
    """La risposta con la sola categoria performance, senza redirect."""
    return json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(encoding="utf-8"))


# --- tempi delle richieste: senza, la cascata non si disegna ---------------- #

def test_la_richiesta_porta_i_suoi_tempi(psi):
    prima = extract.estrai_richieste(psi)[0]
    assert prima.url == "http://bbc.com/"
    assert prima.partita > 0
    assert prima.finita > prima.partita
    assert prima.durata == pytest.approx(prima.finita - prima.partita)
    assert prima.protocollo and prima.priorita


def test_le_richieste_non_arrivano_in_ordine_di_tempo(psi):
    """Fatto verificato sulla risposta reale: 2 inversioni su 126 richieste.
    Quasi ordinate, non ordinate — chi disegna la cascata deve ordinarle."""
    tempi = [r.partita for r in extract.estrai_richieste(psi)]
    assert tempi != sorted(tempi)


def test_la_coda_non_e_mai_negativa(psi):
    """`rendererStartTime` puo' essere 0 o successivo alla partenza in rete:
    la coda si legge come "ferma prima di partire", non come un segno."""
    assert all(r.coda >= 0 for r in extract.estrai_richieste(psi))


def test_il_peso_delle_richieste_torna_col_riepilogo_di_lighthouse(psi):
    """Tre audit diversi contano le stesse richieste: se divergono, il report
    mostrerebbe due numeri per lo stesso fatto."""
    richieste = extract.estrai_richieste(psi)
    riepilogo = next(
        voce for voce in psi["lighthouseResult"]["audits"]["resource-summary"]["details"]["items"]
        if voce["resourceType"] == "total")
    assert len(richieste) == riepilogo["requestCount"]
    assert sum(r.byte for r in richieste) == riepilogo["transferSize"]


# --- tempi osservati -------------------------------------------------------- #

def test_tempi_osservati(psi):
    tempi = extract.estrai_tempi_osservati(psi)
    assert set(tempi) == set(extract.TEMPI_OSSERVATI.values())
    assert tempi["DOM pronto"] < tempi["Caricata"]


def test_tempi_osservati_senza_audit():
    assert extract.estrai_tempi_osservati({}) == {}


# --- catena di redirect ----------------------------------------------------- #

def test_catena_di_redirect(psi):
    salti = extract.estrai_redirect(psi)
    assert [(s.da, s.a, s.stato) for s in salti] == [
        ("http://bbc.com/", "https://bbc.com/", 301),
        ("https://bbc.com/", "https://www.bbc.com/", 301),
    ]
    assert sum(s.ms for s in salti) == pytest.approx(
        psi["lighthouseResult"]["audits"]["redirects"]["numericValue"])


def test_senza_redirect_la_catena_e_vuota(storico):
    """L'audit c'e' lo stesso, con la lista vuota: una tappa sola non e' un salto."""
    assert extract.estrai_redirect(storico) == []


# --- fotogrammi ------------------------------------------------------------- #

def test_filmstrip(psi):
    fotogrammi = extract.estrai_filmstrip(psi)
    assert len(fotogrammi) == 8
    assert [f.ms for f in fotogrammi] == sorted(f.ms for f in fotogrammi)
    assert all(f.immagine.startswith("data:image/jpeg;base64,") for f in fotogrammi)


def test_screenshot_finale(psi):
    finale = extract.estrai_screenshot(psi)
    assert finale is not None
    assert finale.immagine.startswith("data:image/jpeg;base64,")
    # Non e' l'ultimo fotogramma del filmstrip, che arriva dopo: e' il momento
    # in cui la pagina ha smesso di cambiare.
    assert finale.ms == pytest.approx(
        extract.estrai_tempi_osservati(psi)["Ultimo cambio visivo"], abs=2)


def test_senza_immagini_non_si_inventa_niente():
    assert extract.estrai_filmstrip({}) == []
    assert extract.estrai_screenshot({}) is None


# --- categorie -------------------------------------------------------------- #

def test_categorie_in_ordine_e_col_titolo_di_lighthouse(psi):
    categorie = extract.estrai_categorie(psi)
    assert [c.chiave for c in categorie] == list(extract.CATEGORIE)
    assert [c.titolo for c in categorie] == ["Prestazioni", "Accessibilità",
                                             "Best practice", "SEO"]
    assert all(0 <= c.punteggio <= 100 for c in categorie)


def test_con_la_sola_performance_resta_una_categoria(storico):
    assert [c.chiave for c in extract.estrai_categorie(storico)] == ["performance"]


# --- il filtro che tiene fuori gli audit delle altre categorie -------------- #

def test_gli_interventi_restano_quelli_di_performance(psi):
    """Chiedere quattro categorie porta 153 audit al posto di 47: senza filtro,
    un `color-contrast` entrerebbe fra gli interventi di velocita'."""
    di_performance = extract.audit_di_performance(psi)
    tutti = psi["lighthouseResult"]["audits"]
    assert len(tutti) > len(di_performance) * 2
    interventi = extract.estrai_opportunita(psi, "https://www.bbc.com/")
    assert interventi
    assert all(o.audit in di_performance for o in interventi)


def test_il_filtro_non_toglie_niente_alle_risposte_di_sola_performance(storico):
    assert len(extract.estrai_opportunita(storico, "https://www.bbc.com/")) == 14
