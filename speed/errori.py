"""
Errori con un rimedio dentro.

Il tool finisce in mano a chi non lo ha scritto: un traceback non dice cosa fare.
Ogni errore previsto qui porta con se' l'azione che lo risolve.
"""
from __future__ import annotations


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
        return ErroreSpeed(
            f"{servizio}: non e' riuscito ad analizzare la pagina{dove}.",
            "Verifica che l'URL sia raggiungibile pubblicamente e risponda 200.\n"
            "PSI non vede staging, ambienti protetti da password o pagine dietro login.")

    return ErroreSpeed(f"{servizio} ha risposto {codice}: {messaggio[:200]}")


def configurazione(messaggio: str, rimedio: str = "") -> ErroreSpeed:
    return ErroreSpeed(f"Configurazione: {messaggio}", rimedio)
