"""
Test del documento tecnico in Markdown.

Il lettore e' chi mette mano al codice, e la differenza dal report al cliente non
e' cosmetica: qui le liste sono complete e la chiave dell'audit e' scritta. I test
presidiano proprio quello — che non ricompaia il troncamento a sei che va bene in
una scheda ma non a chi deve aprire i file.

Il run di prova si compone dai fixture con la stessa sequenza della CLI, come in
test_render.py: cosi' non c'e' un artefatto in piu' da tenere allineato a mano.
"""
import json
import re
from pathlib import Path

import pytest

from speed.cli import _serializza, _stem_tecnico
from speed.core import consenso, diagnose, extract, thirdparty
from speed.io import crux, render_md

RADICE = Path(__file__).resolve().parent.parent
FIXTURES = RADICE / "fixtures"
URL = "https://www.bbc.com/"
PROPRI = ["bbci.co.uk"]


def _carica(nome):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def _metriche_campo():
    return crux.leggi_record(_carica("crux-bbc.json"))["metriche"]


def _pagina(nome, url, fixture, metriche):
    accordo = consenso.combina([extract.estrai(_carica(fixture), url, "PHONE", PROPRI)])
    fatti = accordo.fatti
    riepilogo = thirdparty.riepiloga(fatti.richieste, url, PROPRI)
    return {
        "template": nome, "url": url, "fatti": fatti,
        "campo": {"livello": "url", "metriche": metriche, "periodo_a": "2026-08-18"},
        "terze_parti": riepilogo,
        "peso_per_tipo": thirdparty.peso_per_tipo(fatti.richieste),
        "problemi": diagnose.diagnostica(fatti, metriche, riepilogo, accordo),
        "misurazioni": accordo.ripetizioni, "concordi": accordo.concordi,
        "consenso": accordo.descrizione,
    }


def _esecuzione(pagine):
    grezza = {"cliente": "Esempio", "sito": "https://www.bbc.com", "data": "2026-08-20",
              "form_factor": "PHONE", "ordinamento_pesato": False, "pagine": pagine}
    # Il renderer lavora sulla forma JSON, non sugli oggetti in memoria.
    return json.loads(json.dumps(grezza, default=_serializza, ensure_ascii=False))


@pytest.fixture(scope="module")
def esecuzione():
    """Due template piu' una pagina fallita: e' la forma che il documento deve reggere."""
    metriche = _metriche_campo()
    return _esecuzione([
        _pagina("Home", URL, "psi-bbc-mobile-it.json", metriche),
        _pagina("Articolo", "https://www.bbc.com/news", "psi-bbc-mobile-it-2.json", metriche),
        {"template": "Video", "url": "https://www.bbc.com/video",
         "errore": "PageSpeed Insights: non e' riuscito ad analizzare la pagina."},
    ])


@pytest.fixture(scope="module")
def documento(esecuzione):
    return render_md.markdown_report(esecuzione)


@pytest.fixture(scope="module")
def solo_home(esecuzione):
    """Una pagina sola: serve a contare le righe di un audit senza raddoppiarle."""
    return render_md.markdown_report(
        {**esecuzione, "pagine": [esecuzione["pagine"][0]]})


def _opportunita(esecuzione, audit):
    for opportunita in esecuzione["pagine"][0]["fatti"]["opportunita"]:
        if opportunita["audit"] == audit:
            return opportunita
    raise AssertionError(f"{audit} non e' nel run di prova")


def _blocco(documento, audit):
    """Il testo del blocco di un audit, fino al successivo."""
    inizio = documento.index(f"#### `{audit}`")
    resto = documento.index("\n#### ", inizio + 1) if "\n#### " in documento[inizio + 1:] \
        else len(documento)
    return documento[inizio:resto]


# --- i link vengono da Lighthouse, non da noi -------------------------------- #

def test_ogni_audit_con_documentazione_ha_il_suo_link(esecuzione, documento):
    """12 audit su 13 portano un URL nella descrizione: nel documento diventano
    link cliccabili a quell'URL, non a un altro."""
    con_link = 0
    for opportunita in esecuzione["pagine"][0]["fatti"]["opportunita"]:
        url = opportunita.get("documentazione")
        if not url:
            continue
        con_link += 1
        assert f"[Documentazione Google]({url})" in documento, opportunita["audit"]
    assert con_link >= 12, "il fixture deve avere almeno dodici audit con documentazione"


def test_l_audit_senza_documentazione_non_ne_riceve_una_inventata(documento):
    """script-treemap-data non ha un link nella descrizione: si omette, non si
    cerca un sostituto plausibile."""
    assert not _opportunita_documentazione_di(documento)


def _opportunita_documentazione_di(documento):
    blocco = _blocco(documento, "script-treemap-data")
    return re.findall(r"\[Documentazione Google\]\(([^)]+)\)", blocco)


def test_i_link_del_documento_sono_solo_quelli_di_lighthouse(esecuzione, documento):
    """Nessun URL di documentazione che non venga dai dati del run."""
    leciti = {o.get("documentazione") for pagina in esecuzione["pagine"]
              for o in (pagina.get("fatti") or {}).get("opportunita") or []}
    for url in re.findall(r"\[Documentazione Google\]\(([^)]+)\)", documento):
        assert url in leciti


# --- le liste non sono troncate ---------------------------------------------- #

def test_le_liste_sono_complete_non_troncate_a_sei(esecuzione, solo_home):
    """E' il punto della feature: `problemi` porta sei risorse, il documento
    tecnico le porta tutte e ventiquattro."""
    opportunita = _opportunita(esecuzione, "cache-insight")
    assert len(opportunita["risorse"]) == 24, "il fixture deve avere 24 risorse"

    problema = next(p for p in esecuzione["pagine"][0]["problemi"]
                    if p["codice"] == "cache-insight")
    assert len(problema["risorse"]) == 6, "la scheda del cliente resta a sei"

    blocco = _blocco(solo_home, "cache-insight")
    numerate = re.findall(r"^\| (\d+) \| ", blocco, flags=re.M)
    assert numerate[-1] == "24", f"la tabella si ferma a {numerate[-1]} righe"


def test_la_lista_lunghissima_si_chiude_ma_non_si_taglia(esecuzione, solo_home):
    """script-treemap-data ha 83 file: stanno in un `<details>`, tutti."""
    assert len(_opportunita(esecuzione, "script-treemap-data")["risorse"]) == 83
    blocco = _blocco(solo_home, "script-treemap-data")
    assert "<details>" in blocco
    numerate = re.findall(r"^\| (\d+) \| ", blocco, flags=re.M)
    assert numerate[-1] == "83"


def test_le_liste_corte_restano_aperte(solo_home):
    """Un `<details>` su tre righe e' un clic in piu' per niente."""
    assert "<details>" not in _blocco(solo_home, "unminified-css")


# --- quello che serve a chi sviluppa ----------------------------------------- #

def test_il_documento_nomina_la_chiave_dell_audit(documento):
    """Serve a rilanciare Lighthouse e a cercare nei changelog: va scritta com'e'."""
    for chiave in ("cache-insight", "bootup-time", "cls-culprits-insight",
                   "network-dependency-tree-insight"):
        assert f"#### `{chiave}`" in documento


def test_i_selettori_e_i_percorsi_dom_compaiono(esecuzione, documento):
    for audit in ("cls-culprits-insight", "image-delivery-insight"):
        elementi = _opportunita(esecuzione, audit)["elementi"]
        assert elementi, f"{audit} deve nominare elementi nel fixture"
        for elemento in elementi[:3]:
            if elemento.get("selettore"):
                assert elemento["selettore"] in documento, audit
            if elemento.get("percorso"):
                assert elemento["percorso"] in documento, audit


def test_i_file_sono_ordinati_per_spreco_decrescente(solo_home):
    blocco = _blocco(solo_home, "bootup-time")
    tempi = [float(v) for v in re.findall(r"\| (\d+) ms \|", blocco)]
    assert tempi == sorted(tempi, reverse=True) and len(tempi) > 3


def test_ogni_file_e_marcato_prima_o_terza_parte(solo_home):
    blocco = _blocco(solo_home, "unused-javascript")
    assert "| 1P |" in blocco and "| 3P |" in blocco


def test_il_cls_non_esce_in_millisecondi(esecuzione, solo_home):
    """`formatta_risparmio` sa che il CLS e' adimensionale: il documento lo usa."""
    risparmi = _opportunita(esecuzione, "cls-culprits-insight").get("risparmi") or {}
    if "CLS" in risparmi:
        assert "CLS 0.095" in solo_home or "CLS 0,095" in solo_home
        assert "CLS 0 ms" not in solo_home


# --- l'origine della ripartizione LCP e' dichiarata -------------------------- #

def test_ripartizione_lcp_dal_campo_e_dichiarata(documento):
    assert "origine: campo CrUX" in documento


def test_ripartizione_lcp_dal_laboratorio_e_dichiarata():
    """Senza le metriche `largest_contentful_paint_image_*` CrUX non espone le
    fasi e si ricade sul laboratorio: il documento deve dirlo, perche' la
    differenza decide chi interviene (ADR-005)."""
    metriche = {k: v for k, v in _metriche_campo().items()
                if "largest_contentful_paint_image" not in k}
    documento = render_md.markdown_report(_esecuzione(
        [_pagina("Home", URL, "psi-bbc-mobile-it.json", metriche)]))
    assert "origine: laboratorio" in documento
    assert "origine: campo CrUX" not in documento


# --- niente sparisce in silenzio --------------------------------------------- #

def test_la_pagina_fallita_compare_dichiarata(documento):
    assert "**non riuscita**" in documento
    assert "## Video" in documento
    assert "Misurazione non riuscita" in documento


def test_gli_audit_non_azionabili_restano_col_loro_motivo():
    """Lo sviluppatore deve poter vedere perche' cache-insight non gli e' stato
    assegnato, non trovarselo sparito.

    Senza domini propri dichiarati le risorse di cache-insight risultano tutte di
    terze parti e l'audit non e' azionabile: e' il caso reale che il motivo serve
    a spiegare. Con `bbci.co.uk` dichiarato l'audit torna azionabile, ed e' giusto
    cosi' — quei file sono del cliente.
    """
    global PROPRI
    originali = PROPRI
    try:
        PROPRI = []
        documento = render_md.markdown_report(_esecuzione(
            [_pagina("Home", URL, "psi-bbc-mobile-it.json", _metriche_campo())]))
    finally:
        PROPRI = originali
    blocco = _blocco(documento, "cache-insight")
    assert "fuori dal master plan" in blocco
    assert "non azionabile" in blocco


def test_l_artefatto_di_dati_e_marcato_come_tale(documento):
    blocco = _blocco(documento, "script-treemap-data")
    assert "artefatto di dati" in blocco


# --- ADR-004: nessuna raccomandazione scritta da noi ------------------------- #

def test_i_titoli_degli_interventi_sono_quelli_di_lighthouse(esecuzione, documento):
    """Il titolo non si riscrive: si copia."""
    titoli = {p["codice"]: p["titolo"] for p in esecuzione["pagine"][0]["problemi"]}
    for riga in documento.splitlines():
        if not riga.startswith("#### `"):
            continue
        codice, titolo = riga[6:].split("` — ", 1)
        assert titolo == titoli[codice].replace("<", "&lt;")


def test_le_descrizioni_sono_quelle_di_lighthouse(esecuzione, documento):
    for opportunita in esecuzione["pagine"][0]["fatti"]["opportunita"]:
        descrizione = opportunita.get("descrizione")
        if descrizione:
            assert descrizione.replace("<", "&lt;") in documento, opportunita["audit"]


def test_nessuna_azione_scritta_a_mano(documento):
    """L'invariante di ADR-004, esteso al nuovo renderer."""
    testo = documento.lower()
    for inventata in ("inventario dei tag", "valutare una facade", "digital pr",
                      "consigliamo", "suggeriamo", "ti consigliamo", "dovresti"):
        assert inventata not in testo


def test_il_renderer_non_contiene_imperativi_propri():
    """Le intestazioni e le etichette che scriviamo noi sono nomi di sezione, non
    istruzioni: l'unica voce imperativa del documento dev'essere di Lighthouse."""
    sorgente = (RADICE / "speed" / "io" / "render_md.py").read_text(encoding="utf-8")
    # Solo le stringhe letterali: i commenti spiegano, non finiscono nel documento.
    letterali = " ".join(re.findall(r'"([^"]{4,})"', sorgente)).lower()
    for imperativo in ("riduci ", "verifica ", "controlla ", "ottimizza ",
                       "elimina ", "rimuovi ", "aggiungi ", "imposta "):
        assert imperativo not in letterali, f"«{imperativo.strip()}» e' un'istruzione nostra"


def test_il_punteggio_psi_sta_in_fondo_e_dichiarato(documento):
    """ADR-001: non entra in nessuna valutazione. Se compare, compare come vetrina.

    La frase ricorre due volte di proposito: fra i limiti in testata, dove
    dichiara cosa il documento NON usa, e nel piede accanto ai numeri.
    """
    piede = documento.rsplit("---", 1)[-1].lower()
    assert "numero di vetrina" in piede
    assert "punteggi pagespeed insights" in piede
    corpo = documento[:documento.rindex("---")]
    assert "performance_score" not in corpo
    assert corpo.count("Punteggi PageSpeed") == 0, "il punteggio non entra negli interventi"


# --- forma e robustezza ------------------------------------------------------ #

def test_nessun_html_attivo_fuori_dai_blocchi_richiudibili(documento):
    """Gli snippet di Lighthouse sono markup vero: dentro un code span sono
    inerti, fuori venivano interpretati e la riga spariva dal documento."""
    senza_codice = re.sub(r"`{1,6}[^`]*`{1,6}", "", documento, flags=re.S)
    tag = set(re.findall(r"<(/?[a-zA-Z][a-zA-Z0-9]*)", senza_codice))
    assert tag <= {"details", "/details", "summary", "/summary"}, tag


def test_le_tabelle_hanno_celle_coerenti(documento):
    """Una pipe non scappata dentro una cella sfonda la tabella."""
    for blocco in re.findall(r"(?:^\|.*\|$\n)+", documento, flags=re.M):
        righe = [r for r in blocco.strip().splitlines()]
        colonne = righe[0].count("|")
        for riga in righe:
            assert riga.count("|") == colonne, riga[:120]


def test_un_run_senza_opportunita_lo_dichiara(esecuzione):
    """La versione web scarta `opportunita` per stare nel limite del corpo: il
    documento generato da un run cosi' deve dirlo, non uscire mutilo in silenzio."""
    pagina = json.loads(json.dumps(esecuzione["pagine"][0]))
    pagina["fatti"].pop("opportunita")
    documento = render_md.markdown_report({**esecuzione, "pagine": [pagina]})
    assert "salvato dalla versione web" in documento


def test_un_run_vuoto_non_esplode():
    documento = render_md.markdown_report({"cliente": "X", "pagine": []})
    assert "Interventi tecnici" in documento


def test_il_nome_del_file_distingue_il_documento_tecnico():
    assert _stem_tecnico("Report velocità 20082026") == "Interventi tecnici 20082026"
    assert _stem_tecnico("Report velocità Ferroli 20082026") == \
        "Interventi tecnici Ferroli 20082026"


# --- l'esempio committato resta allineato ------------------------------------ #

def test_l_esempio_committato_e_aggiornato():
    """Se questo fallisce: `python scripts/esempio_md.py`.

    L'esempio serve a vedere il deliverable senza lanciare una scansione: se resta
    indietro rispetto al renderer mostra un documento che il tool non produce piu'.
    """
    import sys
    sys.path.insert(0, str(RADICE / "scripts"))
    from esempio_md import DESTINAZIONE, esecuzione_di_prova

    atteso = render_md.markdown_report(esecuzione_di_prova())
    assert DESTINAZIONE.exists(), "manca docs/esempio-interventi-tecnici.md"
    assert DESTINAZIONE.read_text(encoding="utf-8") == atteso, \
        "esempio non allineato: rilancia `python scripts/esempio_md.py`"
