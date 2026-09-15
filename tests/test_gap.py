"""
Test del gap competitor: il tuo campo accanto a quello dei concorrenti.

Niente rete: `crux.record` viene sostituito. Quello che si verifica e' il
comportamento che distingue questo confronto da una tabella qualsiasi — il
ripiego sull'origine dichiarato, un URL che cade senza portarsi via gli altri,
e il fatto che il laboratorio non entri.
"""
import asyncio
import io
import json
from pathlib import Path

import pytest

from speed import web
from speed.errori import ErroreSpeed
from speed.io import crux

RADICE = Path(__file__).resolve().parent.parent
MIA = "https://www.esempio.it/prodotto/"


def _record(metriche=None, livello="url", periodo="2026-09-13"):
    return {"livello": livello, "metriche": metriche or {"largest_contentful_paint": 1000.0},
            "periodo_a": periodo}


def _finge(monkeypatch, risposte):
    """`risposte` e' {(url, origin): valore}; un valore Exception viene sollevato."""
    async def finta_record(_client, _chiave, url, _form_factor="PHONE", origin=False, **_k):
        esito = risposte[(url, origin)]
        if isinstance(esito, Exception):
            raise esito
        return {"url": url} | esito

    monkeypatch.setattr(crux, "record", finta_record)


def _gap(monkeypatch, risposte, concorrenti):
    _finge(monkeypatch, risposte)
    return asyncio.run(web.gap("chiave", MIA, concorrenti))


# --- l'ordine e la forma ----------------------------------------------------- #

def test_la_tua_pagina_e_sempre_la_prima(monkeypatch):
    altro = "https://www.concorrente.it/prodotto/"
    esito = _gap(monkeypatch, {(MIA, False): _record(), (altro, False): _record()}, [altro])
    assert [p["url"] for p in esito["pagine"]] == [MIA, altro]
    assert esito["tua"] == MIA


def test_oltre_il_tetto_i_concorrenti_si_tagliano(monkeypatch):
    troppi = [f"https://www.c{n}.it/" for n in range(7)]
    risposte = {(u, False): _record() for u in troppi + [MIA]}
    esito = _gap(monkeypatch, risposte, troppi)
    assert len(esito["pagine"]) == web.LIMITE_CONCORRENTI + 1


def test_la_tua_pagina_non_si_confronta_con_se_stessa(monkeypatch):
    esito = _gap(monkeypatch, {(MIA, False): _record()}, [MIA])
    assert len(esito["pagine"]) == 1


# --- il ripiego sull'origine ------------------------------------------------- #

def test_senza_dati_sulla_pagina_si_guarda_il_dominio(monkeypatch):
    """Misurato il 15/09/2026: coverflex.com non aveva dati sulla home e li aveva
    sull'origine. Senza ripiego quel concorrente sparirebbe pur essendo
    misurabile."""
    altro = "https://www.concorrente.it/prodotto/"
    esito = _gap(monkeypatch, {
        (MIA, False): _record(),
        (altro, False): crux.CruxNonDisponibile(altro),
        (altro, True): _record(livello="origin"),
    }, [altro])
    assert esito["pagine"][1]["livello"] == "origin"


def test_il_ripiego_si_dichiara_e_non_si_traveste(monkeypatch):
    """Un numero del dominio spacciato per quello della pagina e' la stessa
    trappola dell'origin_fallback di PageSpeed: chi disegna deve poterlo dire."""
    altro = "https://www.concorrente.it/prodotto/"
    esito = _gap(monkeypatch, {
        (MIA, False): _record(),
        (altro, False): crux.CruxNonDisponibile(altro),
        (altro, True): _record(livello="origin"),
    }, [altro])
    assert esito["pagine"][0]["livello"] == "url"
    assert esito["pagine"][1]["livello"] != esito["pagine"][0]["livello"]


def test_senza_dati_ne_sulla_pagina_ne_sul_dominio(monkeypatch):
    altro = "https://www.piccolo.it/"
    esito = _gap(monkeypatch, {
        (MIA, False): _record(),
        (altro, False): crux.CruxNonDisponibile(altro),
        (altro, True): crux.CruxNonDisponibile(altro),
    }, [altro])
    assert esito["pagine"][1]["livello"] == "assente"
    assert esito["pagine"][1]["metriche"] == {}


# --- un URL che cade non si porta via gli altri ------------------------------ #

def test_un_concorrente_che_cade_lascia_in_piedi_il_confronto(monkeypatch):
    caduto = "https://www.rotto.it/"
    buono = "https://www.buono.it/"
    esito = _gap(monkeypatch, {
        (MIA, False): _record(),
        (caduto, False): ErroreSpeed("CrUX non ha risposto", "riprova"),
        (buono, False): _record(),
    }, [caduto, buono])
    livelli = [p["livello"] for p in esito["pagine"]]
    assert livelli == ["url", "errore", "url"]
    assert esito["pagine"][1]["errore"]


def test_l_errore_di_una_riga_porta_con_se_il_messaggio(monkeypatch):
    caduto = "https://www.rotto.it/"
    esito = _gap(monkeypatch, {
        (MIA, False): _record(),
        (caduto, False): ErroreSpeed("CrUX non ha risposto entro 8 secondi", "riprova"),
    }, [caduto])
    assert "8 secondi" in esito["pagine"][1]["errore"]


# --- il laboratorio non entra ------------------------------------------------ #

def test_il_confronto_non_chiama_pagespeed():
    """Fra due siti diversi il laboratorio direbbe meno di quanto oscilla fra due
    misurazioni dello stesso (ADR-001). E non ci starebbe: PSI impiega 40 s a
    pagina, CrUX 0,2."""
    sorgente = (RADICE / "speed" / "web.py").read_text(encoding="utf-8")
    corpo = sorgente[sorgente.index("async def gap("):sorgente.index("async def analizza_una(")]
    assert "psi" not in corpo
    assert "crux" in sorgente[sorgente.index("async def campo_con_ripiego("):
                              sorgente.index("async def _voce_gap(")]


# --- l'endpoint -------------------------------------------------------------- #

def _chiama(corpo: dict):
    from app import app
    dati = json.dumps(corpo).encode("utf-8")
    ambiente = {"PATH_INFO": "/api/gap", "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": str(len(dati)), "wsgi.input": io.BytesIO(dati),
                "REMOTE_ADDR": "10.0.0.1"}
    stato = {}

    def avvia(codice, _intestazioni):
        stato["codice"] = codice

    risposta = b"".join(app(ambiente, avvia))
    return stato["codice"], json.loads(risposta)


@pytest.fixture(autouse=True)
def chiave_finta(monkeypatch):
    """L'endpoint controlla la chiave prima di tutto, com'e' giusto: senza, ogni
    richiesta uscirebbe 500 e i test sulla validazione non direbbero niente."""
    monkeypatch.setenv("GOOGLE_API_KEY", "finta")


def test_senza_concorrenti_l_endpoint_lo_dice():
    codice, corpo = _chiama({"url": MIA, "concorrenti": []})
    assert codice.startswith("400")
    assert corpo["rimedio"]


def test_un_indirizzo_storto_non_ferma_gli_altri(monkeypatch):
    """Se ne butta uno, ma il confronto si fa lo stesso e la riga scartata
    compare: sparire in silenzio farebbe credere che fosse stato misurato."""
    altro = "https://www.concorrente.it/"
    _finge(monkeypatch, {(MIA, False): _record(), (altro, False): _record()})
    codice, corpo = _chiama({"url": MIA, "concorrenti": [altro, "non-un-indirizzo"]})
    assert codice.startswith("200")
    assert len(corpo["pagine"]) == 2
    assert corpo["scartati"][0]["url"] == "non-un-indirizzo"
    assert corpo["scartati"][0]["motivo"]


def test_solo_indirizzi_storti_e_un_errore_con_rimedio():
    codice, corpo = _chiama({"url": MIA, "concorrenti": ["pippo", "pluto"]})
    assert codice.startswith("400")
    assert corpo["scartati"] and corpo["rimedio"]


def test_l_endpoint_vuole_post():
    from app import app
    stato = {}

    def avvia(codice, _intestazioni):
        stato["codice"] = codice

    b"".join(app({"PATH_INFO": "/api/gap", "REQUEST_METHOD": "GET"}, avvia))
    assert stato["codice"].startswith("405")


# --- la colonna degli strumenti ---------------------------------------------- #

def _sorgente():
    return (RADICE / "public" / "index.html").read_text(encoding="utf-8")


def test_ogni_strumento_ha_il_suo_pannello():
    """Un pannello che non esiste e' una voce che apre il vuoto."""
    import re
    sorgente = _sorgente()
    pannelli = re.findall(r"pannello: '([a-z-]+)'", sorgente)
    assert len(pannelli) >= 2, pannelli
    for pannello in pannelli:
        assert f'id="{pannello}"' in sorgente, pannello


def test_lo_strumento_aperto_sta_nell_indirizzo():
    """Cosi' si manda a un collega il link del confronto, e ricaricando si resta
    dove si era. In memoria non si potrebbe fare nessuna delle due."""
    sorgente = _sorgente()
    assert "function strumentoDaIndirizzo(" in sorgente
    assert "location.hash" in sorgente
    assert "'hashchange'" in sorgente


def test_la_colonna_chiusa_resta_a_icona():
    """Una navigazione che si nasconde del tutto e' una navigazione che non si
    ritrova."""
    css = _sorgente()
    css = css[css.index("<style>"):css.index("</style>")]
    assert "body.strumenti-chiusi .voce-strumento .nome { display:none; }" in css
    assert "body.strumenti-chiusi .voce-strumento {" in css
