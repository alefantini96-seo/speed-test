# ADR-002: Il campo si legge da CrUX API, non da `loadingExperience` di PSI

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato

---

## Contesto

I dati di campo sono disponibili in due modi: dentro la risposta di PageSpeed
Insights, nel blocco `loadingExperience`, oppure chiamando direttamente CrUX API.
La prima strada e' gratis in termini di chiamate — arriva insieme al laboratorio,
senza una richiesta in piu'.

Nella documentazione di PSI, Google dichiara: *"We plan to discontinue including
real-world data from the Chrome User Experience Report in this API"*, e rimanda
a CrUX API e CrUX History API.

## Problema

Prendere il campo dalla risposta PSI che gia' abbiamo, o pagare una chiamata in
piu' a CrUX API?

## Opzioni valutate

| Opzione | Pro | Contro |
|---------|-----|--------|
| **`loadingExperience` di PSI** | nessuna chiamata aggiuntiva, nessuna seconda API da abilitare | dichiarata in dismissione; nessuno storico |
| **CrUX API + History API** | fonte stabile, e History restituisce 40 settimane a ogni chiamata | una API in piu' da abilitare sul progetto Google, e una chiamata in piu' per pagina |

## Decisione

Il campo si legge da CrUX API. `loadingExperience` viene ancora estratto dalla
risposta PSI ma non alimenta nessuna valutazione: se Google lo rimuove, non si
rompe niente.

La conseguenza che ha deciso: **CrUX History restituisce 40 settimane di storico a
ogni chiamata**. Significa che il tool non deve accumulare niente nel tempo — anche
la prima scansione contiene gia' dieci mesi di andamento. E' cio' che rende
possibile l'ADR-003.

## Conseguenze

- Servono due API abilitate sullo stesso progetto Google Cloud, e se la chiave ha
  restrizioni vanno aggiunte a entrambe. E' il passaggio in cui si perde piu' tempo
  in fase di installazione, e la guida lo mette in evidenza.
- Le finestre CrUX sono medie mobili a 28 giorni: un intervento messo online oggi
  entra nei numeri gradualmente e si legge pulito solo dopo quattro settimane. Il
  report lo dichiara in testa.
- Lo storico e' un di piu': se manca, degrada solo se stesso e le metriche correnti
  restano.

## Come si ribalta

Se Google dismettesse CrUX API invece di `loadingExperience`, o introducesse un
costo per chiamata.
