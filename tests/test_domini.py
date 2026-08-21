"""
Test del dominio registrabile e dell'attribuzione first / third party.

Il caso che ha motivato questi test: prendendo gli ultimi due label,
`static.files.bbci.co.uk` diventava "co.uk". Non era solo impreciso — dichiarando
`bbci.co.uk` fra i domini propri, l'insieme finiva per contenere "co.uk" e
QUALSIASI dominio britannico, vendor di terze parti compresi, risultava prima
parte. E' la classificazione che decide a chi viene assegnato l'intervento.
"""
import pytest

from speed.core.thirdparty import (_propri, dominio_registrabile, e_prima_parte,
                                   riepiloga)
from speed.core.extract import Richiesta


# --- suffissi a due livelli -------------------------------------------------- #

@pytest.mark.parametrize("host, atteso", [
    ("static.files.bbci.co.uk", "bbci.co.uk"),
    ("bbci.co.uk", "bbci.co.uk"),
    ("www.theguardian.co.uk", "theguardian.co.uk"),
    ("comune.milano.gov.it", "milano.gov.it"),
    ("dati.gov.it", "dati.gov.it"),
    ("cdn.esempio.com.br", "esempio.com.br"),
    ("shop.esempio.com.au", "esempio.com.au"),
    ("a.b.c.co.jp", "c.co.jp"),
])
def test_suffissi_a_due_livelli(host, atteso):
    assert dominio_registrabile(host) == atteso


@pytest.mark.parametrize("host, atteso", [
    ("www.bbc.com", "bbc.com"),
    ("www.pluxee.it", "pluxee.it"),
    ("cdn.optimizely.com", "optimizely.com"),
    ("esempio.it", "esempio.it"),
])
def test_suffissi_normali(host, atteso):
    assert dominio_registrabile(host) == atteso


def test_host_degeneri():
    assert dominio_registrabile("localhost") == "localhost"
    assert dominio_registrabile("") == ""
    assert dominio_registrabile("ESEMPIO.IT") == "esempio.it", "il confronto e' minuscolo"


# --- l'effetto sull'attribuzione -------------------------------------------- #

def test_dichiarare_un_co_uk_non_regala_tutto_il_regno_unito():
    """E' il bug: `propri` conteneva "co.uk" e ogni dominio britannico passava."""
    propri = _propri("https://www.bbc.com/", ["bbci.co.uk"])
    assert "co.uk" not in propri
    assert e_prima_parte("static.files.bbci.co.uk", propri) is True
    assert e_prima_parte("cdn.concorrente.co.uk", propri) is False


def test_dichiarare_un_gov_it_non_regala_la_pubblica_amministrazione():
    propri = _propri("https://www.esempio.it/", ["milano.gov.it"])
    assert e_prima_parte("servizi.milano.gov.it", propri) is True
    assert e_prima_parte("altrocomune.gov.it", propri) is False


def test_il_dominio_della_pagina_su_suffisso_doppio():
    """Un cliente ospitato direttamente su .co.uk: la sua pagina resta prima parte."""
    propri = _propri("https://www.cliente.co.uk/", [])
    assert e_prima_parte("www.cliente.co.uk", propri) is True
    assert e_prima_parte("static.cliente.co.uk", propri) is True
    assert e_prima_parte("vendor.co.uk", propri) is False


def test_riepilogo_su_dominio_britannico():
    richieste = [
        Richiesta(url="https://www.cliente.co.uk/", host="www.cliente.co.uk",
                  byte=1000, tipo="Document"),
        Richiesta(url="https://static.cliente.co.uk/a.js", host="static.cliente.co.uk",
                  byte=3000, tipo="Script"),
        Richiesta(url="https://tag.vendor.co.uk/t.js", host="tag.vendor.co.uk",
                  byte=6000, tipo="Script"),
    ]
    r = riepiloga(richieste, "https://www.cliente.co.uk/", [])
    assert r.byte_first == 4000
    assert r.byte_terzi == 6000, "il vendor britannico resta terza parte"
