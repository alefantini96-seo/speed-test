"""
Test del client PageSpeed Insights: status, riprove, risposte non-JSON.

Il caso che ha motivato questi test: `r.json()` veniva chiamato senza guardare lo
status. Un 502 del gateway o una pagina di quota tornano HTML, e la chiamata
esplodeva in JSONDecodeError — un errore che non dice niente a chi legge, e che
su venti template si traduce in buchi silenziosi nel report.
"""
import asyncio

import httpx
import pytest

from speed.errori import ErroreSpeed
from speed.io import google, psi


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

    async def get(self, *_a, **kwargs):
        self.chiamate += 1
        self.parametri = kwargs.get("params", {})
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


def test_chiede_tutte_e_quattro_le_categorie():
    """Accessibilita', best practice e SEO viaggiano nella stessa risposta e non
    costano un'altra misurazione. Il punteggio di nessuna entra in una
    valutazione: compaiono come riferimento, come quello delle prestazioni."""
    cliente = ClienteFinto(RispostaFinta(200, OK))
    _analizza(cliente)
    assert cliente.parametri["category"] == [
        "performance", "accessibility", "best-practices", "seo"]


def test_le_categorie_si_possono_restringere():
    cliente = ClienteFinto(RispostaFinta(200, OK))
    _analizza(cliente, categorie=("performance",))
    assert cliente.parametri["category"] == ["performance"]


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
    assert google.json_sicuro(RispostaFinta(200, {"a": 1})) == {"a": 1}
    assert google.json_sicuro(RispostaFinta(200, None, "<html>")) is None
    assert google.json_sicuro(RispostaFinta(200, [1, 2])) is None, "una lista non e' utile"


# --- quando la rete cade, l'errore deve dire cosa e' successo --------------- #
#
# Il sintomo, visto in produzione: "Misurazione fallita: Errore 502". Uno status,
# nessuna causa, nessun rimedio. httpx solleva `ReadTimeout` con il messaggio
# VUOTO; quella stringa vuota arrivava fino al browser, che ripiegava sullo
# status. Le eccezioni di rete vanno tradotte dove si sa quanto si e' aspettato.

class ClienteCheCade:
    def __init__(self, eccezione):
        self.eccezione = eccezione

    async def get(self, *_a, **_k):
        raise self.eccezione


def test_l_attesa_scaduta_diventa_un_errore_con_rimedio():
    with pytest.raises(ErroreSpeed) as caduta:
        asyncio.run(psi.analizza(ClienteCheCade(httpx.ReadTimeout("")), "chiave",
                                 "https://x.it/", timeout=55.0))
    errore = caduta.value
    assert "55 secondi" in errore.messaggio
    assert "https://x.it/" in errore.messaggio
    assert errore.rimedio, "senza rimedio resta un errore muto"
    assert "riga di comando" in errore.rimedio


def test_la_rete_caduta_non_si_confonde_con_la_pagina_lenta():
    with pytest.raises(ErroreSpeed) as caduta:
        asyncio.run(psi.analizza(ClienteCheCade(httpx.ConnectError("")), "chiave",
                                 "https://x.it/"))
    assert "non e' raggiungibile" in caduta.value.messaggio
    assert "ConnectError" in caduta.value.messaggio, \
        "il nome della classe e' l'unica cosa che porta un'eccezione senza messaggio"


def test_nessun_errore_di_rete_resta_senza_messaggio():
    """Il difetto era proprio questo: `str(ReadTimeout(''))` e' la stringa vuota."""
    for eccezione in (httpx.ReadTimeout(""), httpx.ConnectTimeout(""),
                      httpx.PoolTimeout(""), httpx.ConnectError(""),
                      httpx.RemoteProtocolError("")):
        with pytest.raises(ErroreSpeed) as caduta:
            asyncio.run(psi.analizza(ClienteCheCade(eccezione), "chiave", "https://x.it/"))
        assert caduta.value.messaggio.strip()
        assert caduta.value.rimedio.strip()
