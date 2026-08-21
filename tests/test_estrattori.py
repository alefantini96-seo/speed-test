"""
Test dei lettori per forma di `details` e del criterio di ammissione.

Lighthouse 13 incapsula le stesse informazioni in quattro modi diversi. Leggerne
uno solo faceva perdere il materiale piu' concreto della risposta: gli elementi
che shiftano nel CLS, il costo di main thread per vendor, l'origine di un reflow.

Le forme usate qui sono ritagli della fixture reale, non inventate: dove serve un
caso che la fixture non contiene, il test lo dichiara.
"""
import json
from pathlib import Path

import pytest

from speed.core import diagnose, extract
from speed.core.soglie import UNITA_METRICA, formatta_risparmio

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
URL = "https://www.bbc.com/"


@pytest.fixture(scope="module")
def audits():
    dati = json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(encoding="utf-8"))
    return dati["lighthouseResult"]["audits"]


@pytest.fixture(scope="module")
def opportunita(audits):
    psi = json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(encoding="utf-8"))
    return {o.audit: o for o in extract.estrai_opportunita(psi, URL, [])}


# --- lettori per forma ------------------------------------------------------ #

def test_tabelle_dentro_una_list(audits):
    """`cls-culprits-insight` mette due tabelle dentro details.type == "list"."""
    tabelle = list(extract._tabelle(audits["cls-culprits-insight"]))
    assert len(tabelle) == 2
    assert all(isinstance(t, list) and t for t in tabelle)


def test_tabelle_quando_details_e_gia_una_table(audits):
    """`image-delivery-insight` ha details.type == "table": le righe stanno li'."""
    tabelle = list(extract._tabelle(audits["image-delivery-insight"]))
    assert sum(len(t) for t in tabelle) == 8


def test_tabelle_dentro_una_list_section(audits):
    """`network-dependency-tree-insight` annida la tabella in list-section.value."""
    tabelle = list(extract._tabelle(audits["network-dependency-tree-insight"]))
    assert any(t for t in tabelle), "la tabella dentro list-section va raggiunta"


def test_sotto_righe_legge_subitems_come_dict(audits):
    """`subItems` e' un dict con dentro `items`, non una lista: e' li' che
    third-parties-insight tiene il dettaglio per singolo file."""
    prima = audits["third-parties-insight"]["details"]["items"][0]
    sotto = extract._sotto_righe(prima)
    assert sotto and "url" in sotto[0] and "mainThreadTime" in sotto[0]


def test_sotto_righe_tollera_l_assenza():
    assert extract._sotto_righe({}) == []
    assert extract._sotto_righe({"subItems": []}) == []


# --- nodi ------------------------------------------------------------------- #

def test_leggi_nodo_estrae_i_campi_separati(audits):
    riga = audits["image-delivery-insight"]["details"]["items"][0]
    elemento = extract.leggi_nodo(riga["node"])
    assert elemento is not None
    assert elemento.selettore and elemento.percorso.startswith("1,HTML")
    assert elemento.snippet.startswith("<img")
    assert elemento.etichetta


def test_leggi_nodo_scarta_le_righe_di_totale(audits):
    """Le tabelle del CLS aprono con {type: text, value: "Totale"}: e' un
    riepilogo, e finirebbe nel report come se fosse un selettore."""
    prima_riga = audits["cls-culprits-insight"]["details"]["items"][0]["items"][0]
    assert prima_riga["node"]["value"] == "Totale"
    assert extract.leggi_nodo(prima_riga["node"]) is None


def test_leggi_nodo_ignora_cio_che_non_e_un_nodo():
    assert extract.leggi_nodo(None) is None
    assert extract.leggi_nodo("stringa") is None
    assert extract.leggi_nodo({"type": "node"}) is None, "senza selettore non e' utile"


def test_riferimento_ripiega_in_ordine():
    assert extract.Elemento(selettore="div.a").riferimento == "div.a"
    assert extract.Elemento(etichetta="Titolo").riferimento == "Titolo"
    assert extract.Elemento(percorso="1,HTML").riferimento == "1,HTML"


# --- checklist generalizzata ------------------------------------------------ #

def test_leggi_checklist_generalizzata(audits):
    controlli = extract.leggi_checklist(audits["lcp-discovery-insight"])
    assert set(controlli) == {"priorityHinted", "requestDiscoverable", "eagerlyLoaded"}
    superato, etichetta = controlli["requestDiscoverable"]
    assert superato is True and etichetta


def test_leggi_checklist_su_audit_senza_checklist(audits):
    assert extract.leggi_checklist(audits["unused-javascript"]) == {}


# --- treemap ---------------------------------------------------------------- #

def test_leggi_treemap(audits):
    risorse = extract.leggi_treemap(audits["script-treemap-data"])
    assert len(risorse) == 83, "un nodo radice per file sorgente"
    assert all(r.url for r in risorse)
    assert any(r.byte_sprecati > 0 for r in risorse), "unusedBytes va conservato"
    assert any(r.byte_totali > 0 for r in risorse), "resourceBytes va conservato"


# --- catena critica di rete ------------------------------------------------- #

def test_leggi_catena_rete(audits):
    """La catena non e' una tabella ma un albero di nodi indicizzati per hash:
    nessun lettore per tabella la raggiunge, ed e' il motivo per cui l'audit
    risultava senza contenuto pur essendo fallito."""
    voci = extract.leggi_catena_rete(audits["network-dependency-tree-insight"])
    assert len(voci) > 1
    assert all("navStartToEndTime" in v.misure for v in voci)
    assert voci[0].etichetta.startswith("http"), "la radice e' il documento"
    assert any(v.etichetta.startswith(" ") for v in voci[1:]),         "l'indentazione conserva la profondita': l'ordine e' l'informazione"


def test_la_catena_critica_entra_nel_report(opportunita):
    assert "network-dependency-tree-insight" in opportunita
    assert opportunita["network-dependency-tree-insight"].voci


# --- criterio di ammissione ------------------------------------------------- #

def test_audit_superato_non_entra():
    """layout-shifts e long-tasks hanno score 1 con savings > 0: erano ammessi dal
    criterio precedente, che guardava solo il risparmio."""
    assert extract.ammesso("layout-shifts", 1, {"CLS": 0.095}, True) is False
    assert extract.ammesso("long-tasks", 1, {"TBT": 600}, True) is False


def test_audit_fallito_entra_anche_senza_risparmio():
    assert extract.ammesso("forced-reflow-insight", 0, {}, True) is True


def test_insight_informativo_entra_se_ha_contenuto():
    assert extract.ammesso("cls-culprits-insight", 1, {"CLS": 0}, True) is True
    assert extract.ammesso("cls-culprits-insight", 1, {"CLS": 0}, False) is False


def test_audit_metrica_non_entra():
    """`largest-contentful-paint` ha score 0 ma non nomina nulla: e' il valore di
    una metrica, e quello lo prendiamo dal campo."""
    assert extract.ammesso("largest-contentful-paint", 0, {}, False) is False


def test_audit_gia_consumato_non_entra():
    """La fase LCP e la checklist sono il materiale di classifica_lcp: ammetterli
    qui li farebbe comparire due volte."""
    assert extract.ammesso("lcp-breakdown-insight", 0, {}, True) is False
    assert extract.ammesso("lcp-discovery-insight", 0, {}, True) is False


def test_i_due_audit_superati_sono_spariti_dal_risultato(opportunita):
    assert "layout-shifts" not in opportunita
    assert "long-tasks" not in opportunita


def test_gli_audit_recuperati_ci_sono(opportunita):
    for atteso in ("cls-culprits-insight", "image-delivery-insight",
                   "third-parties-insight", "script-treemap-data",
                   "forced-reflow-insight"):
        assert atteso in opportunita, f"{atteso} deve entrare nel report"


# --- il materiale recuperato ------------------------------------------------ #

def test_il_cls_ora_nomina_gli_elementi(opportunita):
    elementi = opportunita["cls-culprits-insight"].elementi
    assert len(elementi) == 2
    peggiore = elementi[0]
    assert peggiore.selettore and peggiore.percorso
    assert peggiore.misura > 0 and peggiore.unita == "", "il CLS e' adimensionale"


def test_il_costo_di_main_thread_per_vendor(opportunita):
    voci = opportunita["third-parties-insight"].voci
    assert voci, "una voce per entita'"
    assert all("mainThreadTime" in v.misure for v in voci)
    assert any(v.misure["mainThreadTime"] > 100 for v in voci)


def test_le_immagini_portano_il_motivo_di_lighthouse(opportunita):
    risorse = opportunita["image-delivery-insight"].risorse
    assert len(risorse) == 8
    motivi = [r.motivo for r in risorse if r.motivo]
    assert motivi, "il testo del perche' e' scritto da Lighthouse: va conservato"
    assert "immagine" in motivi[0].lower()


def test_l_artefatto_treemap_non_porta_la_sua_nota_interna(opportunita):
    """`script-treemap-data` ha description "Used for treemap app": e' una nota
    interna non localizzata, che come azione nel report sarebbe incomprensibile."""
    assert opportunita["script-treemap-data"].descrizione == ""
    assert opportunita["script-treemap-data"].risorse


# --- unita' ----------------------------------------------------------------- #

def test_il_cls_non_si_misura_in_millisecondi():
    assert UNITA_METRICA["CLS"] == ""
    assert formatta_risparmio("CLS", 0.095) == "0.095"
    assert formatta_risparmio("LCP", 1350.0) == "1350 ms"


def test_metrica_sconosciuta_trattata_come_millisecondi():
    assert formatta_risparmio("BOH", 12.0) == "12 ms"


def test_nessuna_stringa_cls_in_millisecondi(opportunita):
    """Il report conteneva letteralmente "Stima Lighthouse: CLS 0 ms"."""
    campo = {"cumulative_layout_shift": 0.03, "largest_contentful_paint": 1162.0}
    for o in opportunita.values():
        problema = diagnose.da_opportunita(o, campo)
        testo = " ".join(problema.evidenza) + " " + problema.nota
        assert "CLS 0 ms" not in testo
        assert "CLS 0.0 ms" not in testo


# --- responsabile ----------------------------------------------------------- #

def test_responsabile_dichiarato_quando_non_deducibile():
    finta = extract.Opportunita(audit="audit-ignoto", titolo="x", descrizione="",
                                documentazione="", display="", score=0, risparmi={})
    assert diagnose.responsabile_per(finta) == diagnose.NON_DEDUCIBILE
    problema = diagnose.da_opportunita(finta, {})
    assert "non e' deducibile" in problema.nota


def test_le_immagini_vanno_alla_redazione_ovunque_siano_ospitate(opportunita):
    """Le immagini sono contenuto: la responsabilita' non dipende dall'hosting."""
    assert diagnose.responsabile_per(opportunita["image-delivery-insight"]) == diagnose.CMS


def test_gli_elementi_che_shiftano_vanno_allo_sviluppo(opportunita):
    assert diagnose.responsabile_per(opportunita["cls-culprits-insight"]) == diagnose.DEV


# --- priorita' senza risparmio dichiarato ----------------------------------- #

def test_priorita_dal_campo_anche_senza_risparmio(opportunita):
    """cls-culprits non dichiara risparmi: la priorita' segue il CLS reale."""
    scarso = diagnose.priorita_dal_campo(
        opportunita["cls-culprits-insight"], {"cumulative_layout_shift": 0.40})
    buono = diagnose.priorita_dal_campo(
        opportunita["cls-culprits-insight"], {"cumulative_layout_shift": 0.02})
    assert scarso[2] == "cumulative_layout_shift", "la metrica torna al chiamante"
    assert scarso[0] == "alta" and buono[0] == "bassa"
    assert "non dichiara un risparmio" in scarso[1]


def test_lo_speed_index_dichiara_di_essere_approssimato():
    finta = extract.Opportunita(audit="x", titolo="x", descrizione="", documentazione="",
                                display="", score=0, risparmi={"SI": 900.0})
    _gravita, nota, _metrica = diagnose.priorita_dal_campo(
        finta, {"largest_contentful_paint": 1162.0})
    assert "non ha un equivalente nel campo" in nota
