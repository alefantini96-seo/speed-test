"""
Test della raccolta dei dati di campo.

Il caso che ha motivato questi test: record e storico venivano chiesti in un'unica
espressione, e un errore sullo storico faceva perdere anche le metriche correnti.
La pagina risultava senza campo pur avendone, e ogni priorita' ricadeva su "media"
— cioe' il tool smetteva di calibrare sul campo senza segnalarlo.
"""
import asyncio

import pytest

from speed.errori import ErroreSpeed
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


# --- le protezioni di rete: le stesse di psi.py ------------------------------ #
#
# CrUX e' l'unica fonte della metrica: se una chiamata cade, il report perde campo
# e storico e ogni priorita' ricade su "media" senza che nessuno lo dica. Prima
# `r.json()` veniva chiamato senza guardare lo status e senza riprovare.

class RispostaFinta:
    def __init__(self, status_code=200, corpo=None, testo=""):
        self.status_code = status_code
        self._corpo = corpo
        self.text = testo

    def json(self):
        if self._corpo is None:
            raise ValueError("non e' JSON")
        return self._corpo


class ClienteFinto:
    """Restituisce le risposte in sequenza e conta le chiamate."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.chiamate = 0

    async def post(self, *_a, **_k):
        self.chiamate += 1
        return self.risposte[min(self.chiamate - 1, len(self.risposte) - 1)]


DATI = {"record": {"collectionPeriod": {"firstDate": {"year": 2026, "month": 1, "day": 1},
                                        "lastDate": {"year": 2026, "month": 8, "day": 15}},
                   "metrics": {"largest_contentful_paint": {"percentiles": {"p75": 3699}}}}}


def _record(cliente, **kwargs):
    return asyncio.run(crux.record(cliente, "chiave", "https://x.it/",
                                   attesa_iniziale=0, **kwargs))


def test_crux_riprova_sui_codici_transitori():
    cliente = ClienteFinto(RispostaFinta(503, None, "<html>gateway</html>"),
                           RispostaFinta(503, None, "<html>gateway</html>"),
                           RispostaFinta(200, DATI))
    assert _record(cliente)["metriche"]["largest_contentful_paint"] == 3699.0
    assert cliente.chiamate == 3


def test_crux_non_esplode_in_jsondecodeerror():
    """E' il bug: una pagina HTML al posto del JSON usciva grezza da r.json()."""
    cliente = ClienteFinto(RispostaFinta(200, None, "<html>manutenzione</html>"))
    with pytest.raises(ErroreSpeed) as info:
        _record(cliente)
    assert "JSON" in info.value.messaggio


def test_crux_guarda_lo_status_di_errore():
    cliente = ClienteFinto(RispostaFinta(403, None, "accesso negato"))
    with pytest.raises(ErroreSpeed):
        _record(cliente)


def test_crux_non_riprova_sugli_errori_definitivi():
    cliente = ClienteFinto(RispostaFinta(400, {"error": {
        "code": 400, "message": "API key not valid. Please pass a valid API key."}}))
    with pytest.raises(ErroreSpeed) as info:
        _record(cliente)
    assert cliente.chiamate == 1
    assert "chiave API non e' valida" in info.value.messaggio


def test_il_404_resta_un_esito_legittimo_non_un_errore():
    """Nessun dato di campo per questa URL: il report lo dichiara e prosegue con
    la sola diagnosi di laboratorio."""
    cliente = ClienteFinto(RispostaFinta(404, {"error": {"code": 404, "message": "not found"}}))
    with pytest.raises(crux.CruxNonDisponibile):
        _record(cliente)


def test_il_404_senza_corpo_json_e_lo_stesso_esito():
    """Un 404 servito dal gateway non ha un corpo JSON: prima usciva come
    JSONDecodeError invece che come "nessun dato di campo"."""
    cliente = ClienteFinto(RispostaFinta(404, None, "<html>Not Found</html>"))
    with pytest.raises(crux.CruxNonDisponibile):
        _record(cliente)


def test_lo_storico_ha_le_stesse_protezioni():
    cliente = ClienteFinto(RispostaFinta(502, None, "<html>bad gateway</html>"))
    with pytest.raises(ErroreSpeed):
        asyncio.run(crux.storico(cliente, "chiave", "https://x.it/", attesa_iniziale=0))
    assert cliente.chiamate == 3, "tre tentativi, come su PSI"
