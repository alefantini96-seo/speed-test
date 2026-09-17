"""
Test dei due renderer e delle convenzioni di naming.

Il run di prova non e' un file statico: viene composto qui dai fixture reali,
seguendo la stessa sequenza della CLI. Cosi' i test coprono anche la composizione,
e non c'e' un artefatto in piu' da tenere allineato a mano.
"""
import json
from pathlib import Path

import pytest
from docx import Document

from speed.cli import _nomi
from speed.config import Config, Template
from speed.core import consenso, diagnose, extract, thirdparty
from speed.io import crux, render, render_docx

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
URL = "https://www.bbc.com/"
PROPRI = ["bbci.co.uk"]


def _carica(nome):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def _campo():
    """Voce `campo` come la compone la CLI, usando il parsing vero di crux.py."""
    record = crux.leggi_record(_carica("crux-bbc.json"))
    storico = crux.leggi_storico(_carica("crux-history-bbc.json"))
    return {"livello": "url", "metriche": record["metriche"],
            "storico": {"url": URL} | storico}


@pytest.fixture(scope="module")
def esecuzione():
    misurazioni = [extract.estrai(_carica(nome), URL, "PHONE", PROPRI)
                   for nome in ("psi-bbc-mobile-it.json", "psi-bbc-mobile-it-2.json")]
    accordo = consenso.combina(misurazioni)
    fatti = accordo.fatti
    campo = _campo()
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    problemi = diagnose.diagnostica(fatti, campo["metriche"], riepilogo, accordo)

    esecuzione = {
        "cliente": "Esempio", "sito": URL, "data": "2026-08-20", "form_factor": "PHONE",
        "pagine": [{
            "template": "Home", "url": URL, "fatti": fatti, "campo": campo,
            "terze_parti": riepilogo, "problemi": problemi,
            "misurazioni": accordo.ripetizioni, "concordi": accordo.concordi,
            "consenso": accordo.descrizione,
        }],
    }
    # I renderer lavorano sulla forma JSON, non sugli oggetti in memoria.
    from speed.cli import _serializza
    return json.loads(json.dumps(esecuzione, default=_serializza, ensure_ascii=False))


# --- HTML ------------------------------------------------------------------ #

def test_html_e_self_contained(esecuzione):
    h = render.html_report(esecuzione)
    assert "<script" not in h, "nessun JavaScript: il file deve aprirsi anche offline"
    assert "http://" not in h.split("<body>")[0], "nessuna risorsa esterna nell'head"
    assert "<svg" in h, "lo storico va reso come sparkline inline"


def test_html_dichiara_i_limiti(esecuzione):
    h = render.html_report(esecuzione)
    assert "28 giorni" in h, "va detto che il campo e' una media mobile"
    assert "non calibrata" in h or "non vengono usati" in h.replace("\n", " ")


def test_html_dichiara_la_provenienza_del_testo(esecuzione):
    h = render.html_report(esecuzione)
    assert "testo di Lighthouse" in h
    assert "classificazione su dati di campo" in h,         "i fixture CrUX hanno le fasi LCP: il report deve dire che vengono dal campo"


def test_html_riporta_le_risorse_colpevoli(esecuzione):
    h = render.html_report(esecuzione)
    assert "risorse" in h and "impatto" in h


def test_html_dichiara_quante_misurazioni(esecuzione):
    assert "misurazioni di laboratorio" in render.html_report(esecuzione)


# --- cio' che si vede del caricamento --------------------------------------- #

@pytest.fixture(scope="module")
def con_redirect():
    """Un run a un template dalla risposta con redirect e quattro categorie."""
    fatti = extract.estrai(_carica("psi-bbc-redirect-categorie.json"),
                           "http://bbc.com/", "PHONE", PROPRI)
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    esecuzione = {
        "cliente": "Esempio", "sito": URL, "data": "2026-09-15", "form_factor": "PHONE",
        "pagine": [{"template": "Home", "url": "http://bbc.com/", "fatti": fatti,
                    "campo": _campo(), "terze_parti": riepilogo, "problemi": [],
                    "misurazioni": 1, "concordi": 1, "consenso": ""}],
    }
    from speed.cli import _serializza
    return json.loads(json.dumps(esecuzione, default=_serializza, ensure_ascii=False))


def test_il_filmstrip_resta_self_contained(esecuzione):
    """I fotogrammi arrivano gia' come data URI: il report non punta a file."""
    h = render.html_report(esecuzione)
    assert "Come si vede la pagina mentre carica" in h
    assert 'src="data:image/jpeg;base64,' in h
    assert "<img src=\"http" not in h


def test_la_cascata_ha_una_barra_per_richiesta(esecuzione):
    h = render.html_report(esecuzione)
    assert "Cascata delle richieste" in h
    fatti = esecuzione["pagine"][0]["fatti"]
    assert h.count('class="linea"') == len(fatti["richieste"])


def test_nessuna_barra_della_cascata_esce_dal_grafico(esecuzione):
    """Le percentuali finiscono in uno `style`, dove un errore non si vede:
    la somma delle tre parti di ogni barra deve stare dentro la cella."""
    import re
    h = render.html_report(esecuzione)
    for cella in re.findall(r'<td class="linea">(.*?)</td>', h):
        larghezze = [float(x) for x in re.findall(r"width:([0-9.]+)%", cella)]
        assert sum(larghezze) <= 100.2, cella[:120]


def test_ogni_riferimento_del_righello_ha_la_sua_riga():
    """Le etichette si sovrapponevano: la scala della cascata arriva all'ultima
    richiesta - su una pagina con beacon di analytics sono decine di secondi -
    mentre i paint stanno tutti nei primi cinque, quindi i riferimenti si
    ammassano. Girarne tre a rotazione non bastava; una riga ciascuno rende la
    sovrapposizione impossibile invece che improbabile.

    Misurato su www.pluxee.it il 17/09/2026: scala 8.430 ms e quattro
    riferimenti su cinque fra il 30% e il 54%."""
    import re

    from speed.io import render

    disegno = render.cascata(
        [extract.Richiesta(url="https://x.it/a.js", host="x.it", byte=10, tipo="Script",
                           partita=10.0, finita=20.0)],
        {"DOM pronto": 2535.0, "FCP osservato": 3317.0, "Caricata": 3826.0,
         "LCP osservato": 4538.0, "Ultimo cambio visivo": 6944.0},
        "https://x.it/")
    assert len(disegno.riferimenti) == 5

    html = render._cascata({"richieste": [{"url": "https://x.it/a.js", "host": "x.it",
                                           "byte": 10, "tipo": "Script",
                                           "partita": 10.0, "finita": 20.0}],
                            "tempi_osservati": {
                                "DOM pronto": 2535.0, "FCP osservato": 3317.0,
                                "Caricata": 3826.0, "LCP osservato": 4538.0,
                                "Ultimo cambio visivo": 6944.0}},
                           "https://x.it/")
    righello = html[html.index('class="righello"'):html.index("</div>", html.index('class="righello"'))]
    alti = re.findall(r"top:(\d+)px", righello)
    assert len(alti) == 5, righello[:200]
    assert len(set(alti)) == 5, f"due riferimenti sulla stessa riga: {alti}"


def test_la_cascata_e_il_peso_dicono_la_stessa_cosa_sulle_terze_parti(esecuzione):
    """Il difetto: la cascata non riceveva i domini dichiarati e marcava terze
    parti gli stessi host che il paragrafo sopra contava prima parte. Su questo
    run erano 118 richieste su 126 con la targhetta 3P sotto "23% di terze
    parti" - due risposte diverse alla stessa domanda, nello stesso documento."""
    con_domini = dict(esecuzione, domini_propri=PROPRI)
    h = render.html_report(con_domini)
    prime = h.count(">1P</span>")
    terze = h.count(">3P</span>")
    assert prime > terze, f"1P={prime} 3P={terze}: i domini dichiarati non arrivano"

    # Senza dichiararli si torna al comportamento di prima, senza rompersi.
    senza = render.html_report({k: v for k, v in con_domini.items()
                                if k != "domini_propri"})
    assert senza.count(">3P</span>") > h.count(">3P</span>")


def test_il_run_salvato_porta_i_domini_dichiarati():
    """Il report si rigenera da un JSON salvato mesi prima: se la chiave non
    finisce li', `speed report` non puo' sapere quali domini erano del cliente."""
    sorgente = (FIXTURES.parent / "speed" / "cli.py").read_text(encoding="utf-8")
    assert '"domini_propri": list(conf.domini_propri or ())' in sorgente


def test_la_cascata_dichiara_che_i_tempi_sono_osservati(esecuzione):
    """Sono un'altra scala rispetto alle metriche riportate da Lighthouse.
    Senza la riga, il lettore confronta numeri che non si confrontano."""
    h = render.html_report(esecuzione).replace("\n", " ")
    assert "osservati dal trace" in h
    assert "simulate" in h


def test_le_misure_di_laboratorio_dicono_da_dove_arriva_il_ttfb(esecuzione):
    h = render.html_report(esecuzione).replace("\n", " ")
    assert "Altre misure di laboratorio" in h
    assert "data center Google" in h


def test_la_catena_di_redirect_compare_col_tempo_perso(con_redirect):
    h = render.html_report(con_redirect)
    assert "Prima del documento" in h
    assert "http://bbc.com/" in h and "https://www.bbc.com/" in h
    assert "301" in h


def test_senza_redirect_la_sezione_non_compare(esecuzione):
    assert "Prima del documento" not in render.html_report(esecuzione)


def test_i_punteggi_delle_altre_categorie_sono_dichiarati_riferimento(con_redirect):
    h = render.html_report(con_redirect).replace("\n", " ")
    assert "Punteggi Lighthouse" in h
    assert "Accessibilit" in h and "Best practice" in h
    assert "Riferimento, non valutazione" in h


def test_con_la_sola_performance_i_punteggi_non_compaiono(esecuzione):
    """Un riquadro con un numero solo non e' un confronto: non si stampa."""
    assert "Punteggi Lighthouse" not in render.html_report(esecuzione)


# --- DOCX ------------------------------------------------------------------ #

def _testo_docx(percorso):
    doc = Document(str(percorso))
    parti = [p.text for p in doc.paragraphs]
    for tabella in doc.tables:
        for riga in tabella.rows:
            parti += [c.text for c in riga.cells]
    return "\n".join(parti)


def test_docx_si_genera(esecuzione, tmp_path):
    percorso = render_docx.docx_report(esecuzione, tmp_path / "r.docx")
    assert percorso.exists() and percorso.stat().st_size > 10_000


def test_docx_contiene_gli_stessi_fatti_dell_html(esecuzione, tmp_path):
    testo = _testo_docx(render_docx.docx_report(esecuzione, tmp_path / "r.docx"))
    for atteso in ("p75 reale", "testo di Lighthouse", "28 giorni",
                   "misurazioni di laboratorio", "Interventi"):
        assert atteso in testo, f"manca nel DOCX: {atteso}"


def test_docx_ha_la_tabella_del_campo(esecuzione, tmp_path):
    doc = Document(str(render_docx.docx_report(esecuzione, tmp_path / "r.docx")))
    assert doc.tables, "il campo va reso come tabella, non come testo"
    intestazione = [c.text for c in doc.tables[0].rows[0].cells]
    assert "Metrica" in intestazione and "p75 reale" in intestazione


def test_sparkline_a_blocchi():
    assert render_docx._sparkline([1, 2, 3, 4, 5])
    assert render_docx._sparkline([None, None]) == "", "serie vuota -> nessuna sparkline"
    assert render_docx._sparkline([5]) == "", "un punto solo non e' un andamento"


# --- naming ---------------------------------------------------------------- #

def _config(output):
    return Config(cliente="Cliente Uno", sito="https://x.it",
                  template=[Template(nome="Home", url="https://x.it/")], output=output)


def test_nome_senza_cliente_se_scrive_nella_cartella_cliente():
    _, report = _nomi(_config("C:/Clienti/Uno/05_Report"))
    assert "Cliente" not in report and report.startswith("Report velocità ")


def test_nome_con_cliente_se_scrive_in_out():
    _, report = _nomi(_config(""))
    assert "Cliente-Uno" in report


def test_nessuna_versione_nel_nome():
    for output in ("", "C:/Clienti/Uno"):
        dati, report = _nomi(_config(output))
        assert "_v" not in report and "finale" not in report.lower()
        assert dati != report, "dati e report non devono collidere"
