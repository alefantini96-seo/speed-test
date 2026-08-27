"""
Test dell'aggregazione del master plan.

Il frammento e' consumato da uno script esterno al repo che impagina l'xlsx:
qui si verifica la forma, l'aggregazione per sito e le regole del registro.
"""
import json
from pathlib import Path

import pytest

from speed.core import masterplan

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _problema(codice, gravita="media", peso=1.0, fonte="lighthouse", titolo=None,
              azioni=("Descrizione Lighthouse",), azionabile=True, metrica="",
              evidenza=(), risorse=(), elementi=(), azione_breve=""):
    return {
        "codice": codice, "titolo": titolo or f"Titolo {codice}", "gravita": gravita,
        "responsabile": "sviluppo", "fonte": fonte, "azioni": list(azioni),
        "evidenza": list(evidenza), "risorse": [list(r) for r in risorse],
        "elementi": [list(e) for e in elementi], "azionabile": azionabile,
        "peso": peso, "metrica": metrica, "azione_breve": azione_breve, "risparmio": 0.0,
    }


def _pagina(template, url, problemi, metriche=None):
    return {"template": template, "url": url, "problemi": problemi,
            "campo": {"livello": "url", "metriche": metriche or {}}}


def _esecuzione(*pagine, pesato=True):
    return {"cliente": "X", "sito": "https://x.it", "data": "2026-08-21",
            "form_factor": "PHONE", "ordinamento_pesato": pesato, "pagine": list(pagine)}


# --- aggregazione ------------------------------------------------------------ #

def test_una_riga_per_tipo_non_per_template():
    """Tre template con lo stesso problema danno UNA riga, non tre."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("unused-javascript")]),
        _pagina("Cat", "https://x.it/c", [_problema("unused-javascript")]),
        _pagina("Prod", "https://x.it/p", [_problema("unused-javascript")]),
    ))
    assert len(frammento["masterplan"]) == 1
    assert "su 3 template su 3" in frammento["masterplan"][0]["problema"]


def test_il_conteggio_dice_quanti_template_su_quanti():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("unused-javascript")]),
        _pagina("Cat", "https://x.it/c", [_problema("cache-insight")]),
        _pagina("Prod", "https://x.it/p", [_problema("cache-insight")]),
    ))
    per_codice = {r["problema"].split(" su ")[0]: r["problema"]
                  for r in frammento["masterplan"]}
    assert "su 1 template su 3" in per_codice["JavaScript inutilizzato"]
    assert "su 2 template su 3" in per_codice["Cache del browser breve"]


def test_gli_id_seguono_l_ordine_di_priorita():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("unused-javascript", gravita="bassa"),
            _problema("cache-insight", gravita="alta"),
            _problema("bootup-time", gravita="media")]),
    ))
    righe = frammento["masterplan"]
    assert [r["id"] for r in righe] == [1, 2, 3]
    assert [r["priorita"] for r in righe] == ["Alta", "Media", "Bassa"]


def test_il_peso_di_traffico_conta_nell_ordine():
    """Stessa gravita', ma un problema tocca il template principale e l'altro no."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight", peso=1.0)]),
        _pagina("Marg", "https://x.it/m", [_problema("bootup-time", peso=0.02)]),
    ))
    assert frammento["masterplan"][0]["problema"].startswith("Cache")


def test_la_priorita_usa_la_stessa_scala_con_la_maiuscola():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight", gravita="alta")])))
    assert frammento["masterplan"][0]["priorita"] == "Alta"


# --- esclusioni -------------------------------------------------------------- #

def test_le_righe_non_azionabili_restano_fuori():
    frammento, esclusi = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("cache-insight", azionabile=False),
            _problema("unused-javascript")])))
    assert len(frammento["masterplan"]) == 1
    assert len(esclusi) == 1 and "non azionabile" in esclusi[0][2]


def test_gli_artefatti_di_dati_restano_fuori():
    """script-treemap-data non porta una raccomandazione: il titolo tecnico non
    e' un intervento."""
    frammento, esclusi = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("script-treemap-data", azioni=())])))
    assert frammento["masterplan"] == []
    assert "artefatto di dati" in esclusi[0][2]


def test_le_constatazioni_restano_fuori():
    frammento, esclusi = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("peso-terze-parti", fonte="classificazione", azioni=())])))
    assert frammento["masterplan"] == []
    assert "constatazione" in esclusi[0][2]


def test_un_audit_con_bersagli_inline_non_finisce_fra_i_silenzi():
    """Non deve sparire ne' dal master plan ne' dall'elenco degli esclusi: il
    tool dichiara cio' che lascia fuori."""
    frammento, esclusi = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema(
            "unminified-css", titolo="Minimizza CSS",
            risorse=(("CSS inline: .a { color: red }", "2 KB", False),))])))
    righe = frammento["masterplan"]
    assert len(righe) == 1 and righe[0]["intervento"] == "Minimizza CSS"
    assert esclusi == []


def test_le_pagine_fallite_non_entrano_nel_conteggio():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")]),
        {"template": "Rotta", "url": "https://x.it/r", "errore": "PSI 502"}))
    assert "su 1 template su 1" in frammento["masterplan"][0]["problema"]


# --- registro delle celle ---------------------------------------------------- #

def test_l_intervento_e_il_titolo_di_lighthouse_verbatim():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("unused-javascript", titolo="Riduci il codice JavaScript inutilizzato")])))
    assert frammento["masterplan"][0]["intervento"] == "Riduci il codice JavaScript inutilizzato"


def test_dove_il_titolo_e_un_sostantivo_si_usa_l_imperativo_del_link():
    """"Terze parti" non e' un intervento; l'etichetta del link di Lighthouse si'."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("third-parties-insight", titolo="Terze parti",
                      azione_breve="Riduci e posticipa il caricamento del codice di terze parti")])))
    assert frammento["masterplan"][0]["intervento"].startswith("Riduci e posticipa")


def test_gli_inviti_alla_documentazione_non_sono_interventi():
    """"Scopri come..." e' un rimando, non un'azione: meglio il titolo."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("cls-culprits-insight", titolo="Responsabili delle variazioni",
                      azione_breve="Scopri come evitare le variazioni")])))
    assert frammento["masterplan"][0]["intervento"] == "Responsabili delle variazioni"


def test_dove_lighthouse_non_ha_un_imperativo_l_intervento_lo_scriviamo_noi():
    """"Carattere visualizzato" e' il nome di `font-display` tradotto, non un'azione,
    e il primo link della descrizione rende il termine stesso: nessuna delle due
    strade di Lighthouse porta a un'istruzione."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("font-display-insight", titolo="Carattere visualizzato",
                      azione_breve="font-display"),
            _problema("legacy-javascript-insight", titolo="JavaScript precedente",
                      azione_breve="di base")])))
    interventi = {r["problema"].split(" su ")[0]: r["intervento"]
                  for r in frammento["masterplan"]}
    assert interventi["Font senza font-display"].startswith("Imposta font-display")
    assert interventi["JavaScript per browser vecchi"].startswith("Escludi polyfill")


def test_nessun_intervento_e_il_sostantivo_di_quei_due_audit():
    """Il sintomo: la colonna consegnata al cliente riceveva il titolo tradotto."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("font-display-insight", titolo="Carattere visualizzato",
                      azione_breve="font-display"),
            _problema("legacy-javascript-insight", titolo="JavaScript precedente",
                      azione_breve="di base")])))
    interventi = [r["intervento"] for r in frammento["masterplan"]]
    for sostantivo in ("Carattere visualizzato", "JavaScript precedente",
                       "font-display", "di base"):
        assert sostantivo not in interventi


def test_la_tabella_non_tocca_gli_audit_col_titolo_gia_imperativo():
    """AZIONE_PER_AUDIT e' un'eccezione enumerata: dove Lighthouse ha gia'
    un'istruzione, il suo testo resta."""
    codici = ("unused-javascript", "bootup-time", "cache-insight",
              "image-delivery-insight", "third-parties-insight")
    assert not [c for c in codici if c in masterplan.AZIONE_PER_AUDIT]

    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("unused-javascript",
                      titolo="Riduci il codice JavaScript inutilizzato")])))
    assert frammento["masterplan"][0]["intervento"] ==         "Riduci il codice JavaScript inutilizzato"


def test_la_riga_dichiara_chi_ha_scritto_l_intervento():
    """ADR-004: l'origine del testo si dichiara, non si deduce."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("font-display-insight", titolo="Carattere visualizzato"),
            _problema("unused-javascript", titolo="Riduci il codice inutilizzato")])))
    fonti = {r["intervento"]: r["fonte_intervento"] for r in frammento["masterplan"]}
    assert fonti["Riduci il codice inutilizzato"] == "lighthouse"
    assert fonti[masterplan.AZIONE_PER_AUDIT["font-display-insight"]] == "nostra"


def test_ogni_voce_della_tabella_e_un_imperativo_non_un_sostantivo():
    """Il difetto che la tabella corregge non deve rientrare dalla tabella stessa."""
    for codice, azione in masterplan.AZIONE_PER_AUDIT.items():
        assert len(azione.split()) >= 4, f"{codice}: troppo corto per essere un'azione"
        assert azione[0].isupper(), f"{codice}: un'istruzione comincia con un verbo"


def test_per_le_classificazioni_nostre_l_intervento_e_la_checklist_lighthouse():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("lcp-resourceLoadDelay", fonte="campo",
                      azioni=("Deve essere applicata fetchpriority=high",))])))
    assert frammento["masterplan"][0]["intervento"] == "Deve essere applicata fetchpriority=high"


def test_l_evidenza_porta_il_p75_di_campo():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/",
                [_problema("cache-insight", metrica="largest_contentful_paint",
                           evidenza=("Risparmio stimato di 498 KiB",))],
                metriche={"largest_contentful_paint": 4180.0})))
    evidenza = frammento["masterplan"][0]["evidenza"]
    assert "LCP p75 4.180 ms" in evidenza
    assert "Risparmio stimato di 498 KiB" in evidenza


def test_l_evidenza_scarta_le_nostre_parafrasi():
    """La quota di terze parti e la stima servono a priorita' e responsabile, non
    descrivono il problema: in una cella di audit sono rumore."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/",
                [_problema("cache-insight", metrica="largest_contentful_paint",
                           evidenza=("Stima Lighthouse: LCP 300 ms",
                                     "96% dello spreco e' su risorse di terze parti"))],
                metriche={"largest_contentful_paint": 4180.0})))
    evidenza = frammento["masterplan"][0]["evidenza"]
    assert "Stima Lighthouse" not in evidenza and "dello spreco" not in evidenza


def test_nessuna_cella_contiene_una_data_o_il_metodo():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("cache-insight", metrica="largest_contentful_paint",
                      evidenza=("Risparmio stimato di 498 KiB",))],
            metriche={"largest_contentful_paint": 4180.0})))
    for riga in frammento["masterplan"]:
        testo = " ".join(str(v) for v in riga.values()).lower()
        for vietato in ("verificato", "rilevazione", "2026-", "/2026"):
            assert vietato not in testo


# --- tab ---------------------------------------------------------------------- #

def test_un_tab_di_metrica_solo_se_qualcuno_e_oltre_soglia():
    sana = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")],
                metriche={"largest_contentful_paint": 1100.0})))[0]
    assert not [t for t in sana["tab"] if t["nome"].startswith("URL - LCP")]

    rotta = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")],
                metriche={"largest_contentful_paint": 4500.0})))[0]
    assert [t for t in rotta["tab"] if t["nome"].startswith("URL - LCP")]


def test_il_tab_ha_intestazioni_e_larghezze():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")],
                metriche={"largest_contentful_paint": 4500.0})))
    tab = frammento["tab"][0]
    assert len(tab["intestazioni"]) == len(tab["larghezze"]) == len(tab["righe"][0])


def test_il_riferimento_al_tab_esiste_davvero():
    """Una riga non deve puntare a un tab che non e' stato creato."""
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [
            _problema("unused-javascript", risorse=(("https://x.it/a.js", "50 KB", True),))])))
    nomi = {t["nome"] for t in frammento["tab"]}
    for riga in frammento["masterplan"]:
        assert riga["tab"] == "" or riga["tab"] in nomi


def test_il_numero_di_tab_e_limitato():
    problemi = [_problema(f"audit-{i}", risorse=((f"https://x.it/{i}.js", "1 KB", False),))
                for i in range(12)]
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", problemi)))
    assert len(frammento["tab"]) <= masterplan.MASSIMO_TAB


# --- forma del frammento ------------------------------------------------------ #

def test_forma_del_frammento():
    frammento, _ = masterplan.costruisci(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")])))
    assert set(frammento) == {"masterplan", "tab"}
    riga = frammento["masterplan"][0]
    assert set(riga) == {"id", "problema", "priorita", "evidenza", "intervento",
                         "fonte_intervento", "tab"}
    assert isinstance(riga["id"], int)
    assert json.dumps(frammento, ensure_ascii=False), "dev'essere serializzabile"


def test_funziona_su_un_run_reale(tmp_path):
    """Il comando deve girare su un JSON salvato mesi prima: si parte dalla forma
    JSON, non dagli oggetti in memoria."""
    salvato = json.loads(json.dumps(_esecuzione(
        _pagina("Home", "https://x.it/", [_problema("cache-insight")]))))
    frammento, _ = masterplan.costruisci(salvato)
    assert frammento["masterplan"]
