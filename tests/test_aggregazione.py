"""
Test del raggruppamento degli interventi.

Il caso reale che l'ha motivato: su tre template, 10 interventi su 13 comparivano
su tutti e tre — 20 schede su 37 erano ripetizioni dello stesso titolo. I file su
cui agire invece quasi non coincidevano, dal 43% allo 0% di sovrapposizione.
"""
import json
from pathlib import Path

from speed.core import consenso, diagnose, extract, thirdparty
from speed.io import crux
from speed.core.aggregazione import Intervento, raggruppa

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _problema(codice, gravita="media", bersagli=(), risorse=(), elementi=(), **extra):
    base = {"codice": codice, "titolo": f"Titolo {codice}", "gravita": gravita,
            "responsabile": "sviluppo", "fonte": "lighthouse",
            "bersagli": [list(b) for b in bersagli], "azioni": ["Descrizione"],
            "risorse": [list(r) for r in risorse], "elementi": [list(e) for e in elementi],
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


def test_un_file_comune_oltre_il_terzo_bersaglio_non_deve_sparire():
    """Il sintomo: l'intersezione girava sulle liste di resa, troncate a 3, e su
    tre voci due template non hanno quasi mai un file in comune. Qui vendor.js e'
    su entrambi ma quarto su entrambi: e' esattamente il bundle condiviso che la
    funzione esiste per trovare."""
    def pagina(nome, url, propri):
        return _pagina(nome, url, [_problema(
            "unused-javascript",
            bersagli=[(f"{n}.js", "10 KB", "") for n in propri[:3]],
            risorse=[(f"https://x.it/{n}.js", "10 KB", False) for n in propri]
                    + [("https://cdn.x.it/vendor.js", "300 KB", False)])])

    lista = raggruppa(_run(
        pagina("Home", "https://x.it/", ["a", "b", "c"]),
        pagina("Cat", "https://x.it/c", ["d", "e", "f"]),
    ))
    intervento = lista[0]
    assert all("vendor.js" not in [b[0] for b in t.bersagli]
               for t in intervento.template), "il caso ha senso solo se e' fuori dai primi tre"
    assert intervento.comuni == ["vendor.js"]


def test_il_bersaglio_comune_conserva_la_sua_misura():
    """Trovato oltre i primi tre, deve comunque arrivare in tabella con l'impatto:
    una riga "vendor.js" senza numero non serve a chi implementa."""
    def pagina(nome, url, propri):
        return _pagina(nome, url, [_problema(
            "unused-javascript",
            bersagli=[(f"{n}.js", "10 KB", "") for n in propri],
            risorse=[(f"https://x.it/{n}.js", "10 KB", False) for n in propri]
                    + [("https://cdn.x.it/vendor.js", "300 KB", False)])])

    intervento = raggruppa(_run(pagina("Home", "https://x.it/", ["a", "b", "c"]),
                                pagina("Cat", "https://x.it/c", ["d", "e", "f"])))[0]
    assert intervento.misura_di("vendor.js") ==         ("vendor.js", "300 KB", "https://cdn.x.it/vendor.js")


def test_gli_elementi_del_dom_entrano_nel_confronto():
    """Per gli audit sul CLS i bersagli sono nodi, non file: la stessa regola."""
    def pagina(nome, url, propri):
        return _pagina(nome, url, [_problema(
            "cls-culprits-insight",
            bersagli=[(s, "0.010", "") for s in propri[:3]],
            elementi=[(s, "0.010", "1,HTML", "<div>") for s in propri]
                     + [("header.banner", "0.080", "1,HTML,0,HEADER", "<header>")])])

    intervento = raggruppa(_run(pagina("Home", "https://x.it/", [".a", ".b", ".c"]),
                                pagina("Cat", "https://x.it/c", [".d", ".e", ".f"])))[0]
    assert intervento.comuni == ["header.banner"]


def test_il_troncamento_resta_nella_lista_di_resa():
    """`bersagli` non cresce: e' quella che finisce nel payload e nelle tabelle."""
    intervento = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema(
            "unused-javascript",
            bersagli=[("a.js", "1 KB", ""), ("b.js", "1 KB", ""), ("c.js", "1 KB", "")],
            risorse=[(f"https://x.it/{n}.js", "1 KB", False)
                     for n in ("a", "b", "c", "d", "e", "f")])])))[0]
    assert len(intervento.template[0].bersagli) == 3
    assert len(intervento.template[0].tutti) == 6


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


def test_l_evidenza_viene_dal_template_messo_peggio():
    """Il sintomo: la gravita' era del peggiore, i numeri del primo template
    incontrato. Una scheda diceva "alta" mostrando le misure della pagina sana."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema(
            "x", gravita="bassa", evidenza=["Risparmio stimato di 2 KiB"],
            nota="Per gli utenti reali questa metrica e' gia' a posto.")]),
        _pagina("Cat", "https://x.it/c", [_problema(
            "x", gravita="alta", evidenza=["Risparmio stimato di 800 KiB"],
            nota="il campo dice LCP 4.180 ms (scarso).")]),
    ))
    intervento = lista[0]
    assert intervento.gravita == "alta"
    assert intervento.evidenza == ["Risparmio stimato di 800 KiB"]
    assert "4.180 ms" in intervento.nota


def test_il_guadagno_viene_dal_membro_peggiore_non_dal_primo_che_ce_l_ha():
    """Mostrare il guadagno di un template e la gravita' di un altro e' la stessa
    incoerenza: la scheda descrive un template solo, quello messo peggio."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("x", gravita="bassa",
                                                    guadagno="10 ms su LCP",
                                                    guadagno_tipo="tempo")]),
        _pagina("Cat", "https://x.it/c", [_problema("x", gravita="alta",
                                                    guadagno="600 ms su LCP",
                                                    guadagno_tipo="tempo")]),
    ))
    assert lista[0].guadagno == "600 ms su LCP" and lista[0].guadagno_tipo == "tempo"


def test_l_azionabilita_non_si_eredita_dal_template_sbagliato():
    """Marcare non azionabile un intervento che altrove lo e' lo toglie dal
    master plan per il motivo sbagliato."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema("cache-insight", gravita="bassa",
                                                    azionabile=False)]),
        _pagina("Cat", "https://x.it/c", [_problema("cache-insight", gravita="alta",
                                                    azionabile=True)]),
    ))
    assert lista[0].gravita == "alta" and lista[0].azionabile is True


def test_la_scheda_aggregata_descrive_un_template_solo():
    """Tutti i campi non per-template vengono dallo stesso membro: e' cio' che
    masterplan.costruisci fa gia' sulla riga aggregata."""
    peggiore = _problema("x", gravita="alta", evidenza=["800 KiB"],
                         nota="nota del peggiore", documentazione="https://peggiore",
                         guadagno="600 ms su LCP", azioni=["Azione del peggiore"],
                         responsabile="infrastruttura")
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema(
            "x", gravita="media", evidenza=["2 KiB"], nota="nota del primo",
            documentazione="https://primo", azioni=["Azione del primo"],
            responsabile="sviluppo")]),
        _pagina("Cat", "https://x.it/c", [peggiore]),
    ))
    intervento = lista[0]
    assert intervento.evidenza == ["800 KiB"]
    assert intervento.nota == "nota del peggiore"
    assert intervento.documentazione == "https://peggiore"
    assert intervento.azioni == ["Azione del peggiore"]
    assert intervento.responsabile == "infrastruttura"


def test_i_bersagli_restano_di_ogni_template():
    """L'unica cosa che NON viene dal peggiore: i file cambiano per pagina, ed e'
    tutto il motivo per cui la scheda li tiene separati."""
    lista = raggruppa(_run(
        _pagina("Home", "https://x.it/", [_problema(
            "x", gravita="bassa", bersagli=[("home.js", "50 KB", "")])]),
        _pagina("Cat", "https://x.it/c", [_problema(
            "x", gravita="alta", bersagli=[("cat.js", "30 KB", "")])]),
    ))
    nomi = {t.nome: [b[0] for b in t.bersagli] for t in lista[0].template}
    assert nomi == {"Home": ["home.js"], "Cat": ["cat.js"]}


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


# --- sui due PSI reali -------------------------------------------------------- #

def _pagina_reale(nome_template, nome_fixture, url):
    """Una pagina come la produce un run, dai fixture e senza rete."""
    psi = json.loads((FIXTURES / nome_fixture).read_text(encoding="utf-8"))
    accordo = consenso.combina([extract.estrai(psi, url, "PHONE")])
    fatti = accordo.fatti
    metriche = crux.leggi_record(
        json.loads((FIXTURES / "crux-bbc.json").read_text(encoding="utf-8")))["metriche"]
    riepilogo = thirdparty.riepiloga(fatti.richieste, url)
    pagina = {"template": nome_template, "url": url,
              "problemi": diagnose.diagnostica(fatti, metriche, riepilogo, accordo)}
    return json.loads(json.dumps(pagina, default=lambda o: o.__dict__,
                                 ensure_ascii=False))


def test_sui_fixture_il_bundle_condiviso_si_vede():
    """Su bootup-time require.js e' sesto su entrambe le misurazioni: con
    l'intersezione sui primi tre bersagli non compariva da nessuna parte."""
    lista = raggruppa({"pagine": [
        _pagina_reale("Home", "psi-bbc-mobile-it.json", "https://www.bbc.com/"),
        _pagina_reale("News", "psi-bbc-mobile-it-2.json", "https://www.bbc.com/news"),
    ]})
    bootup = next(i for i in lista if i.codice == "bootup-time")
    resa = {b[0] for t in bootup.template for b in t.bersagli}
    assert "require.js" not in resa, "il caso ha senso solo se e' fuori dalla resa"
    assert "require.js" in bootup.comuni
    assert bootup.misura_di("require.js")[1], "deve arrivare con il suo impatto"
