"""
Test del client PageSpeed Insights: status, riprove, risposte non-JSON.

Il caso che ha motivato questi test: `r.json()` veniva chiamato senza guardare lo
status. Un 502 del gateway o una pagina di quota tornano HTML, e la chiamata
esplodeva in JSONDecodeError — un errore che non dice niente a chi legge, e che
su venti template si traduce in buchi silenziosi nel report.
"""
import asyncio

import pytest

from speed.errori import ErroreSpeed
from speed.io import psi


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

    async def get(self, *_a, **_k):
        self.chiamate += 1
        return self.risposte[min(self.chiamate - 1, len(self.risposte) - 1)]


def _analizza(cliente, **kwargs):
    # attesa azzerata: il backoff e' gia' verificato dal conteggio dei tentativi
    return asyncio.run(psi.analizza(cliente, "chiave", "https://x.it/",
                                    attesa_iniziale=0, **kwargs))


OK = {"lighthouseResult": {"lighthouseVersion": "13.4.1"}}


def test_risposta_valida():
    cliente = ClienteFinto(RispostaFinta(200, OK))
    assert _analizza(cliente) == OK
    assert cliente.chiamate == 1, "niente riprove quando va bene"


def test_riprova_sui_codici_transitori():
    cliente = ClienteFinto(RispostaFinta(503, None, "<html>gateway</html>"),
                           RispostaFinta(503, None, "<html>gateway</html>"),
                           RispostaFinta(200, OK))
    assert _analizza(cliente) == OK
    assert cliente.chiamate == 3


def test_si_arrende_dopo_i_tentativi_previsti():
    cliente = ClienteFinto(RispostaFinta(502, None, "<html>bad gateway</html>"))
    with pytest.raises(ErroreSpeed):
        _analizza(cliente)
    assert cliente.chiamate == 3, "tre tentativi, non di piu'"


def test_non_riprova_sugli_errori_definitivi():
    """Una chiave sbagliata non migliora riprovando: riprovare sprecherebbe solo
    tempo e quota."""
    cliente = ClienteFinto(RispostaFinta(400, {"error": {
        "code": 400, "message": "API key not valid. Please pass a valid API key."}}))
    with pytest.raises(ErroreSpeed) as info:
        _analizza(cliente)
    assert cliente.chiamate == 1
    assert "chiave API non e' valida" in info.value.messaggio
    assert "console.cloud.google.com" in info.value.rimedio


def test_risposta_non_json_non_esplode_in_jsondecodeerror():
    """E' il bug: una pagina HTML al posto del JSON usciva come JSONDecodeError."""
    cliente = ClienteFinto(RispostaFinta(200, None, "<html>manutenzione</html>"))
    with pytest.raises(ErroreSpeed) as info:
        _analizza(cliente)
    assert "JSON" in info.value.messaggio


def test_lo_status_di_errore_viene_guardato():
    """Un 403 con corpo HTML: prima passava a `.json()` senza controlli."""
    cliente = ClienteFinto(RispostaFinta(403, None, "accesso negato"))
    with pytest.raises(ErroreSpeed):
        _analizza(cliente)


def test_la_quota_esaurita_porta_il_suo_rimedio():
    cliente = ClienteFinto(RispostaFinta(429, {"error": {
        "code": 429, "message": "Quota exceeded"}}))
    with pytest.raises(ErroreSpeed) as info:
        _analizza(cliente)
    assert "quota" in info.value.messaggio.lower()
    assert "25.000" in info.value.rimedio


def test_json_sicuro():
    assert psi._json_sicuro(RispostaFinta(200, {"a": 1})) == {"a": 1}
    assert psi._json_sicuro(RispostaFinta(200, None, "<html>")) is None
    assert psi._json_sicuro(RispostaFinta(200, [1, 2])) is None, "una lista non e' utile"
