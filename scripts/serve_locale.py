"""
Server locale che imita l'instradamento di Vercel.

Serve `public/` come sito statico e manda `/api/<nome>` all'handler in
`api/<nome>.py`. Non e' usato in produzione: esiste per poter provare la versione
web senza fare un deploy a ogni modifica.

    python scripts/serve_locale.py           # http://localhost:8000

Legge .env dalla radice del progetto, come la CLI.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RADICE / ".env")


def _carica_handler(nome: str):
    percorso = RADICE / "api" / f"{nome}.py"
    if not percorso.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"api_{nome}", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return getattr(modulo, "handler", None)


class Instradatore(SimpleHTTPRequestHandler):
    """Statico da public/, dinamico da api/."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(RADICE / "public"), **kwargs)

    def _delega(self, metodo: str) -> bool:
        if not self.path.startswith("/api/"):
            return False
        nome = self.path[len("/api/"):].split("?")[0].strip("/")
        handler = _carica_handler(nome)
        if handler is None:
            self.send_error(404, f"nessun endpoint {nome}")
            return True
        # Gli handler Vercel sono BaseHTTPRequestHandler: riusiamo la connessione
        # gia' aperta invece di istanziarli, che farebbe rileggere la richiesta.
        finto = handler.__new__(handler)
        finto.rfile, finto.wfile = self.rfile, self.wfile
        finto.headers, finto.path, finto.command = self.headers, self.path, self.command
        finto.request_version, finto.client_address = self.request_version, self.client_address
        finto.server, finto.connection = self.server, self.connection
        finto.requestline = self.requestline
        getattr(finto, f"do_{metodo}")()
        return True

    def do_POST(self):
        if not self._delega("POST"):
            self.send_error(405)

    def do_GET(self):
        if not self._delega("GET"):
            super().do_GET()

    def log_message(self, formato, *args):
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")


def main(porta: int = 8000):
    import os
    if not os.getenv("GOOGLE_API_KEY"):
        print("Attenzione: GOOGLE_API_KEY non impostata, le analisi falliranno.")
    print(f"http://localhost:{porta}  (Ctrl+C per fermare)")
    HTTPServer(("127.0.0.1", porta), partial(Instradatore)).serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
