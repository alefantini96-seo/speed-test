"""
Test del consenso fra ripetizioni.

Il caso reale che ha motivato il modulo: tre run consecutivi della stessa URL
hanno dato "attesa pre-download 92%", "89%" e "rendering 79%". Se il tool
dichiarasse la fase dominante da una misurazione sola, attribuirebbe la
responsabilita' alla squadra sbagliata una volta su tre.
"""
import json
from pathlib import Path

from speed.core import consenso, diagnose, extract

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _fatti(fasi, snippet="<img src='hero.jpg'>", discovery=None, timestamp=""):
    return extract.FattiPagina(
        url="https://x.it/", form_factor="PHONE", timestamp=timestamp,
        lcp_fasi=dict(fasi), lcp_elemento_snippet=snippet,
        lcp_discovery=discovery if discovery is not None else {"eagerlyLoaded": False},
    )


# Tre profili: due dominati dall'attesa pre-download, uno dal rendering.
ATTESA_A = {"timeToFirstByte": 6, "resourceLoadDelay": 3134, "resourceLoadDuration": 50,
            "elementRenderDelay": 205}
ATTESA_B = {"timeToFirstByte": 6, "resourceLoadDelay": 3050, "resourceLoadDuration": 40,
            "elementRenderDelay": 340}
RENDERING = {"timeToFirstByte": 6, "resourceLoadDelay": 259, "resourceLoadDuration": 24,
             "elementRenderDelay": 1103}


def test_misurazione_singola_non_e_attendibile():
    """Una sola misurazione non basta a dichiarare la fase dominante."""
    c = consenso.combina([_fatti(ATTESA_A)])
    assert c.ripetizioni == 1
    assert c.attendibile is False
    assert "indicativa" in c.descrizione


# --- la cache di PSI non deve gonfiare il conteggio ------------------------- #

def test_risposte_dalla_cache_non_contano_come_misurazioni():
    """Tre chiamate ravvicinate tornano identiche, stesso analysisUTCTimestamp:
    contarle come tre misurazioni concordi sarebbe una falsa sicurezza."""
    stessa = "2026-08-20T13:46:33.243Z"
    c = consenso.combina([_fatti(ATTESA_A, timestamp=stessa),
                          _fatti(ATTESA_A, timestamp=stessa),
                          _fatti(ATTESA_A, timestamp=stessa)])
    assert c.ripetizioni == 1, "una sola misurazione distinta"
    assert c.richieste == 3
    assert c.cache_rilevata is True
    assert c.attendibile is False
    assert "dalla cache" in c.descrizione


def test_timestamp_diversi_contano_tutte():
    c = consenso.combina([_fatti(ATTESA_A, timestamp="a"),
                          _fatti(ATTESA_B, timestamp="b"),
                          _fatti(RENDERING, timestamp="c")])
    assert c.ripetizioni == 3 and c.richieste == 3
    assert c.cache_rilevata is False


def test_cache_parziale_conta_solo_le_distinte():
    c = consenso.combina([_fatti(ATTESA_A, timestamp="a"),
                          _fatti(ATTESA_A, timestamp="a"),
                          _fatti(RENDERING, timestamp="b")])
    assert c.ripetizioni == 2 and c.richieste == 3
    assert c.cache_rilevata is True


def test_la_dispersione_viene_riportata():
    c = consenso.combina([_fatti(ATTESA_A, timestamp="a"), _fatti(ATTESA_B, timestamp="b"),
                          _fatti(RENDERING, timestamp="c")])
    minimo, massimo = c.dispersione
    assert (minimo, massimo) == (259, 3134), "min e max della fase dominante"
    assert "oscillato fra" in c.descrizione


def test_maggioranza_decide_la_fase_dominante():
    c = consenso.combina([_fatti(ATTESA_A), _fatti(ATTESA_B), _fatti(RENDERING)])
    assert c.fase_dominante == "resourceLoadDelay"
    assert c.concordi == 2 and c.ripetizioni == 3
    assert c.attendibile is True


def test_combina_non_muta_le_misurazioni_ricevute():
    """Era l'unica funzione del core dichiarata pura che modificava un oggetto
    ricevuto: chi passava le sue misurazioni se le ritrovava cambiate."""
    misurazioni = [_fatti(ATTESA_A, timestamp="a"), _fatti(ATTESA_B, timestamp="b"),
                   _fatti(RENDERING, timestamp="c")]
    prima = [dict(m.lcp_fasi) for m in misurazioni]
    consenso.combina(misurazioni)
    assert [dict(m.lcp_fasi) for m in misurazioni] == prima


def test_le_fasi_riportate_sono_le_mediane():
    c = consenso.combina([_fatti(ATTESA_A), _fatti(ATTESA_B), _fatti(RENDERING)])
    assert c.fasi_mediane["resourceLoadDelay"] == 3050    # mediana di 3134, 3050, 259
    assert c.fasi_mediane["elementRenderDelay"] == 340    # mediana di 205, 340, 1103
    assert c.fatti.lcp_fasi == c.fasi_mediane, \
        "i fatti rappresentativi devono portare le mediane, non un singolo run"


def test_senza_maggioranza_il_risultato_e_dichiarato_inaffidabile():
    solo_tbt = {"timeToFirstByte": 900, "resourceLoadDelay": 10,
                "resourceLoadDuration": 5, "elementRenderDelay": 20}
    c = consenso.combina([_fatti(ATTESA_A), _fatti(RENDERING), _fatti(solo_tbt)])
    assert c.concordi == 1
    assert c.attendibile is False
    assert "NON concordano" in c.descrizione


def test_instabilita_di_elemento_e_checklist_viene_rilevata():
    c = consenso.combina([
        _fatti(ATTESA_A, snippet="<img src='a.jpg'>", discovery={"eagerlyLoaded": False}),
        _fatti(ATTESA_B, snippet="<h1>altro</h1>", discovery={"eagerlyLoaded": True}),
    ])
    assert c.elemento_stabile is False
    assert c.checklist_stabile is False


def test_due_misurazioni_reali_della_stessa_pagina():
    """Due risposte PSI vere, prese a novanta secondi di distanza sulla stessa URL.

    Sono misurazioni distinte (timestamp diversi) e NON concordano sulla fase
    dominante: e' il caso che il tool deve saper dichiarare invece di nascondere.
    Cio' che resta identico e' l'elemento LCP e la checklist, che dipendono
    dall'HTML e non dalla rete.
    """
    misurazioni = [
        extract.estrai(json.loads((FIXTURES / nome).read_text(encoding="utf-8")),
                       "https://www.bbc.com/", "PHONE", ["bbci.co.uk"])
        for nome in ("psi-bbc-mobile-it.json", "psi-bbc-mobile-it-2.json")
    ]
    c = consenso.combina(misurazioni)
    assert c.ripetizioni == 2, "timestamp diversi: due misurazioni distinte"
    assert c.cache_rilevata is False
    assert c.elemento_stabile and c.checklist_stabile
    assert c.attendibile is False, "due misurazioni discordi non fanno maggioranza"
    assert "NON concordano" in c.descrizione


# --- effetto sulla diagnosi ------------------------------------------------- #

def test_la_discordanza_arriva_nel_report():
    c = consenso.combina([_fatti(ATTESA_A), _fatti(RENDERING),
                          _fatti({"timeToFirstByte": 900, "resourceLoadDelay": 10,
                                  "resourceLoadDuration": 5, "elementRenderDelay": 20})])
    p = diagnose.classifica_lcp(c.fatti, {"largest_contentful_paint": 3699.0}, c)
    assert "discordanti" in p.titolo
    assert "da confermare" in p.responsabile
    assert "NON concordano" in p.nota


def test_la_concordanza_non_sporca_il_titolo():
    c = consenso.combina([_fatti(ATTESA_A), _fatti(ATTESA_B), _fatti(RENDERING)])
    p = diagnose.classifica_lcp(c.fatti, {"largest_contentful_paint": 3699.0}, c)
    assert "discordanti" not in p.titolo
    assert "da confermare" not in p.responsabile
    assert "2 misurazioni distinte su 3" in p.nota
