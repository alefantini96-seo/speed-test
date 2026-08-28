"""
Test delle tre classificazioni, contro una risposta PSI reale con locale=it.

Il principio da difendere: il tool non inventa raccomandazioni. Il testo viene da
Lighthouse, i numeri dalla misurazione, e le uniche cose che aggiungiamo sono
chi interviene, quanto e' prioritario e se e' azionabile — tutte e tre derivate
da dati, non da opinioni.
"""
import json
from pathlib import Path

import pytest

from speed.core import diagnose, extract, thirdparty

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
URL = "https://www.bbc.com/"
PROPRI = ["bbci.co.uk"]

# Il campo reale di quella pagina: tutte le metriche entro soglia.
CAMPO_BUONO = {
    "largest_contentful_paint": 1162.0,
    "interaction_to_next_paint": 109.0,
    "cumulative_layout_shift": 0.03,
    "first_contentful_paint": 685.0,
    "experimental_time_to_first_byte": 342.0,
}


@pytest.fixture(scope="module")
def psi():
    return json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fatti(psi):
    return extract.estrai(psi, URL, "PHONE", PROPRI)


@pytest.fixture(scope="module")
def problemi(fatti):
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    return diagnose.diagnostica(fatti, CAMPO_BUONO, riepilogo)


def _per_codice(problemi, frammento):
    trovati = [p for p in problemi if frammento in p.codice]
    assert trovati, f"nessun problema con codice contenente {frammento!r}"
    return trovati[0]


# --- il testo non lo scriviamo noi ----------------------------------------- #

def test_il_titolo_e_quello_di_lighthouse(psi, problemi):
    audits = psi["lighthouseResult"]["audits"]
    for problema in problemi:
        if problema.fonte != "lighthouse":
            continue
        assert problema.titolo.replace(" [misurazioni discordanti]", "") \
            == audits[problema.codice]["title"], "titolo di Lighthouse, verbatim"


def test_le_azioni_sono_la_descrizione_di_lighthouse(problemi):
    p = _per_codice(problemi, "unused-javascript")
    assert p.azioni and len(p.azioni[0]) > 40
    assert p.documentazione.startswith("https://"), "il link alla documentazione va conservato"
    assert p.fonte == "lighthouse"


def test_le_risorse_colpevoli_sono_nel_problema(problemi):
    p = _per_codice(problemi, "unused-javascript")
    assert len(p.risorse) >= 3
    for url, misura, _terza in p.risorse:
        assert url.startswith("http") and misura


def test_la_checklist_lcp_e_riportata_testuale(problemi, fatti):
    p = _per_codice(problemi, "lcp-")
    assert p.fonte == "classificazione", "la fase la classifichiamo noi, il rimedio no"
    fallite = [k for k, v in fatti.lcp_discovery.items() if v is False]
    assert len(p.azioni) == len(fallite), "una voce per ogni controllo fallito, niente di piu'"


def test_nessuna_azione_scritta_a_mano(problemi):
    """Le vecchie stringhe inventate non devono ricomparire."""
    testo = " ".join(a for p in problemi for a in p.azioni).lower()
    for inventata in ("inventario dei tag", "valutare una facade", "digital pr"):
        assert inventata not in testo


# --- chi interviene, dedotto dalle risorse ---------------------------------- #

def test_responsabile_dipende_da_chi_possiede_le_risorse(psi):
    """Lo stesso audit cambia responsabile a seconda di `domini_propri`."""
    senza = extract.estrai(psi, URL, "PHONE", [])
    con = extract.estrai(psi, URL, "PHONE", PROPRI)
    op_senza = [o for o in senza.opportunita if o.audit == "unused-javascript"][0]
    op_con = [o for o in con.opportunita if o.audit == "unused-javascript"][0]
    assert diagnose.responsabile_per(op_senza) == diagnose.MARKETING
    assert diagnose.responsabile_per(op_con) != diagnose.MARKETING


def test_audit_di_cache_va_sempre_a_infrastruttura(problemi):
    assert _per_codice(problemi, "cache").responsabile == diagnose.INFRA


def test_responsabile_non_e_un_default(problemi):
    responsabili = {p.responsabile for p in problemi}
    assert len(responsabili) > 1, "se hanno tutti lo stesso responsabile non stiamo classificando"


# --- priorita' dal campo, non dal laboratorio ------------------------------- #

def test_campo_sano_azzera_le_priorita(problemi):
    """Su questa pagina il campo e' entro soglia ovunque: Lighthouse stima
    comunque 1350 ms di risparmio sull'LCP, ma per gli utenti non c'e' problema."""
    assert all(p.gravita == "bassa" for p in problemi)
    assert "gia' a posto" in _per_codice(problemi, "unused-javascript").nota


def test_campo_degradato_alza_la_priorita(fatti):
    campo = dict(CAMPO_BUONO, largest_contentful_paint=6000.0)
    problemi = diagnose.diagnostica(fatti, campo)
    assert _per_codice(problemi, "unused-javascript").gravita == "alta"


def test_senza_campo_la_priorita_e_dichiarata_non_calibrata(fatti):
    problemi = diagnose.diagnostica(fatti, {})
    p = _per_codice(problemi, "unused-javascript")
    assert p.gravita == "media" and "non calibrata sul campo" in p.nota


def test_il_proxy_tbt_inp_e_dichiarato(fatti):
    campo = dict(CAMPO_BUONO, interaction_to_next_paint=600.0)
    problemi = diagnose.diagnostica(fatti, campo)
    tbt = [p for p in problemi if "TBT" in " ".join(p.evidenza)]
    assert tbt and any("proxy di laboratorio dell'INP" in p.nota for p in tbt)


def test_ordinamento_per_gravita(fatti):
    campo = dict(CAMPO_BUONO, largest_contentful_paint=6000.0)
    problemi = diagnose.diagnostica(fatti, campo)
    ordine = {"alta": 0, "media": 1, "bassa": 2}
    livelli = [ordine[p.gravita] for p in problemi]
    assert livelli == sorted(livelli)


# --- la ripartizione LCP viene dal campo quando c'e' ------------------------ #

# Le quattro fasi come CrUX le espone: sono la ripartizione sugli utenti reali.
CAMPO_CON_FASI = dict(CAMPO_BUONO, **{
    "largest_contentful_paint_image_time_to_first_byte": 339.0,
    "largest_contentful_paint_image_resource_load_delay": 498.0,
    "largest_contentful_paint_image_resource_load_duration": 176.0,
    "largest_contentful_paint_image_element_render_delay": 257.0,
})


def test_le_fasi_vengono_dal_campo_quando_disponibili(fatti):
    p = diagnose.classifica_lcp(fatti, CAMPO_CON_FASI)
    assert p.fonte == "campo"
    assert "utenti reali" in p.evidenza[0]
    assert "dai dati di campo CrUX" in p.nota
    assert p.codice == "lcp-resourceLoadDelay", "il campo dice attesa pre-download"


def test_senza_fasi_di_campo_si_ricade_sul_laboratorio(fatti):
    p = diagnose.classifica_lcp(fatti, CAMPO_BUONO)
    assert p.fonte == "classificazione"
    assert "laboratorio" in p.evidenza[0]
    assert "CrUX non espone le fasi" in p.nota


def test_campo_e_laboratorio_possono_dare_diagnosi_diverse(fatti):
    """Caso reale: il campo indica l'attesa pre-download, il lab il rendering.
    E' la ragione per cui il campo ha la precedenza."""
    dal_campo = diagnose.classifica_lcp(fatti, CAMPO_CON_FASI)
    dal_lab = diagnose.classifica_lcp(fatti, CAMPO_BUONO)
    assert dal_campo.codice != dal_lab.codice


def test_una_ripartizione_parziale_non_viene_usata(fatti):
    """Tre fasi su quattro darebbero una dominante falsata da cio' che manca."""
    parziale = dict(CAMPO_CON_FASI)
    del parziale["largest_contentful_paint_image_element_render_delay"]
    assert diagnose.classifica_lcp(fatti, parziale).fonte == "classificazione"


def test_dal_campo_il_consenso_non_serve_piu(fatti):
    """Con le fasi di campo la discordanza fra misurazioni lab e' irrilevante."""
    class AccordoFinto:
        attendibile = False
        checklist_stabile = True
        descrizione = "discordanti"
    p = diagnose.classifica_lcp(fatti, CAMPO_CON_FASI, AccordoFinto())
    assert "discordanti" not in p.titolo
    assert "da confermare" not in p.responsabile


# --- azionabilita' ---------------------------------------------------------- #

def test_intervento_su_server_altrui_non_e_azionabile(fatti):
    finta = extract.Opportunita(
        audit="cache-insight", titolo="Cache", descrizione="", documentazione="",
        display="", score=0, risparmi={"LCP": 500.0},
        risorse=[extract.Risorsa(url="https://terzo.example/a.js", byte_sprecati=1000,
                                 terza_parte=True)])
    assert diagnose.azionabile(finta) is False
    p = diagnose.da_opportunita(finta, CAMPO_BUONO)
    assert "non e' nelle vostre mani" in p.nota


def test_intervento_sul_proprio_sito_resta_azionabile(problemi):
    assert _per_codice(problemi, "unused-javascript").azionabile is True


# --- la constatazione sulle terze parti non contiene rimedi ------------------ #

def test_terze_parti_e_constatazione_non_intervento(fatti):
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, [])   # senza dichiarazione: sopra soglia
    p = diagnose.constatazione_terze_parti(riepilogo)
    assert p is not None
    assert p.azioni == [], "qui non si raccomanda niente: e' solo il dato"
    assert p.risorse and "non un intervento" in p.nota


# --- bersagli inline: si dichiarano, non si scartano ------------------------- #

def test_l_audit_con_bersagli_inline_arriva_nel_report(problemi):
    """Sul fixture `unminified-css` fallisce (score 0,5) e dichiara 2 KiB di
    risparmio: prima non compariva ne' fra i problemi ne' fra gli esclusi."""
    problema = _per_codice(problemi, "unminified-css")
    assert problema.titolo == "Minimizza CSS", "il titolo resta quello di Lighthouse"
    assert problema.risorse, "il blocco inline e' un bersaglio"


def test_l_etichetta_inline_e_dichiarata_nella_nota(problemi):
    """ADR-004: l'etichetta e' nostra, e il report lo dice."""
    problema = _per_codice(problemi, "unminified-css")
    assert "codice inline" in problema.nota
    assert "e' nostra" in problema.nota


def test_il_codice_inline_non_manda_l_intervento_a_marketing(problemi):
    """Un blocco nel documento e' prima parte: dedurne la proprieta' dal dominio
    dava netloc vuoto, quindi terza parte, quindi il lavoro alla squadra sbagliata."""
    assert _per_codice(problemi, "unminified-css").responsabile == diagnose.DEV


def test_il_segnaposto_non_arriva_ai_bersagli(fatti):
    """Su forced-reflow-insight Lighthouse non attribuisce la riga a nessuno:
    il tempo resta, il bersaglio no."""
    reflow = next(o for o in fatti.opportunita if o.audit == "forced-reflow-insight")
    assert any("[senza attributi]" in str(v.etichetta) for v in reflow.voci), \
        "il caso ha senso solo se il segnaposto e' nei dati"
    problema = diagnose.da_opportunita(reflow, {})
    assert problema.bersagli == []
    assert problema.ms_sprecati > 0, "la misura non si perde con il segnaposto"


def test_un_bersaglio_scartato_lascia_posto_al_successivo():
    """Scartare non deve accorciare la lista: se ci sono altri bersagli veri,
    devono salire al posto del segnaposto."""
    class Finta:
        etichetta = "[senza attributi]"
        misure = {"wastedMs": 10.0}

    class Vera:
        etichetta = "davvero.js"
        misure = {"wastedMs": 5.0}

    class Opportunita:
        audit = "forced-reflow-insight"
        elementi = []
        risorse = []
        voci = [Finta(), Finta(), Vera()]

    bersagli = diagnose.bersagli_di(Opportunita(), massimo=2)
    assert [b[0] for b in bersagli] == ["davvero.js"]


# --- la quota di una fase LCP porta il tempo che vale ------------------------- #

def test_la_quota_di_una_fase_porta_il_valore_assoluto():
    """Il sintomo: "39% del tempo LCP" e basta. Il 39% di 8,1 s e il 39% di
    12,3 s sono due problemi diversi, e l'LCP sta in un'altra tabella."""
    fasi = {"timeToFirstByte": 100.0, "resourceLoadDelay": 900.0}
    assert diagnose.quota_lcp(fasi, "resourceLoadDelay") == "90% (900 ms)"


def test_sopra_il_secondo_la_quota_si_legge_in_secondi():
    fasi = {"timeToFirstByte": 1000.0, "elementRenderDelay": 3000.0}
    assert diagnose.quota_lcp(fasi, "elementRenderDelay") == "75% (3,0 s)"


def test_il_bersaglio_dell_lcp_non_e_piu_una_percentuale_nuda(fatti):
    problema = diagnose.classifica_lcp(fatti, {})
    assert problema is not None
    _nome, misura, _dettaglio = problema.bersagli[0]
    assert "del tempo LCP" in misura
    assert "(" in misura and ("ms)" in misura or "s)" in misura), misura


def test_anche_la_fase_dominante_dichiara_il_tempo(fatti):
    """La stessa riga finisce nel report al cliente attraverso il master plan:
    li' la percentuale nuda aveva lo stesso difetto."""
    problema = diagnose.classifica_lcp(fatti, {})
    riga = next(e for e in problema.evidenza if e.startswith("Fase dominante"))
    assert "% (" in riga, riga

