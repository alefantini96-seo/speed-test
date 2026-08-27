"""
Test del budget di tempo del percorso web.

Il caso che li ha motivati: con i valori predefiniti dei client il caso peggiore
di una singola analisi era 852 secondi — 3 tentativi PSI da 120 s per due giri,
piu' 75 s di CrUX — contro i 300 di `maxDuration`. Su una pagina lenta la
piattaforma uccideva la funzione prima che il tool potesse consegnare il suo
errore con rimedio, e all'utente arrivava un 504 anonimo.

Niente rete: si verificano l'aritmetica del budget e i parametri che il percorso
web passa ai client.
"""
import asyncio
import json
from pathlib import Path

from speed import web
from speed.io import crux, psi

RADICE = Path(__file__).resolve().parent.parent
FIXTURES = RADICE / "fixtures"
URL = "https://www.bbc.com/"


# --- l'aritmetica ------------------------------------------------------------ #

def test_il_caso_peggiore_sta_sotto_il_tetto_della_piattaforma():
    assert web.BUDGET.peggior_caso() < web.MAX_DURATA_VERCEL


def test_il_margine_e_reale_non_al_millisecondo():
    """Sotto il tetto va tenuto con spazio: restano l'avvio a freddo, la rete e
    la serializzazione della risposta."""
    margine = web.MAX_DURATA_VERCEL - web.BUDGET.peggior_caso()
    assert margine >= 30, f"solo {margine:.0f} s di margine sul tetto"


def test_il_tetto_dichiarato_e_quello_di_vercel():
    """Se qualcuno alza maxDuration senza toccare qui, il conto non vale piu'."""
    configurazione = json.loads((RADICE / "vercel.json").read_text(encoding="utf-8"))
    assert configurazione["functions"]["app.py"]["maxDuration"] == web.MAX_DURATA_VERCEL


def test_l_attesa_fra_i_giri_non_si_somma_al_caso_peggiore():
    """analizza_molte aspetta il residuo: se il giro e' durato piu' dell'attesa,
    non aspetta affatto. Contarla in piu' porterebbe a stringere i timeout senza
    motivo."""
    budget = web.BUDGET
    assert budget.psi_attesa_fra_giri < budget.giro_psi
    assert budget.peggior_caso(2) == budget.campo + budget.giro_psi * 2


def test_un_solo_giro_costa_meno_di_due():
    assert web.BUDGET.peggior_caso(1) < web.BUDGET.peggior_caso(2)


# --- i parametri che arrivano davvero ai client ------------------------------ #

def _analisi_finta(monkeypatch):
    """Esegue analizza_una senza rete, catturando i parametri passati ai client."""
    visto = {}

    async def finta_raccogli(_client, _api_key, _url, _form_factor, **kwargs):
        visto["crux"] = kwargs
        # Senza fasi LCP di campo: e' il ramo a due giri, quello costoso.
        return {"livello": "url", "metriche": {"largest_contentful_paint": 1162.0},
                "storico": None}

    async def finta_analizza_molte(_api_key, urls, _strategy, **kwargs):
        visto["psi"] = kwargs
        risposta = json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(
            encoding="utf-8"))
        return {urls[0]: [risposta] * kwargs["ripetizioni"]}

    monkeypatch.setattr(crux, "raccogli", finta_raccogli)
    monkeypatch.setattr(psi, "analizza_molte", finta_analizza_molte)
    asyncio.run(web.analizza_una("chiave", URL, "PHONE", []))
    return visto


def test_il_percorso_web_passa_il_suo_budget_ai_client(monkeypatch):
    visto = _analisi_finta(monkeypatch)
    budget = web.BUDGET
    assert visto["psi"]["timeout"] == budget.psi_timeout
    assert visto["psi"]["tentativi"] == budget.psi_tentativi
    assert visto["psi"]["attesa_iniziale"] == budget.psi_backoff
    assert visto["psi"]["attesa_fra_giri"] == budget.psi_attesa_fra_giri
    assert visto["crux"]["timeout_record"] == budget.crux_timeout_record
    assert visto["crux"]["timeout_storico"] == budget.crux_timeout_storico
    assert visto["crux"]["tentativi"] == budget.crux_tentativi


def test_dai_parametri_passati_il_conto_torna_sotto_il_tetto(monkeypatch):
    """Non si verifica il budget dichiarato ma quello che i client ricevono: e'
    li' che il tempo si consuma davvero."""
    visto = _analisi_finta(monkeypatch)
    effettivo = web.Budget(
        psi_tentativi=visto["psi"]["tentativi"],
        psi_timeout=visto["psi"]["timeout"],
        psi_backoff=visto["psi"]["attesa_iniziale"],
        psi_attesa_fra_giri=visto["psi"]["attesa_fra_giri"],
        psi_giri_massimi=visto["psi"]["ripetizioni"],
        crux_timeout_record=visto["crux"]["timeout_record"],
        crux_timeout_storico=visto["crux"]["timeout_storico"],
        crux_tentativi=visto["crux"]["tentativi"],
        crux_tentativi_storico=visto["crux"]["tentativi_storico"],
        crux_backoff=visto["crux"]["attesa_iniziale"],
    )
    assert effettivo.peggior_caso() < web.MAX_DURATA_VERCEL


def test_il_ramo_costoso_e_quello_a_due_giri(monkeypatch):
    """Senza fasi LCP dal campo — cioe' su ogni LCP testuale — i giri sono due."""
    visto = _analisi_finta(monkeypatch)
    assert visto["psi"]["ripetizioni"] == web.BUDGET.psi_giri_massimi == 2


# --- la CLI non eredita i timeout stretti ------------------------------------ #

def test_la_cli_tiene_i_valori_generosi():
    """Non ha limiti di durata: stringerle i timeout perderebbe le pagine lente
    per un vincolo che non la riguarda."""
    assert psi.TIMEOUT == 120.0
    assert crux.TIMEOUT_RECORD == 30.0 and crux.TIMEOUT_STORICO == 45.0
    for funzione in (psi.analizza, crux.record, crux.storico):
        difetti = funzione.__defaults__ or ()
        assert 3 in difetti, f"{funzione.__name__}: tre tentativi, come prima"
