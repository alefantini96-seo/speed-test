"""
Endpoint Vercel: dalle pagine gia' analizzate produce il report Word.

Il browser rimanda indietro i risultati che ha accumulato, il server li impagina.
Nessuno stato lato server: non c'e' niente da conservare fra una richiesta e l'altra.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from speed.io import render_docx  # noqa: E402

LIMITE_PAGINE = 40


class handler(BaseHTTPRequestHandler):

    def _errore(self, codice: int, messaggio: str):
        corpo = json.dumps({"errore": messaggio}, ensure_ascii=False).encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_POST(self):
        try:
            lunghezza = int(self.headers.get("Content-Length") or 0)
            richiesta = json.loads(self.rfile.read(lunghezza) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._errore(400, "Richiesta non valida.")

        attesa = os.getenv("SPEED_PASSWORD")
        if attesa and richiesta.get("password") != attesa:
            return self._errore(401, "Password non valida.")

        pagine = richiesta.get("pagine") or []
        if not pagine:
            return self._errore(400, "Nessuna pagina da impaginare.")
        if len(pagine) > LIMITE_PAGINE:
            return self._errore(400, f"Troppe pagine: il massimo e' {LIMITE_PAGINE}.")

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
            return self._errore(500, f"Generazione fallita: {str(exc)[:200]}")

        nome = f"Report velocita {date.today():%d%m%Y}.docx"
        self.send_response(200)
        self.send_header("Content-Type",
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
        self.send_header("Content-Length", str(len(contenuto)))
        self.end_headers()
        self.wfile.write(contenuto)
