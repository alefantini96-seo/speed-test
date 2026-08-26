"""
Server locale: la stessa app WSGI che gira su Vercel, servita da wsgiref.

Esiste per provare la versione web senza fare un deploy a ogni modifica. Non c'e'
nessuna simulazione dell'instradamento: Vercel manda tutte le richieste all'app,
e qui succede lo stesso, quindi cio' che funziona in locale funziona online.

    python scripts/serve_locale.py           # http://localhost:8000
    python scripts/serve_locale.py 8765      # su un'altra porta

Legge .env dalla radice del progetto, come la CLI.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RADICE / ".env")

from app import app  # noqa: E402


def main(porta: int = 8000):
    if not os.getenv("GOOGLE_API_KEY"):
        print("Attenzione: GOOGLE_API_KEY non impostata, le analisi falliranno.")
    print(f"http://localhost:{porta}  (Ctrl+C per fermare)")
    with make_server("127.0.0.1", porta, app) as server:
        server.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
