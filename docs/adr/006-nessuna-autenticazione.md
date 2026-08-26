# ADR-006: Nessuna autenticazione sull'app pubblica

**Data:** 2026-08-26
**Stato:** Approvato

---

## Contesto

La versione online ha avuto fin dall'inizio una password condivisa: una variabile
`SPEED_PASSWORD` sul server, un campo nella pagina, il valore rispedito a ogni
chiamata di `/api/analizza` e `/api/report`.

Non era un sistema di identita': una sola parola uguale per tutti, senza account,
senza revoca, senza tracciamento di chi la usa. Serviva a una cosa sola — che il
link, se girava, non venisse aperto da chiunque — e ne costava tre: un campo in
cima al modulo, un segreto da distribuire a mano a ogni collega, e una modalita'
in piu' da tenere in piedi nel codice e nei test.

## Problema

Vale la pena di tenere una password condivisa per proteggere una quota?

## Opzioni valutate

| Opzione | Pro | Contro |
|---------|-----|--------|
| **Password condivisa nell'app** | argina il link che gira | non e' autenticazione: nessun account, nessuna revoca; un campo in cima al modulo per tutti; il segreto va distribuito e prima o poi finisce in una chat |
| **Nessuna autenticazione** | il tool si apre e si usa; niente segreti da distribuire; meno codice e meno stati | chiunque abbia il link consuma la quota Google di chi ospita |
| **Protezione davanti all'app** (Deployment Protection di Vercel) | vera autenticazione, con account e revoca; zero codice | si configura sulla piattaforma, non nel repo |

## Decisione

Nessuna autenticazione dentro l'app. Se in futuro serve una barriera, si mette
**davanti** — Deployment Protection di Vercel — dove esistono account e revoca, e
non dentro, dove esisterebbe solo una parola condivisa.

Il server ignora `SPEED_PASSWORD` anche se la variabile e' rimasta impostata da un
deploy precedente: una variabile dimenticata non deve chiudere fuori nessuno.

## Conseguenze

- Chiunque abbia il link analizza, e ogni analisi consuma le 25.000 richieste PSI
  giornaliere del progetto Google di chi ospita l'app.
- Il limite di 40 analisi all'ora per indirizzo resta **l'unico freno lato
  applicazione**, e l'ADR-003 ha gia' dichiarato che vive nella memoria della
  singola istanza: argina un abuso da una sola sorgente su un'istanza calda, non
  uno distribuito. Rimossa la password, quel limite diventa il solo, e questo ne
  alza il prezzo.
- `/api/stato` non dichiara piu' la lunghezza della chiave Google: l'endpoint e'
  aperto come il resto, e la lunghezza la direbbe a chiunque. Per il caso che
  serviva a diagnosticare — un incollaggio troncato — basta reincollare la
  variabile.

## Come si ribalta

Se il link finisce fuori dal gruppo di lavoro, o se la quota Google comincia a
essere consumata da traffico non riconosciuto. Il rimedio non e' rimettere una
password nel codice: e' accendere la protezione della piattaforma.
