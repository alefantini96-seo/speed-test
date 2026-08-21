"""
Applicazione WSGI: l'involucro della versione online.

Vercel carica questo file e gli manda **tutte** le richieste, statiche comprese:
in modalita' applicazione Python non esiste piu' l'instradamento file-per-file di
`api/`. Quindi qui si serve anche la pagina, oltre ai due endpoint.

Nessuna dipendenza: WSGI e' nella libreria standard. La logica vera sta in
`speed/web.py`, che e' testabile senza alzare un server.

    /                  la pagina
    POST /api/analizza {url, password} -> analisi di una singola pagina
    POST /api/report   {pagine}        -> report Word da scaricare
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from speed.io import render_docx
from speed.web import LIMITE_PAGINE, analizza_una, serializza, valida_url

RADICE = Path(__file__).resolve().parent
PAGINA = RADICE / "public" / "index.html"

TIPO_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _json(avvia, codice: str, corpo: dict):
    testo = json.dumps(corpo, default=serializza, ensure_ascii=False).encode("utf-8")
    avvia(codice, [("Content-Type", "application/json; charset=utf-8"),
                   ("Content-Length", str(len(testo)))])
    return [testo]


def _leggi(environ) -> dict:
    try:
        lunghezza = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return {}
    if lunghezza <= 0:
        return {}
    try:
        return json.loads(environ["wsgi.input"].read(lunghezza) or b"{}")
    except (ValueError, json.JSONDecodeError):
        return {}


def _password_valida(richiesta: dict) -> bool:
    """Senza SPEED_PASSWORD impostata l'app resta aperta: e' una scelta esplicita
    di chi la installa, non un default che nascondiamo."""
    attesa = os.getenv("SPEED_PASSWORD")
    return not attesa or richiesta.get("password") == attesa


def _pagina(avvia):
    corpo = PAGINA.read_bytes()
    avvia("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                     ("Content-Length", str(len(corpo))),
                     ("Cache-Control", "no-store")])
    return [corpo]


def _stato(avvia):
    """Dice quali variabili d'ambiente il server vede davvero.

    Serve a distinguere in un secondo fra "non l'ho impostata", "l'ho impostata
    dopo il deploy e non e' stata iniettata" e "l'ho impostata sull'ambiente
    sbagliato". Non espone alcun valore: solo presenza e lunghezza, che bastano
    a smascherare un incollaggio troncato o una stringa vuota.
    """
    def descrivi(nome):
        valore = os.getenv(nome)
        if valore is None:
            return "assente"
        if not valore.strip():
            return "presente ma vuota"
        return f"presente ({len(valore)} caratteri)"

    return _json(avvia, "200 OK", {
        "GOOGLE_API_KEY": descrivi("GOOGLE_API_KEY"),
        "SPEED_PASSWORD": descrivi("SPEED_PASSWORD"),
        "protezione": "attiva" if os.getenv("SPEED_PASSWORD") else
                      "ASSENTE: l'app e' aperta a chiunque abbia il link",
        "nota": "Le variabili vengono iniettate al momento del deploy: se le hai "
                "aggiunte dopo, serve un redeploy perche' arrivino.",
    })


def _analizza(avvia, richiesta: dict):
    if not _password_valida(richiesta):
        return _json(avvia, "401 Unauthorized", {"errore": "Password non valida."})

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _json(avvia, "500 Internal Server Error", {
            "errore": "GOOGLE_API_KEY non configurata sul server.",
            "rimedio": "Impostala nelle variabili d'ambiente del progetto Vercel."})

    url = (richiesta.get("url") or "").strip()
    problema = valida_url(url)
    if problema:
        return _json(avvia, "400 Bad Request", {"errore": "URL non valido.",
                                                "rimedio": problema})

    form_factor = "DESKTOP" if richiesta.get("desktop") else "PHONE"
    domini = [d for d in (richiesta.get("domini_propri") or []) if isinstance(d, str)]
    try:
        risultato = asyncio.run(analizza_una(api_key, url, form_factor, domini))
    except Exception as exc:
        return _json(avvia, "502 Bad Gateway", {"errore": str(exc)[:400], "url": url})
    return _json(avvia, "200 OK", risultato)


def _report(avvia, richiesta: dict):
    if not _password_valida(richiesta):
        return _json(avvia, "401 Unauthorized", {"errore": "Password non valida."})

    pagine = richiesta.get("pagine") or []
    if not pagine:
        return _json(avvia, "400 Bad Request", {"errore": "Nessuna pagina da impaginare."})
    if len(pagine) > LIMITE_PAGINE:
        return _json(avvia, "400 Bad Request",
                     {"errore": f"Troppe pagine: il massimo e' {LIMITE_PAGINE}."})

    # Il nome del cliente non lo conosciamo: usiamo il dominio analizzato.
    primo = pagine[0].get("url", "")
    dominio = primo.split("//")[-1].split("/")[0] if primo else "sito"
    esecuzione = {
        "cliente": dominio,
        "sito": f"https://{dominio}",
        "data": date.today().isoformat(),
        "form_factor": "DESKTOP" if richiesta.get("desktop") else "PHONE",
        "pagine": pagine,
    }

    try:
        with tempfile.TemporaryDirectory() as cartella:
            percorso = Path(cartella) / "report.docx"
            render_docx.docx_report(esecuzione, percorso)
            contenuto = percorso.read_bytes()
    except Exception as exc:
        return _json(avvia, "500 Internal Server Error",
                     {"errore": f"Generazione fallita: {str(exc)[:200]}"})

    nome = f"Report velocita {date.today():%d%m%Y}.docx"
    avvia("200 OK", [("Content-Type", TIPO_DOCX),
                     ("Content-Disposition", f'attachment; filename="{nome}"'),
                     ("Content-Length", str(len(contenuto)))])
    return [contenuto]


def app(environ, avvia):
    percorso = environ.get("PATH_INFO", "/").rstrip("/") or "/"
    metodo = environ.get("REQUEST_METHOD", "GET")

    if percorso in ("/", "/index.html") and metodo == "GET":
        return _pagina(avvia)
    if percorso == "/api/stato" and metodo == "GET":
        return _stato(avvia)
    if percorso == "/api/analizza" and metodo == "POST":
        return _analizza(avvia, _leggi(environ))
    if percorso == "/api/report" and metodo == "POST":
        return _report(avvia, _leggi(environ))
    if percorso in ("/api/analizza", "/api/report"):
        return _json(avvia, "405 Method Not Allowed", {"errore": "Usa POST."})
    return _json(avvia, "404 Not Found", {"errore": "Percorso sconosciuto."})


# Vercel cerca `app`; questo alias serve ai server WSGI che cercano `application`.
application = app
