"""
CLI del tool.

    python -m speed check-config clienti/x.yaml     verifica la copertura CrUX degli URL
    python -m speed run          clienti/x.yaml     scansione completa -> JSON + HTML + DOCX

La scansione e' una tantum: non c'e' database e non c'e' storico da accumulare.
La serie storica arriva da CrUX History a ogni esecuzione (ADR-002).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

from . import config as cfg
from .errori import ErroreSpeed
from .core import consenso, diagnose, extract, thirdparty
from .core.soglie import fasi_dal_campo
from .core.soglie import ETICHETTE, formatta, giudizio
from .io import crux, psi

SIMBOLO = {"buono": "OK", "da_migliorare": "!!", "scarso": "XX", "sconosciuto": "--"}


def _console_utf8():
    """La console Windows di default e' cp1252 e non sa stampare accenti ne' i
    caratteri di blocco delle sparkline: senza questo il primo comando muore con
    UnicodeEncodeError. Va risolto qui, non chiesto all'utente."""
    for flusso in (sys.stdout, sys.stderr):
        riconfigura = getattr(flusso, "reconfigure", None)
        if riconfigura:
            try:
                riconfigura(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _chiave(nome: str) -> str:
    load_dotenv()
    valore = os.getenv(nome)
    if not valore:
        sys.exit(f"Manca {nome}. Copiare .env.example in .env e compilarlo.")
    return valore


def _serializza(o):
    if is_dataclass(o):
        return asdict(o)
    raise TypeError(f"non serializzabile: {type(o)}")


# --------------------------------------------------------------------------- #
#  check-config
# --------------------------------------------------------------------------- #
async def _check(percorso: str) -> int:
    conf = cfg.carica(percorso)
    api_key = _chiave("GOOGLE_API_KEY")
    print(f"{conf.cliente} — {len(conf.template)} template, form factor {conf.form_factor}\n")

    async with httpx.AsyncClient() as client:
        esiti = await asyncio.gather(*(
            crux.disponibilita(client, api_key, t.url, conf.form_factor)
            for t in conf.template
        ))
        try:
            origin = await crux.record(client, api_key, conf.sito, conf.form_factor, origin=True)
        except Exception:
            origin = None

    senza = 0
    for t, e in zip(conf.template, esiti):
        if e["campo_url"]:
            lcp = e["metriche"].get("largest_contentful_paint")
            print(f"  [campo] {t.nome:22s} LCP {formatta('largest_contentful_paint', lcp)}"
                  f"  ({SIMBOLO[giudizio('largest_contentful_paint', lcp)]})   {t.url}")
        else:
            senza += 1
            print(f"  [SOLO LAB] {t.nome:19s} nessun dato di campo               {t.url}")

    if origin:
        print(f"\n  origin {conf.sito}: " + "  ".join(
            f"{ETICHETTE[m]} {formatta(m, v)}" for m, v in origin["metriche"].items()
            if m in ETICHETTE))

    if senza:
        print(f"\n  {senza} template su {len(conf.template)} non hanno dati di campo.")
        print("  Sostituiscili con la pagina piu' trafficata dello stesso template:")
        print("  senza campo resta solo la diagnosi lab, senza metrica ne' storico.")
    else:
        print("\n  Tutti i template hanno dati di campo a livello di URL.")
    return 1 if senza else 0


async def _mostra_entita(conf: cfg.Config, api_key: str) -> None:
    """Elenca chi serve gli asset della prima pagina.

    Serve a compilare `domini_propri`: un cliente che serve gli asset da un dominio
    diverso (CDN, dominio fratello) verrebbe altrimenti classificato come terza
    parte, e il tool assegnerebbe a marketing il lavoro degli sviluppatori.
    """
    prima = conf.template[0]
    print(f"\n  chi serve gli asset di {prima.nome} (una misurazione lab)...", flush=True)
    try:
        async with httpx.AsyncClient() as client:
            risposta = await psi.analizza(client, api_key, prima.url, conf.strategy)
    except Exception as exc:
        print(f"    non verificabile: {exc}")
        return

    fatti = extract.estrai(risposta, prima.url, conf.form_factor, conf.domini_propri)
    riepilogo = thirdparty.riepiloga(fatti.richieste, prima.url, conf.domini_propri)
    for entita in riepilogo.entita[:8]:
        marchio = "proprio" if not entita.terza_parte else "terza parte"
        print(f"    [{marchio:11s}] {entita.nome[:28]:28s} {entita.kb:7.0f} KB")
    if conf.domini_propri:
        print(f"    domini dichiarati come propri: {', '.join(conf.domini_propri)}")
    else:
        print("    Se fra le 'terza parte' compare un dominio del cliente (CDN, dominio")
        print("    fratello), aggiungilo a domini_propri nel YAML: cambia a chi viene")
        print("    assegnato l'intervento.")


# --------------------------------------------------------------------------- #
#  run
# --------------------------------------------------------------------------- #
async def _dati_campo(api_key: str, conf: cfg.Config, parallelismo: int = 10) -> dict:
    """Campo e andamento per tutti i template, in parallelo.

    Prima si procedeva in serie, due chiamate per URL: su venti template erano una
    quarantina di round trip messi in fila senza motivo. CrUX regge 150 richieste
    al minuto, e `check-config` usava gia' asyncio.gather.

    Il semaforo a 10 lascia margine sotto il limite anche se qualcuno lancia due
    scansioni insieme.
    """
    sem = asyncio.Semaphore(parallelismo)
    out: dict = {}

    async with httpx.AsyncClient() as client:
        async def una(url: str):
            async with sem:
                try:
                    out[url] = await crux.raccogli(client, api_key, url, conf.form_factor)
                except Exception as exc:
                    # Un URL che fallisce non deve fermare la scansione degli altri:
                    # il report dichiara il buco invece di non esistere.
                    out[url] = {"livello": "errore", "metriche": {}, "storico": None,
                                "errore": str(exc)}

        await asyncio.gather(*(una(t.url) for t in conf.template))
    return out


async def _run(percorso: str, desktop: bool, formato: str, ripetizioni: int) -> int:
    conf = cfg.carica(percorso)
    if desktop:
        conf.form_factor = "DESKTOP"
    api_key = _chiave("GOOGLE_API_KEY")

    print(f"{conf.cliente} — {len(conf.template)} template ({conf.strategy})")
    print("  campo (CrUX)...", flush=True)
    campo = await _dati_campo(api_key, conf)

    def avviso(giro, totale, attesa):
        if attesa > 0:
            print(f"    attendo {attesa:.0f}s prima del giro {giro + 1}: PSI serve "
                  f"dalla cache le chiamate ravvicinate", flush=True)
        else:
            print(f"    giro {giro}/{totale} di misurazione lab...", flush=True)

    # Le ripetizioni servono solo dove la ripartizione LCP NON arriva dal campo:
    # li' la fase dominante va stabilita sul laboratorio, che oscilla (ADR-005).
    if ripetizioni is None:
        senza_fasi = [u for u, v in campo.items()
                      if not fasi_dal_campo(v.get("metriche") or {})]
        ripetizioni = 3 if senza_fasi else 1
        if senza_fasi:
            print(f"  {len(senza_fasi)} URL su {len(conf.template)} non hanno le fasi LCP "
                  f"nel campo: servono {ripetizioni} misurazioni lab per pagina.", flush=True)
        else:
            print("  le fasi LCP arrivano dal campo per tutti gli URL: "
                  "basta una misurazione lab per pagina.", flush=True)

    print(f"  lab (PageSpeed Insights), {ripetizioni} giri per URL:", flush=True)
    risposte = await psi.analizza_molte(api_key, conf.urls, conf.strategy,
                                        ripetizioni=ripetizioni, avviso=avviso)

    pagine = []
    for t in conf.template:
        riuscite = [r for r in risposte.get(t.url, []) if not isinstance(r, Exception)]
        if not riuscite:
            errori = [str(r) for r in risposte.get(t.url, [])] or ["nessuna risposta"]
            print(f"  [errore] {t.nome}: {errori[0]}")
            pagine.append({"template": t.nome, "url": t.url, "errore": errori[0]})
            continue

        accordo = consenso.combina([
            extract.estrai(r, t.url, conf.form_factor, conf.domini_propri)
            for r in riuscite])
        fatti = accordo.fatti
        metriche_campo = campo.get(t.url, {}).get("metriche", {})
        riepilogo = thirdparty.riepiloga(fatti.richieste, t.url, conf.domini_propri)
        problemi = diagnose.diagnostica(fatti, metriche_campo, riepilogo, accordo)

        pagine.append({
            "template": t.nome,
            "url": t.url,
            "fatti": fatti,
            "campo": campo.get(t.url, {}),
            "misurazioni": accordo.ripetizioni,
            "concordi": accordo.concordi,
            "consenso": accordo.descrizione,
            "terze_parti": riepilogo,
            "peso_per_tipo": thirdparty.peso_per_tipo(fatti.richieste),
            "problemi": problemi,
        })
        _stampa_template(t.nome, fatti, metriche_campo, riepilogo, problemi)

    esecuzione = {
        "cliente": conf.cliente,
        "sito": conf.sito,
        "data": date.today().isoformat(),
        "form_factor": conf.form_factor,
        "pagine": pagine,
    }
    # Il report si genera dalla forma JSON, non dagli oggetti in memoria: cosi'
    # `speed report` puo' rigenerarlo da un run salvato mesi fa.
    testo_json = json.dumps(esecuzione, default=_serializza, ensure_ascii=False, indent=2)

    destinazione = Path(conf.output) if conf.output else Path("out")
    destinazione.mkdir(parents=True, exist_ok=True)
    stem_dati, stem_report = _nomi(conf)
    percorso_json = destinazione / f"{stem_dati}.json"
    percorso_json.write_text(testo_json, encoding="utf-8")
    print(f"\n  dati grezzi: {percorso_json}")

    for percorso in _scrivi_report(json.loads(testo_json), destinazione, stem_report, formato):
        print(f"  report:      {percorso}")
    return 0


def _nomi(conf: cfg.Config):
    """(nome file dati, nome file report).

    Convenzione del workspace: il nome del cliente compare nel file solo se il file
    non e' gia' dentro la sua cartella. Niente versioni nel nome.
    """
    oggi = f"{date.today():%d%m%Y}"
    if conf.output:
        return (f"dati velocita {oggi}", f"Report velocità {oggi}")
    slug = conf.cliente.replace(" ", "-")
    return (f"dati velocita {slug} {oggi}", f"Report velocità {slug} {oggi}")


def _scrivi_report(esecuzione: dict, destinazione: Path, stem: str, formato: str) -> list:
    scritti = []
    if formato in ("html", "entrambi"):
        from .io import render
        percorso = destinazione / f"{stem}.html"
        percorso.write_text(render.html_report(esecuzione), encoding="utf-8")
        scritti.append(percorso)
    if formato in ("docx", "entrambi"):
        from .io import render_docx
        scritti.append(render_docx.docx_report(esecuzione, destinazione / f"{stem}.docx"))
    return scritti


def _report(percorso_json: str, formato: str) -> int:
    """Rigenera il report da un run gia' salvato, senza rifare le chiamate."""
    origine = Path(percorso_json)
    esecuzione = json.loads(origine.read_text(encoding="utf-8"))
    stem = origine.stem.replace("dati velocita", "Report velocità")
    for percorso in _scrivi_report(esecuzione, origine.parent, stem, formato):
        print(f"  report: {percorso}")
    return 0


def _stampa_template(nome, fatti, campo, riepilogo, problemi):
    print(f"\n  --- {nome} ---")
    if campo:
        print("   campo: " + "   ".join(
            f"{ETICHETTE[m]} {formatta(m, v)} {SIMBOLO[giudizio(m, v)]}"
            for m, v in campo.items() if m in ETICHETTE))
    else:
        print("   campo: assente (solo diagnosi lab)")
    fase, quota = fatti.lcp_fase_dominante
    if fase:
        print(f"   LCP: {extract.FASI_IT[fase]} = {quota * 100:.0f}% del tempo")
    print(f"   peso: {riepilogo.byte_totali / 1024:.0f} KB "
          f"({riepilogo.quota_terzi * 100:.0f}% terze parti, {riepilogo.richieste_totali} richieste)")
    for p in problemi:
        marchio = "" if p.azionabile else "  [non azionabile]"
        print(f"   [{p.gravita:5s}] {p.titolo[:62]:62s} {p.responsabile}{marchio}")


def main(argv=None) -> int:
    _console_utf8()
    parser = argparse.ArgumentParser(prog="speed", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_check = sub.add_parser("check-config", help="verifica la copertura CrUX degli URL")
    p_check.add_argument("config")

    p_run = sub.add_parser("run", help="scansione completa")
    p_run.add_argument("config")
    p_run.add_argument("--desktop", action="store_true", help="misura desktop invece di mobile")
    p_run.add_argument("--formato", choices=("html", "docx", "entrambi"), default="entrambi")
    p_run.add_argument("--ripetizioni", type=int, default=None,
                       help="misurazioni lab per URL; senza valore decide il tool: "
                            "1 se le fasi LCP arrivano dal campo, altrimenti 3")

    p_rep = sub.add_parser("report", help="rigenera l'HTML da un run salvato")
    p_rep.add_argument("json")
    p_rep.add_argument("--formato", choices=("html", "docx", "entrambi"), default="entrambi")

    args = parser.parse_args(argv)
    # Gli errori previsti portano con se' il rimedio: si stampano, non si
    # rovesciano addosso a chi ha lanciato il comando sotto forma di traceback.
    try:
        if args.comando == "check-config":
            return asyncio.run(_check(args.config))
        if args.comando == "report":
            return _report(args.json, args.formato)
        return asyncio.run(_run(args.config, args.desktop, args.formato, args.ripetizioni))
    except ErroreSpeed as errore:
        print("", file=sys.stderr)
        print(errore, file=sys.stderr)
        return 1
