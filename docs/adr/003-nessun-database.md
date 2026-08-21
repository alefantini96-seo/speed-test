# ADR-003: Nessun database, nessuno storico accumulato

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato

---

## Contesto

Un tool che misura la velocita' nel tempo sembra chiedere un database: si salvano
le misurazioni, si confrontano, si mostra l'andamento. E' la forma che ha quasi
ogni strumento di monitoraggio.

Ma l'ADR-002 ha stabilito che il campo viene da CrUX History, che restituisce 40
settimane a ogni chiamata. L'andamento c'e' gia', e non e' nostro: e' di Google.

## Problema

Serve conservare le misurazioni?

## Opzioni valutate

| Opzione | Pro | Contro |
|---------|-----|--------|
| **Database delle misurazioni** | confronto fra le nostre esecuzioni; annotazione dei deploy | infrastruttura da mantenere, backup, migrazioni, e uno storico che diventa utile solo dopo mesi |
| **Nessuno stato** | la prima scansione e' gia' completa di andamento; niente da amministrare | non si confrontano due nostre esecuzioni |

## Decisione

Nessun database. La scansione e' una tantum e lo storico arriva da CrUX History a
ogni esecuzione.

Il confronto fra due nostre esecuzioni si recupera a costo zero: la scansione
salva il JSON grezzo accanto al report, nella cartella del cliente. Il filesystem
fa da archivio.

## Conseguenze

- La versione online non ha coda ne' polling: si analizza **una URL per richiesta**,
  e il browser accumula i risultati. E' anche cio' che tiene ogni richiesta dentro
  i limiti di durata di una funzione serverless.
- Non c'e' nessuno stato condiviso fra le istanze. Il limite di richieste dell'app
  pubblica e' percio' per istanza calda e non globale: e' dichiarato nel codice, ed
  e' il prezzo di questa decisione.
- Nessuna annotazione automatica dei deploy: si ricava confrontando i JSON salvati.

## Come si ribalta

Se il tool passasse da uno strumento una tantum a un monitoraggio ricorrente con
allarmi, o se servisse un limite di richieste affidabile su piu' istanze.
