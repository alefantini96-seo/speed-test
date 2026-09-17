"""
Errori con un rimedio dentro.

Il tool finisce in mano a chi non lo ha scritto: un traceback non dice cosa fare.
Ogni errore previsto qui porta con se' l'azione che lo risolve.
"""
from __future__ import annotations

import re


class ErroreSpeed(Exception):
    """Errore atteso, con rimedio. La CLI lo stampa senza traceback."""

    def __init__(self, messaggio: str, rimedio: str = ""):
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.rimedio = rimedio

    def __str__(self) -> str:
        return self.messaggio if not self.rimedio else f"{self.messaggio}\n\n{self.rimedio}"


def da_risposta_google(servizio: str, codice, messaggio: str, url: str = "") -> ErroreSpeed:
    """Traduce un errore delle API Google in qualcosa su cui si puo' agire."""
    testo = (messaggio or "").lower()
    dove = f" su {url}" if url else ""

    if codice == 400 and "api key not valid" in testo:
        return ErroreSpeed(
            f"{servizio}: la chiave API non e' valida.",
            "Controlla GOOGLE_API_KEY nel file .env. La chiave si crea su\n"
            "console.cloud.google.com -> API e servizi -> Credenziali.")

    if codice == 403 and "has not been used" in testo:
        return ErroreSpeed(
            f"{servizio}: l'API non e' abilitata sul progetto Google Cloud.",
            "Servono ENTRAMBE le API, abilitate sullo stesso progetto:\n"
            "  - PageSpeed Insights API\n"
            "  - Chrome UX Report API\n"
            "Dopo averle abilitate aspetta un paio di minuti: la propagazione non e' immediata.")

    if codice == 403 and "blocked" in testo:
        return ErroreSpeed(
            f"{servizio}: la chiave e' ristretta e non include questa API.",
            "Credenziali -> la tua chiave -> Restrizioni API: aggiungi sia\n"
            "PageSpeed Insights API sia Chrome UX Report API.\n"
            "Abilitare l'API sul progetto non basta se la chiave ha restrizioni.")

    if codice == 429:
        return ErroreSpeed(
            f"{servizio}: quota esaurita.",
            "I limiti sono 25.000 richieste al giorno per PageSpeed Insights e\n"
            "150 al minuto per CrUX. Riprova fra qualche minuto, oppure riduci\n"
            "--ripetizioni o il numero di template.")

    if codice in (400, 500) and ("unable to process" in testo or "lighthouse" in testo):
        # Il codice di Lighthouse, quando c'e': ERRORED_DOCUMENT_REQUEST, NO_FCP,
        # FAILED_DOCUMENT_REQUEST... dice molto piu' di "non e' riuscito", e
        # cercarlo nei changelog e' il primo passo per capire un fallimento che
        # si ripete.
        sigla = re.search(r"\b([A-Z][A-Z_]{6,})\b", messaggio or "")
        dettaglio = sigla.group(1) if sigla else (messaggio or "").strip()[:120]
        return ErroreSpeed(
            f"{servizio} non e' riuscito a misurare la pagina{dove}"
            + (f": {dettaglio}." if dettaglio else "."),
            "Capita anche su pagine perfettamente raggiungibili: e' il run di\n"
            "Lighthouse ad essere andato male, non la pagina. Misurato su una URL\n"
            "che aveva appena fallito: sei chiamate su sei riuscite pochi minuti\n"
            "dopo. Riprova questa pagina.\n"
            "Se invece fallisce sempre, allora controlla che l'URL risponda 200\n"
            "senza login: PSI non vede staging ne' ambienti protetti da password.")

    return ErroreSpeed(f"{servizio} ha risposto {codice}: {messaggio[:200]}")


# Il rimedio dipende da cosa stava facendo il servizio. PageSpeed **misura** la
# pagina, e una pagina pesante puo' semplicemente metterci troppo; CrUX **legge**
# dati gia' raccolti, e se non risponde e' la rete. Dire a chi aspetta CrUX di
# passare alla riga di comando "perche' la pagina e' lenta" sarebbe un consiglio
# sbagliato con l'aria di essere giusto.
RIMEDIO_ATTESA = {
    "PageSpeed Insights":
        "La misurazione di una pagina pesante puo' superare il tempo che la\n"
        "versione online puo' aspettare. Riprova questa pagina: la seconda volta\n"
        "e' spesso piu' rapida, perche' Google serve dalla cache le richieste\n"
        "ravvicinate. Se fallisce ancora, la riga di comando non ha limiti di durata.",
    "Chrome UX Report":
        "Non e' una misurazione ma una lettura: di norma risponde in un paio di\n"
        "secondi, quindi e' quasi sempre un intoppo di rete. Riprova la pagina.",
}

RIMEDIO_ATTESA_GENERICO = "Riprova fra un minuto."


def da_attesa_scaduta(servizio: str, secondi: float, url: str = "") -> ErroreSpeed:
    """Il servizio non ha risposto in tempo.

    Non e' un dettaglio di implementazione: e' il modo in cui la versione online
    fallisce piu' spesso, perche' una misurazione di laboratorio dura 30-60
    secondi e ogni tanto di piu'. Va detto con parole sue, altrimenti diventa
    quello che era: "Errore 502", che e' uno status e non una causa.
    """
    dove = f" su {url}" if url else ""
    return ErroreSpeed(
        f"{servizio} non ha risposto entro {secondi:.0f} secondi{dove}.",
        RIMEDIO_ATTESA.get(servizio, RIMEDIO_ATTESA_GENERICO))


def da_rete(servizio: str, eccezione, url: str = "") -> ErroreSpeed:
    """Rete caduta fra noi e Google: non e' un problema della pagina analizzata.

    Il nome della classe e' l'unica cosa che alcune eccezioni di httpx portano:
    `ReadTimeout` e compagne hanno il messaggio vuoto.
    """
    dettaglio = str(eccezione).strip() or type(eccezione).__name__
    dove = f" su {url}" if url else ""
    return ErroreSpeed(
        f"{servizio} non e' raggiungibile{dove}: {dettaglio[:120]}.",
        "E' la rete fra il server e Google, non la pagina analizzata.\n"
        "Riprova fra un minuto.")


def configurazione(messaggio: str, rimedio: str = "") -> ErroreSpeed:
    return ErroreSpeed(f"Configurazione: {messaggio}", rimedio)
