"""
Test del confronto fra due scansioni.

Le due avvertenze devono comparire nell'output e non solo nel codice: chi legge il
risultato non apre il sorgente. Verificato su entrambe le uscite, terminale e HTML.
"""
import json

from speed.core import confronto
from speed.io import render_confronto


def _pagina(template, url, codici, metriche):
    return {"template": template, "url": url,
            "problemi": [{"codice": c, "titolo": f"Titolo {c}"} for c in codici],
            "campo": {"livello": "url", "metriche": metriche}}


def _run(data, *pagine):
    return {"cliente": "X", "sito": "https://x.it", "data": data,
            "form_factor": "PHONE", "pagine": list(pagine)}


CAMPO_PRIMA = {"largest_contentful_paint": 4180.0, "interaction_to_next_paint": 210.0,
               "cumulative_layout_shift": 0.12}
CAMPO_DOPO = {"largest_contentful_paint": 2300.0, "interaction_to_next_paint": 205.0,
              "cumulative_layout_shift": 0.12}


# --- problemi ---------------------------------------------------------------- #

def test_spariti_comparsi_restati():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/",
                                   ["unused-javascript", "cache-insight"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/",
                                   ["cache-insight", "font-display"], CAMPO_DOPO)))
    voce = esito.template[0]
    assert [c for c, _t in voce.spariti] == ["unused-javascript"]
    assert [c for c, _t in voce.comparsi] == ["font-display"]
    assert [c for c, _t in voce.restati] == ["cache-insight"]


def test_il_confronto_si_regge_sull_url_non_sul_nome():
    """Il nome del template puo' cambiare fra una scansione e l'altra: l'indirizzo
    e' cio' che identifica la stessa misurazione."""
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Homepage", "https://x.it/", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"], CAMPO_DOPO)))
    assert len(esito.template) == 1
    assert esito.template[0].template == "Home", "vale il nome della scansione nuova"


def test_i_template_non_comuni_sono_dichiarati():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Vecchio", "https://x.it/v", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Nuovo", "https://x.it/n", ["a"], CAMPO_DOPO)))
    assert esito.solo_prima == ["Vecchio"] and esito.solo_dopo == ["Nuovo"]
    assert esito.template == [], "senza URL comuni non c'e' niente da confrontare"


# --- movimento del campo ------------------------------------------------------ #

def test_il_movimento_del_campo_viene_descritto():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"], CAMPO_DOPO)))
    lcp = [m for m in esito.template[0].metriche
           if m.metrica == "largest_contentful_paint"][0]
    assert lcp.verso == "migliorato"
    assert lcp.delta == -1880.0
    assert "4180 ms" in lcp.descrivi() and "2300 ms" in lcp.descrivi()


def test_il_cambio_di_giudizio_viene_detto():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"], CAMPO_DOPO)))
    lcp = [m for m in esito.template[0].metriche
           if m.metrica == "largest_contentful_paint"][0]
    assert lcp.cambia_giudizio is True
    assert "da scarso a buono" in lcp.descrivi(), "4180 ms e' scarso, 2300 buono"


def test_un_movimento_minimo_e_stabile():
    """Sotto il 5% non si commenta: sarebbe rumore spacciato per risultato."""
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"],
                                   {"largest_contentful_paint": 2000.0})),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"],
                                   {"largest_contentful_paint": 2040.0})))
    assert esito.template[0].metriche[0].verso == "stabile"


def test_un_peggioramento_e_riconosciuto():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"],
                                   {"largest_contentful_paint": 2000.0})),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"],
                                   {"largest_contentful_paint": 3500.0})))
    assert esito.template[0].metriche[0].verso == "peggiorato"


def test_metrica_mancante_in_una_scansione():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], {})),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"],
                                   {"largest_contentful_paint": 2000.0})))
    movimento = esito.template[0].metriche[0]
    assert movimento.verso == "sconosciuto"
    assert "dato mancante" in movimento.descrivi()


# --- le avvertenze devono uscire ---------------------------------------------- #

def test_le_due_avvertenze_esistono():
    assert len(confronto.AVVERTENZE) == 2
    testo = " ".join(confronto.AVVERTENZE)
    assert "28 giorni" in testo
    assert "oscilla" in testo and "non e' di per se' un risultato" in testo


def test_le_avvertenze_compaiono_nell_html():
    """Nel sorgente gli apostrofi sono entita' HTML: si confronta la forma
    codificata, che e' quella che il browser rende identica al testo."""
    from html import escape
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"], CAMPO_DOPO)))
    html = render_confronto.html_confronto(esito)
    for avvertenza in confronto.AVVERTENZE:
        assert escape(avvertenza[:60]) in html


def test_l_html_e_self_contained():
    esito = confronto.confronta(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], CAMPO_PRIMA)),
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["b"], CAMPO_DOPO)))
    html = render_confronto.html_confronto(esito)
    assert "<script" not in html
    assert "Spariti" in html and "Comparsi" in html


# --- forma JSON --------------------------------------------------------------- #

def test_funziona_su_run_salvati():
    """Come `speed report` e `speed masterplan`: si parte dalla forma JSON."""
    prima = json.loads(json.dumps(
        _run("2026-06-20", _pagina("Home", "https://x.it/", ["a"], CAMPO_PRIMA))))
    dopo = json.loads(json.dumps(
        _run("2026-08-21", _pagina("Home", "https://x.it/", ["a"], CAMPO_DOPO))))
    assert confronto.confronta(prima, dopo).template
