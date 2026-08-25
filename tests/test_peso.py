"""
Test del peso di traffico per template.

Senza peso, un template da 200.000 sessioni e uno da 400 producono lo stesso
ordine di intervento. Con il peso dichiarato, l'ordinamento diventa
gravita x peso — e senza, resta identico a com'era.
"""
import pytest

from speed.config import Config, Template, carica
from speed.core import diagnose
from speed.errori import ErroreSpeed


def _config(*template, **kwargs):
    return Config(cliente="X", sito="https://x.it", template=list(template), **kwargs)


def _problema(gravita, codice="x", azionabile=True, risparmio=0.0):
    return diagnose.Problema(codice=codice, titolo=codice, gravita=gravita,
                             responsabile="sviluppo", azionabile=azionabile,
                             risparmio=risparmio)


# --- lettura e validazione --------------------------------------------------- #

def test_pesi_normalizzati_sul_massimo():
    conf = _config(Template(nome="Home", url="https://x.it/", sessioni=82000),
                   Template(nome="Cat", url="https://x.it/c/", sessioni=41000),
                   Template(nome="Marg", url="https://x.it/m/", sessioni=400))
    pesi = conf.pesi()
    assert pesi["https://x.it/"] == 1.0
    assert pesi["https://x.it/c/"] == pytest.approx(0.5)
    assert pesi["https://x.it/m/"] == pytest.approx(400 / 82000)


def test_quota_traffico_equivale_a_sessioni():
    a = _config(Template(nome="A", url="https://x.it/a", quota_traffico=0.8),
                Template(nome="B", url="https://x.it/b", quota_traffico=0.2)).pesi()
    b = _config(Template(nome="A", url="https://x.it/a", sessioni=800),
                Template(nome="B", url="https://x.it/b", sessioni=200)).pesi()
    assert a == b, "conta il rapporto, non l'unita'"


def test_senza_traffico_tutti_pesano_uno():
    conf = _config(Template(nome="A", url="https://x.it/a"),
                   Template(nome="B", url="https://x.it/b"))
    assert set(conf.pesi().values()) == {1.0}
    assert conf.traffico_dichiarato is False


def test_un_template_senza_traffico_fra_altri_che_ce_l_hanno():
    """Meglio sovrastimarlo e vederlo in cima che perderlo in fondo per un dato
    che manca."""
    conf = _config(Template(nome="A", url="https://x.it/a", sessioni=50000),
                   Template(nome="B", url="https://x.it/b"))
    assert conf.pesi()["https://x.it/b"] == 1.0


def test_sessioni_e_quota_insieme_sono_un_errore(tmp_path):
    file = tmp_path / "c.yaml"
    file.write_text("cliente: X\nsito: https://x.it\ntemplate:\n"
                    "  - nome: Home\n    url: https://x.it/\n"
                    "    sessioni: 100\n    quota_traffico: 0.5\n", encoding="utf-8")
    with pytest.raises(ErroreSpeed) as info:
        carica(file)
    assert "alternativi" in info.value.rimedio


def test_traffico_negativo_e_un_errore(tmp_path):
    file = tmp_path / "c.yaml"
    file.write_text("cliente: X\nsito: https://x.it\ntemplate:\n"
                    "  - nome: Home\n    url: https://x.it/\n    sessioni: -5\n",
                    encoding="utf-8")
    with pytest.raises(ErroreSpeed):
        carica(file)


def test_il_traffico_si_legge_dal_yaml(tmp_path):
    file = tmp_path / "c.yaml"
    file.write_text("cliente: X\nsito: https://x.it\ntemplate:\n"
                    "  - nome: Home\n    url: https://x.it/\n    sessioni: 82000\n"
                    "  - nome: Cat\n    url: https://x.it/c\n    quota_traffico: 0.1\n",
                    encoding="utf-8")
    conf = carica(file)
    assert conf.traffico_dichiarato is True
    assert conf.template[0].traffico == 82000.0
    assert conf.template[1].traffico == 0.1


# --- effetto sull'ordinamento ------------------------------------------------ #

def test_punteggio_e_gravita_per_peso():
    assert _problema("alta").punteggio == 3.0
    p = _problema("bassa")
    p.peso = 0.5
    assert p.punteggio == 0.5


def test_senza_peso_l_ordine_e_quello_di_prima():
    """Con peso uniforme la moltiplicazione non deve cambiare niente."""
    problemi = [_problema("bassa", "c"), _problema("alta", "a"), _problema("media", "b")]
    for p in problemi:
        p.peso = 1.0
    problemi.sort(key=lambda p: (-p.punteggio, not p.azionabile, -p.risparmio))
    assert [p.codice for p in problemi] == ["a", "b", "c"]


def test_il_traffico_puo_ribaltare_la_gravita():
    """Una gravita' media sul template principale batte una gravita' alta su un
    template marginale: e' il punto del peso."""
    principale = _problema("media", "principale")
    principale.peso = 1.0
    marginale = _problema("alta", "marginale")
    marginale.peso = 0.05
    assert principale.punteggio > marginale.punteggio


def test_a_parita_di_peso_vince_la_gravita():
    alto = _problema("alta", "a")
    basso = _problema("bassa", "b")
    alto.peso = basso.peso = 0.4
    assert alto.punteggio > basso.punteggio


def test_diagnostica_applica_il_peso_a_tutti_i_problemi():
    from speed.core.extract import FattiPagina
    fatti = FattiPagina(url="https://x.it/", form_factor="PHONE")
    problemi = diagnose.diagnostica(fatti, {}, None, None, peso=0.25)
    assert all(p.peso == 0.25 for p in problemi)


# --- quanto vale un intervento e su cosa agisce ------------------------------ #

def _opportunita(**kwargs):
    from speed.core.extract import Opportunita
    base = dict(audit="x", titolo="T", descrizione="", documentazione="", display="",
                score=0, risparmi={})
    base.update(kwargs)
    return Opportunita(**base)


def test_il_guadagno_e_un_tempo_quando_lighthouse_lo_da():
    testo, tipo = diagnose.guadagno_di(_opportunita(risparmi={"LCP": 1350.0}))
    assert (testo, tipo) == ("1.350 ms su LCP", "tempo")


def test_fra_piu_metriche_vince_il_risparmio_maggiore():
    testo, _ = diagnose.guadagno_di(_opportunita(risparmi={"LCP": 600.0, "FCP": 1100.0}))
    assert "1.100 ms su FCP" == testo


def test_il_cls_non_e_un_tempo():
    """Il CLS e' adimensionale: non puo' finire in una casella che dice millisecondi."""
    testo, tipo = diagnose.guadagno_di(_opportunita(risparmi={"CLS": 0.095},
                                                   display="Risparmio di 0,095"))
    assert tipo == "peso", "senza metriche di tempo si ripiega sul displayValue"


def test_senza_tempo_si_mostra_il_peso():
    testo, tipo = diagnose.guadagno_di(
        _opportunita(display="Risparmio stimato di 521 KiB"))
    assert (testo, tipo) == ("Risparmio stimato di 521 KiB", "peso")


def test_senza_niente_non_si_inventa_un_numero():
    """Per otto interventi su tredici Lighthouse non da' un tempo: convertire byte
    in secondi con una regola nostra sarebbe inventare."""
    assert diagnose.guadagno_di(_opportunita()) == ("", "")
    assert diagnose.guadagno_di(_opportunita(display="Nessun problema")) == ("", "")


def test_i_bersagli_mettono_prima_i_nodi_del_dom():
    from speed.core.extract import Elemento, Risorsa
    opportunita = _opportunita(
        elementi=[Elemento(selettore="div.hero", misura=0.09)],
        risorse=[Risorsa(url="https://x.it/a.js", byte_sprecati=51200)])
    bersagli = diagnose.bersagli_di(opportunita)
    assert bersagli[0][0] == "div.hero", "il selettore e' cio' che si cerca per primo"
    assert bersagli[1][0] == "a.js", "il file si nomina senza il percorso completo"


def test_i_bersagli_sono_pochi():
    from speed.core.extract import Risorsa
    opportunita = _opportunita(
        risorse=[Risorsa(url=f"https://x.it/{i}.js", byte_sprecati=1000) for i in range(9)])
    assert len(diagnose.bersagli_di(opportunita)) == 3


def test_il_bersaglio_porta_il_dettaglio_per_esteso():
    """Il nome breve sta nella scheda, l'URL intero nel titolo al passaggio del mouse."""
    from speed.core.extract import Risorsa
    bersagli = diagnose.bersagli_di(
        _opportunita(risorse=[Risorsa(url="https://x.it/lungo/percorso/a.js",
                                      byte_sprecati=1000)]))
    assert bersagli[0][0] == "a.js"
    assert bersagli[0][2] == "https://x.it/lungo/percorso/a.js"
