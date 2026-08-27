"""
Test dell'estrazione contro risposte PSI reali.

I fixture sono risposte vere di PageSpeed Insights (Lighthouse 13.4.1) su un sito
pubblico. Quando Lighthouse cambia le chiavi degli audit sono questi test a
rompersi: e' il segnale che extract.py va riallineato, ed e' voluto.

Testano la funzione vera, importata. Nessuna logica riscritta nel test.
"""
import json
from pathlib import Path

import pytest

from speed.core import extract, thirdparty

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
URL = "https://www.bbc.com/"
# bbc.com serve gli asset da bbci.co.uk: dominio diverso, stessa organizzazione.
PROPRI = ["bbci.co.uk"]


@pytest.fixture(scope="module")
def psi():
    return json.loads((FIXTURES / "psi-bbc-mobile-it.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fatti(psi):
    return extract.estrai(psi, URL, "PHONE", PROPRI)


def test_metadati_lab(fatti):
    assert fatti.lighthouse_version.startswith("13.")
    assert fatti.benchmark_index > 0, "benchmarkIndex serve a scartare run su macchine lente"
    assert fatti.timestamp, "analysisUTCTimestamp identifica la misurazione: serve a deduplicare"


def test_fasi_lcp_complete(fatti):
    assert set(fatti.lcp_fasi) == set(extract.FASI_LCP)
    assert all(v >= 0 for v in fatti.lcp_fasi.values())


def test_fase_dominante_e_una_proporzione(fatti):
    fase, quota = fatti.lcp_fase_dominante
    assert fase in extract.FASI_LCP
    assert 0 < quota <= 1


def test_elemento_lcp_e_una_immagine(fatti):
    assert fatti.lcp_elemento_snippet.startswith("<img")


def test_checklist_discovery(fatti):
    # Caso reale: l'immagine e' nell'HTML ma senza priorita' dichiarata.
    assert fatti.lcp_discovery["requestDiscoverable"] is True
    assert fatti.lcp_discovery["priorityHinted"] is False
    assert set(fatti.lcp_discovery_label) == set(fatti.lcp_discovery)


def test_richieste_e_peso(fatti):
    assert len(fatti.richieste) > 50
    assert sum(r.byte for r in fatti.richieste) > 1_000_000


def test_le_richieste_portano_l_entita_di_lighthouse(fatti):
    con_entita = [r for r in fatti.richieste if r.entita]
    assert con_entita, "network-requests espone il campo entity: va conservato"


# --- opportunita': il testo viene da Lighthouse ----------------------------- #

def test_opportunita_presenti_e_ordinate(fatti):
    """L'ordinamento e' sul risparmio NORMALIZZATO, non su quello grezzo.

    Prima questo test verificava l'ordine per `risparmio_massimo`. Confrontare i
    valori grezzi mette pero' 0,095 di CLS sempre dietro a 600 ms di TBT per pura
    questione di scala, cioe' spinge in fondo ogni intervento sul layout. Ora si
    normalizza sulla soglia di ciascuna metrica.
    """
    assert len(fatti.opportunita) >= 5
    pesi = [o.peso_relativo for o in fatti.opportunita]
    assert pesi == sorted(pesi, reverse=True)


def test_ogni_opportunita_ha_titolo_e_contenuto(fatti):
    """Prima si pretendeva che ogni opportunita' avesse dei `metricSavings`.

    Non e' piu' vero, ed e' il punto della modifica: `cls-culprits-insight` non
    dichiara risparmi ma nomina gli elementi che fanno ballare la pagina. Cio' che
    va preteso e' che ogni voce del report NOMINI qualcosa su cui intervenire.
    """
    for o in fatti.opportunita:
        assert o.titolo, o.audit
        assert o.ha_contenuto or o.risparmi, f"{o.audit} non nomina nulla"
        assert all(v > 0 for v in o.risparmi.values())


def test_le_opportunita_nominano_le_risorse(fatti):
    unused = [o for o in fatti.opportunita if o.audit == "unused-javascript"][0]
    assert len(unused.risorse) >= 3
    assert all(r.url.startswith("http") for r in unused.risorse)
    assert any(r.byte_sprecati > 0 for r in unused.risorse)


def test_descrizione_in_italiano_e_link_conservato(fatti):
    unused = [o for o in fatti.opportunita if o.audit == "unused-javascript"][0]
    assert "JavaScript" in unused.titolo or "javascript" in unused.titolo.lower()
    assert unused.documentazione.startswith("https://")
    assert "](" not in unused.descrizione, "il markdown del link va risolto, non lasciato grezzo"


def test_campo_psi_e_a_livello_url(fatti):
    assert fatti.campo_psi_origin_fallback is False
    assert "LARGEST_CONTENTFUL_PAINT_MS" in fatti.campo_psi


# --- attribuzione first / third party --------------------------------------- #

def test_dominio_fratello_senza_dichiarazione_risulta_terza_parte(psi):
    """Senza `domini_propri`, il CDN del cliente viene scambiato per terza parte."""
    fatti = extract.estrai(psi, URL, "PHONE", [])
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, [])
    assert riepilogo.quota_terzi > 0.9


def test_dichiarare_il_dominio_proprio_ribalta_l_attribuzione(psi):
    fatti = extract.estrai(psi, URL, "PHONE", PROPRI)
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    assert riepilogo.quota_terzi < 0.4
    propri = [e for e in riepilogo.entita if not e.terza_parte]
    assert any("bbci" in e.nome for e in propri)


def test_le_entita_raggruppano_piu_host(fatti):
    riepilogo = thirdparty.riepiloga(fatti.richieste, URL, PROPRI)
    multi = [e for e in riepilogo.entita if len(e.host) > 1]
    assert multi, "Lighthouse unisce piu' host sotto un provider: va sfruttato"


def test_peso_per_tipo(fatti):
    per_tipo = thirdparty.peso_per_tipo(fatti.richieste)
    assert per_tipo and list(per_tipo.values()) == sorted(per_tipo.values(), reverse=True)


# --- bersagli inline: Lighthouse non li nomina con un URL -------------------- #

def test_un_audit_con_bersagli_inline_non_sparisce(fatti):
    """Il sintomo: `unminified-css` sul fixture ha score 0,5 e "Risparmio stimato
    di 2 KiB", e non compariva da nessuna parte. La cella `url` porta l'estratto
    del blocco `<style>`, non un indirizzo: la riga non produceva niente,
    `ha_contenuto` era falso e l'audit veniva scartato in silenzio."""
    audit = {o.audit: o for o in fatti.opportunita}
    assert "unminified-css" in audit
    opportunita = audit["unminified-css"]
    assert opportunita.risorse, "il blocco inline e' un bersaglio, non niente"
    assert opportunita.risorse[0].etichetta == "CSS inline"
    assert opportunita.risorse[0].byte_sprecati > 0


def test_il_bersaglio_inline_porta_l_estratto_di_lighthouse(fatti):
    """L'etichetta e' nostra, l'estratto no: senza, il blocco resta da cercare."""
    inline = next(o for o in fatti.opportunita if o.audit == "unminified-css").risorse[0]
    assert inline.nome == "CSS inline"
    assert inline.riferimento.startswith("CSS inline: ")
    assert ".hygVWX" in inline.riferimento, "l'estratto e' testo di Lighthouse"


def test_il_codice_inline_e_prima_parte_per_costruzione(psi):
    """Sta nel documento: la proprieta' non si deduce dal dominio. Dedurla dava
    netloc vuoto, quindi terza parte, quindi l'intervento a marketing/tag."""
    fatti = extract.estrai(psi, URL, "PHONE", ["bbci.co.uk"])
    inline = next(o for o in fatti.opportunita if o.audit == "unminified-css").risorse[0]
    assert inline.terza_parte is False


def test_l_etichetta_inline_non_si_applica_a_ogni_riga_senza_url(fatti):
    """Su `bootup-time` la stessa cella porta "Unattributable": e' lavoro non
    attribuito, non un blocco inline, e chiamarlo "script inline" sarebbe
    un'informazione inventata."""
    bootup = next(o for o in fatti.opportunita if o.audit == "bootup-time")
    assert not [r for r in bootup.risorse if r.etichetta]
    assert "Unattributable" not in [r.url for r in bootup.risorse]


def test_le_risorse_con_un_file_non_cambiano_forma(fatti):
    """L'etichetta resta vuota dove un URL c'e': `riferimento` e' l'URL, come prima."""
    unused = next(o for o in fatti.opportunita if o.audit == "unused-javascript")
    for risorsa in unused.risorse:
        assert risorsa.etichetta == ""
        assert risorsa.riferimento == risorsa.url
