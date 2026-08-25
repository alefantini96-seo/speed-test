"""
Test del raggruppamento degli interventi.

Il caso reale che l'ha motivato: su tre template, 10 interventi su 13 comparivano
su tutti e tre — 20 schede su 37 erano ripetizioni dello stesso titolo. I file su
cui agire invece quasi non coincidevano, dal 43% allo 0% di sovrapposizione.
"""
from speed.core.aggregazione import Intervento, raggruppa


def _problema(codice, gravita="media", bersagli=(), **extra):
    base = {"codice": codice, "titolo": f"Titolo {codice}", "gravita": gravita,
            "responsabile": "sviluppo", "fonte": "lighthouse",
            "bersagli": [list(b) for b in bersagli], "azioni": ["Descrizione"],
            "evidenza": [], "nota": "", "documentazione": "", "azionabile": True,
            "guadagno": "", "guadagno_tipo": ""}
    base.update(extra)
    return base


def _run(*pagine):
    return {"cliente": "X", "sito": "https://x.it", "pagine": list(pagine)}


def _pagina(nome, url, problemi):
    return {"template": nome, "url": url, "problemi": problemi}


# --- raggruppamento ---------------------------------------------------------- #

def test_lo_stesso_intervento_su_tre_template_diventa_uno():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("unused-javascript")]),
        _pagina("Cat", "https://x.it/c", [_problema("unused-javascript")]),
        _pagina("Prod", "https://x.it/p", [_problema("unused-javascript")]),
    ))
    assert len(lista) == 1
    assert lista[0].quanti == 3 and lista[0].totale_template == 3


def test_ogni_template_conserva_i_suoi_bersagli():
    """I file non coincidono fra template: raggruppare il titolo non deve
    perderli."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema(
            "unused-javascript", bersagli=[("home.js", "50 KB", "https://x.it/home.js")])]),
        _pagina("Cat", "https://x.it/c", [_problema(
            "unused-javascript", bersagli=[("cat.js", "30 KB", "https://x.it/cat.js")])]),
    ))
    nomi = {t.nome: [b[0] for b in t.bersagli] for t in lista[0].template}
    assert nomi == {"Home": ["home.js"], "Cat": ["cat.js"]}


def test_i_bersagli_comuni_a_tutti_i_template_vengono_isolati():
    """Sono il bundle condiviso: sistemarli una volta vale per tutto il sito."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("unused-javascript", bersagli=[
            ("vendor.js", "100 KB", ""), ("home.js", "50 KB", "")])]),
        _pagina("Cat", "https://x.it/c", [_problema("unused-javascript", bersagli=[
            ("vendor.js", "100 KB", ""), ("cat.js", "30 KB", "")])]),
    ))
    intervento = lista[0]
    assert intervento.comuni == ["vendor.js"]
    propri = {t.nome: [b[0] for b in intervento.propri_di(t)] for t in intervento.template}
    assert propri == {"Home": ["home.js"], "Cat": ["cat.js"]}


def test_con_un_solo_template_non_esistono_bersagli_comuni():
    """Con una pagina sola la nozione non ha senso e direbbe una cosa falsa."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x", bersagli=[("a.js", "1 KB", "")])])))
    assert lista[0].comuni == []


def test_un_bersaglio_manca_su_un_template_e_non_e_comune():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x", bersagli=[
            ("vendor.js", "1 KB", ""), ("solo-home.js", "1 KB", "")])]),
        _pagina("Cat", "https://x.it/c", [_problema("x", bersagli=[
            ("vendor.js", "1 KB", "")])]),
    ))
    assert lista[0].comuni == ["vendor.js"]


def test_un_template_senza_bersagli_azzera_i_comuni():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x", bersagli=[("a.js", "1 KB", "")])]),
        _pagina("Cat", "https://x.it/c", [_problema("x", bersagli=[])]),
    ))
    assert lista[0].comuni == []


# --- gravita' e ordine -------------------------------------------------------- #

def test_fra_due_template_vale_la_gravita_peggiore():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x", gravita="bassa")]),
        _pagina("Cat", "https://x.it/c", [_problema("x", gravita="alta")]),
    ))
    assert lista[0].gravita == "alta"


def test_ordine_per_gravita_poi_per_quanti_template():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [
            _problema("diffuso", gravita="media"),
            _problema("isolato", gravita="media"),
            _problema("grave", gravita="alta")]),
        _pagina("Cat", "https://x.it/c", [_problema("diffuso", gravita="media")]),
    ))
    assert [i.codice for i in lista] == ["grave", "diffuso", "isolato"]


def test_il_guadagno_si_conserva_dal_primo_template_che_lo_dichiara():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x")]),
        _pagina("Cat", "https://x.it/c", [_problema("x", guadagno="600 ms su LCP",
                                                    guadagno_tipo="tempo")]),
    ))
    assert lista[0].guadagno == "600 ms su LCP" and lista[0].guadagno_tipo == "tempo"


# --- robustezza --------------------------------------------------------------- #

def test_le_pagine_fallite_non_contano():
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x")]),
        {"template": "Rotta", "url": "https://x.it/r", "errore": "PSI 502"}))
    assert lista[0].totale_template == 1


def test_run_senza_pagine():
    assert raggruppa({"pagine": []}) == []


def test_la_riduzione_e_reale():
    """Tre template con dieci interventi in comune: da 30 schede a 10."""
    problemi = [_problema(f"audit-{i}") for i in range(10)]
    lista = raggruppa(_run(*[_pagina(f"T{n}", f"https://x.it/{n}", problemi)
                             for n in range(3)]))
    assert len(lista) == 10, "trenta schede diventano dieci"
    assert all(i.quanti == 3 for i in lista)
