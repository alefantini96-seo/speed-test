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
import hmac
import json
import os
import tempfile
import time
from datetime import date
from pathlib import Path

from speed.errori import ErroreSpeed
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
    di chi la installa, non un default che nascondiamo.

    Il confronto usa compare_digest: `==` esce al primo carattere diverso, e il
    tempo di risposta lascia indovinare la password un carattere alla volta.
    """
    attesa = os.getenv("SPEED_PASSWORD")
    if not attesa:
        return True
    fornita = richiesta.get("password")
    if not isinstance(fornita, str):
        return False
    return hmac.compare_digest(fornita.encode("utf-8"), attesa.encode("utf-8"))


# --------------------------------------------------------------------------- #
#  Limite di richieste
#
#  Senza SPEED_PASSWORD chiunque abbia il link consuma le 25.000 richieste PSI
#  giornaliere del progetto Google di chi ospita l'app.
#
#  LIMITE DICHIARATO: il contatore vive nella memoria dell'istanza. Su una
#  piattaforma serverless le istanze sono piu' d'una e vengono ricreate, quindi
#  questo argina un abuso da una sola sorgente su un'istanza calda, non un attacco
#  distribuito. Un limite vero vorrebbe uno stato condiviso, cioe' un database:
#  la scelta di non averne uno e' deliberata (vedi ADR-003).
# --------------------------------------------------------------------------- #

LIMITE_RICHIESTE = 40          # analisi per finestra, per indirizzo
FINESTRA_SECONDI = 3600

_conteggio: dict = {}


def _origine(environ) -> str:
    inoltrato = environ.get("HTTP_X_FORWARDED_FOR", "")
    return (inoltrato.split(",")[0].strip() if inoltrato
            else environ.get("REMOTE_ADDR", "sconosciuta"))


def _oltre_il_limite(environ, adesso=None) -> bool:
    adesso = time.time() if adesso is None else adesso
    chiave = _origine(environ)
    recenti = [t for t in _conteggio.get(chiave, []) if adesso - t < FINESTRA_SECONDI]
    if len(recenti) >= LIMITE_RICHIESTE:
        _conteggio[chiave] = recenti
        return True
    recenti.append(adesso)
    _conteggio[chiave] = recenti
    # Le origini inattive non restano in memoria per sempre.
    if len(_conteggio) > 500:
        for altra, tempi in list(_conteggio.items()):
            if not any(adesso - t < FINESTRA_SECONDI for t in tempi):
                _conteggio.pop(altra, None)
    return False


def _pagina(avvia):
    corpo = PAGINA.read_bytes()
    avvia("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                     ("Content-Length", str(len(corpo))),
                     ("Cache-Control", "no-store")])
    return [corpo]


def _stato(avvia, richiesta: dict):
    """Dice quali variabili d'ambiente il server vede davvero.

    Serve a distinguere in un secondo fra "non l'ho impostata", "l'ho impostata
    dopo il deploy e non e' stata iniettata" e "l'ho impostata sull'ambiente
    sbagliato". Non espone MAI un valore: al massimo la lunghezza, che basta a
    smascherare un incollaggio troncato o una stringa vuota.

    Con la password configurata la richiede, come gli altri endpoint. Senza,
    risponde in forma ridotta — solo presenza, niente lunghezze — perche' altrimenti
    annuncerebbe a chiunque abbia il link che l'app e' senza protezione, insieme a
    quanto e' lunga la chiave. La diagnosi resta possibile proprio nel caso in cui
    serve: quando la password non e' arrivata al server.
    """
    protetta = bool(os.getenv("SPEED_PASSWORD"))
    if protetta and not _password_valida(richiesta):
        return _json(avvia, "401 Unauthorized", {
            "errore": "Password non valida.",
            "rimedio": 'Lo stato e protetto: chiamalo in POST con {"password": "..."}.'})

    def descrivi(nome, con_lunghezza):
        valore = os.getenv(nome)
        if valore is None:
            return "assente"
        if not valore.strip():
            return "presente ma vuota"
        return f"presente ({len(valore)} caratteri)" if con_lunghezza else "presente"

    risposta = {
        "GOOGLE_API_KEY": descrivi("GOOGLE_API_KEY", protetta),
        "SPEED_PASSWORD": descrivi("SPEED_PASSWORD", protetta),
        "nota": "Le variabili vengono iniettate al momento del deploy: se le hai "
                "aggiunte dopo, serve un redeploy perche' arrivino.",
    }
    if protetta:
        risposta["protezione"] = "attiva"
    else:
        risposta["protezione"] = ("assente: imposta SPEED_PASSWORD, altrimenti "
                                  "chiunque abbia il link consuma la tua quota Google")
    return _json(avvia, "200 OK", risposta)


def _analizza(avvia, richiesta: dict, environ):
    if not _password_valida(richiesta):
        return _json(avvia, "401 Unauthorized", {"errore": "Password non valida."})

    if _oltre_il_limite(environ):
        return _json(avvia, "429 Too Many Requests", {
            "errore": f"Troppe analisi: il limite e' {LIMITE_RICHIESTE} all'ora.",
            "rimedio": "Riprova fra un po'. Il limite protegge la quota Google "
                       "del progetto che ospita l'app."})

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
    except ErroreSpeed as errore:
        return _json(avvia, "502 Bad Gateway", {"errore": errore.messaggio,
                                                "rimedio": errore.rimedio, "url": url})
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
    if percorso == "/api/stato" and metodo in ("GET", "POST"):
        return _stato(avvia, _leggi(environ) if metodo == "POST" else {})
    if percorso == "/api/analizza" and metodo == "POST":
        return _analizza(avvia, _leggi(environ), environ)
    if percorso == "/api/report" and metodo == "POST":
        return _report(avvia, _leggi(environ))
    if percorso in ("/api/analizza", "/api/report"):
        return _json(avvia, "405 Method Not Allowed", {"errore": "Usa POST."})
    return _json(avvia, "404 Not Found", {"errore": "Percorso sconosciuto."})


# Vercel cerca `app`; questo alias serve ai server WSGI che cercano `application`.
application = app
