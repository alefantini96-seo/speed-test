"""
Cio' che le chiamate alle API Google hanno in comune.

Le tre protezioni che servivano a PageSpeed Insights servono identiche a CrUX, e
per un motivo piu' serio: CrUX e' **la metrica** (ADR-001). Se una chiamata cade,
il report perde campo e storico e ogni priorita' ricade su "media" senza che
nessuno lo dica.

Le tre:

1. **il corpo puo' non essere JSON.** Un 502 del gateway o una pagina di quota
   tornano HTML, e `.json()` alla cieca esplode in JSONDecodeError, che non dice
   niente a chi legge;
2. **lo status va guardato.** Un 403 puo' portare un corpo che JSON e' ma errore
   non lo dichiara;
3. **i codici transitori vanno riprovati.** Sono transitori: su venti template
   una risposta persa e' un buco silenzioso nel report.

Nessuna rete qui dentro: si riceve una funzione che la richiesta la fa.
"""
from __future__ import annotations

import asyncio

# Codici su cui vale la pena riprovare: sono transitori. PSI risponde "Unable to
# process" con regolarita', e su venti template una risposta persa e' un buco
# silenzioso nel report — un template che non compare, senza che nessuno lo noti.
CODICI_RIPROVABILI = (429, 500, 502, 503, 504)


def json_sicuro(risposta) -> dict | None:
    """Il corpo come dizionario, o None se non e' JSON.

    Un 502 del gateway o una pagina di quota tornano HTML: chiamare `.json()`
    alla cieca faceva esplodere JSONDecodeError, che non dice niente a nessuno.
    """
    try:
        dati = risposta.json()
    except ValueError:
        return None
    return dati if isinstance(dati, dict) else None


async def richiedi(esegui, tentativi: int = 3, attesa_iniziale: float = 2.0) -> tuple:
    """(risposta, corpo JSON o None), riprovando sui codici transitori.

    `esegui` e' una funzione senza argomenti che ritorna la coroutine della
    richiesta. Chi chiama decide cosa farne: la mappatura degli errori e' diversa
    fra i due servizi — il 404 di CrUX significa "questa URL non ha dati di
    campo", che e' un esito legittimo e non un errore.
    """
    risposta = None
    for tentativo in range(1, tentativi + 1):
        risposta = await esegui()
        if risposta.status_code not in CODICI_RIPROVABILI or tentativo == tentativi:
            break
        # Backoff esponenziale: 2s, 4s. Su 429 riprovare subito peggiora le cose.
        await asyncio.sleep(attesa_iniziale * 2 ** (tentativo - 1))
    return risposta, json_sicuro(risposta)
