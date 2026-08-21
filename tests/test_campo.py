"""
Test della raccolta dei dati di campo.

Il caso che ha motivato questi test: record e storico venivano chiesti in un'unica
espressione, e un errore sullo storico faceva perdere anche le metriche correnti.
La pagina risultava senza campo pur avendone, e ogni priorita' ricadeva su "media"
— cioe' il tool smetteva di calibrare sul campo senza segnalarlo.
"""
import asyncio

import pytest

from speed.io import crux

RECORD = {
    "url": "https://x.it/", "livello": "url",
    "periodo_da": "2026-01-01", "periodo_a": "2026-08-15",
    "metriche": {"largest_contentful_paint": 3699.0, "cumulative_layout_shift": 0.03},
}
STORICO = {"url": "https://x.it/", "periodi": ["2026-08-15"],
           "serie": {"largest_contentful_paint": [3699.0]}}


def _esegui(record_risultato, storico_risultato, monkeypatch):
    async def finto_record(*_a, **_k):
        if isinstance(record_risultato, Exception):
            raise record_risultato
        return record_risultato

    async def finto_storico(*_a, **_k):
        if isinstance(storico_risultato, Exception):
            raise storico_risultato
        return storico_risultato

    monkeypatch.setattr(crux, "record", finto_record)
    monkeypatch.setattr(crux, "storico", finto_storico)
    return asyncio.run(crux.raccogli(None, "chiave", "https://x.it/", "PHONE"))


def test_tutto_disponibile(monkeypatch):
    voce = _esegui(RECORD, STORICO, monkeypatch)
    assert voce["livello"] == "url"
    assert voce["metriche"]["largest_contentful_paint"] == 3699.0
    assert voce["storico"]["serie"]


def test_storico_mancante_non_cancella_le_metriche(monkeypatch):
    """E' il bug: lo storico che fallisce non deve portarsi via il campo."""
    voce = _esegui(RECORD, crux.CruxNonDisponibile("https://x.it/"), monkeypatch)
    assert voce["livello"] == "url", "le metriche correnti ci sono: il livello e' 'url'"
    assert voce["metriche"]["largest_contentful_paint"] == 3699.0
    assert voce["storico"] is None, "manca solo l'andamento"


def test_storico_che_esplode_per_altro_motivo_non_cancella_le_metriche(monkeypatch):
    """Un 500 o un timeout sullo storico non e' CruxNonDisponibile, ma il risultato
    per chi legge il report dev'essere lo stesso: si perde l'andamento, non il campo."""
    voce = _esegui(RECORD, RuntimeError("CrUX History 500"), monkeypatch)
    assert voce["livello"] == "url"
    assert voce["metriche"] and voce["storico"] is None


def test_record_mancante_lascia_la_pagina_senza_campo(monkeypatch):
    """Qui il degrado e' corretto: senza record non c'e' metrica di campo."""
    voce = _esegui(crux.CruxNonDisponibile("https://x.it/"), STORICO, monkeypatch)
    assert voce["livello"] == "assente"
    assert voce["metriche"] == {} and voce["storico"] is None


def test_il_record_che_esplode_non_viene_nascosto(monkeypatch):
    """Un errore diverso da CruxNonDisponibile — chiave sbagliata, quota — non va
    scambiato per "questa pagina non ha traffico": deve arrivare a chi ha lanciato."""
    with pytest.raises(RuntimeError):
        _esegui(RuntimeError("CrUX 403: chiave non valida"), STORICO, monkeypatch)
