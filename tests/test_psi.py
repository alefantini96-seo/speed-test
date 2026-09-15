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
    """Restituisce le risposte in sequenza e conta le chiamate.

    Una risposta che e' un'eccezione viene sollevata invece che restituita: e'
    cosi' che si provano le cadute di rete e le scadenze.
    """

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.chiamate = 0
        self.attese = []

    async def get(self, *_a, **kwargs):
        self.chiamate += 1
        self.parametri = kwargs.get("params", {})
        self.attese.append(kwargs.get("timeout"))
        esito = self.risposte[min(self.chiamate - 1, len(self.risposte) - 1)]
        if isinstance(esito, Exception):
            raise esito
        return esito


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

# --- riprovare dopo uno scadere --------------------------------------------- #
#
# Il caso visto in produzione: una misurazione scaduta a 120 s faceva fallire la
# pagina con meta' del budget ancora in mano. Il gruzzolo e' sulle CHIAMATE, e
# una scadenza deve poterne spendere una come la spenderebbe un 503.
#
# Non e' il recupero della prima: misurato il 15/09/2026, abbandonata una
# chiamata a 15 s e richiesta la stessa URL dopo 45 e dopo 90 secondi, la
# risposta e' arrivata in 41,0 e 32,5 s con una marca temporale nuova. PSI non
# tiene il lavoro che nessuno ha ritirato: e' un secondo sorteggio, e conviene
# perche' la coda lenta e' l'eccezione.

def test_dopo_uno_scadere_si_riprova():
    cliente = ClienteFinto(httpx.ReadTimeout(""), RispostaFinta(200, OK))
    assert _analizza(cliente, chiamate=2) == OK
    assert cliente.chiamate == 2


def test_con_una_chiamata_sola_non_si_riprova():
    """Chi ha comprato una chiamata ne ha una: la seconda la deve pagare il
    budget, non la buona volonta' del client."""
    cliente = ClienteFinto(httpx.ReadTimeout(""), RispostaFinta(200, OK))
    with pytest.raises(ErroreSpeed):
        _analizza(cliente, chiamate=1)
    assert cliente.chiamate == 1


def test_due_scadenze_di_fila_restano_un_errore_con_rimedio():
    cliente = ClienteFinto(httpx.ReadTimeout(""), httpx.ReadTimeout(""))
    with pytest.raises(ErroreSpeed) as caduta:
        _analizza(cliente, chiamate=2)
    assert cliente.chiamate == 2
    assert caduta.value.rimedio


def test_la_riprova_non_comincia_se_il_tempo_non_basta():
    """Una chiamata che sfora il tetto fa uccidere la funzione dalla piattaforma,
    e l'utente perde l'errore con rimedio invece di riceverlo."""
    cliente = ClienteFinto(httpx.ReadTimeout(""), RispostaFinta(200, OK))
    fra_poco = asyncio.new_event_loop().time() + 5
    with pytest.raises(ErroreSpeed):
        asyncio.run(psi.analizza(cliente, "chiave", "https://x.it/",
                                 chiamate=3, attesa_iniziale=0, scadenza=fra_poco))
    assert cliente.chiamate == 1, "la seconda non parte: non ci sarebbe stata"


def test_la_scadenza_accorcia_l_attesa_dell_ultima_chiamata():
    """Meglio una chiamata piu' corta che una che sfora: il tempo che resta e'
    quello, e chiederne di piu' non lo fa comparire."""
    cliente = ClienteFinto(RispostaFinta(200, OK))
    fra_poco = asyncio.new_event_loop().time() + 40
    asyncio.run(psi.analizza(cliente, "chiave", "https://x.it/", timeout=120.0,
                             attesa_iniziale=0, scadenza=fra_poco))
    assert cliente.attese[0] <= 40


def test_senza_scadenza_la_cli_tiene_il_suo_timeout():
    cliente = ClienteFinto(RispostaFinta(200, OK))
    asyncio.run(psi.analizza(cliente, "chiave", "https://x.it/", timeout=120.0))
    assert cliente.attese[0] == 120.0
