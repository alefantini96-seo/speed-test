# ADR-001: Il campo e' la metrica, il laboratorio e' la diagnosi

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato

---

## Contesto

PageSpeed Insights restituisce due dataset in una sola risposta: i risultati di
Lighthouse, misurati in laboratorio su una simulazione, e i dati di campo di CrUX,
raccolti da utenti reali. Il tool doveva scegliere su quale dei due poggiare.

Misurato: la stessa pagina, misurata due volte a novanta secondi di distanza, ha
dato `resourceLoadDelay` fra 260 e 3.118 ms. Il punteggio Lighthouse varia in modo
comparabile. Lighthouse gira inoltre dai server Google, quindi il suo TTFB non
rappresenta gli utenti del sito: su una pagina italiana il lab riportava 10 ms
contro 403 ms misurati sul campo.

## Problema

Quale delle due fonti dice se il sito e' lento, e quale dice perche'?

## Opzioni valutate

| Opzione | Pro | Contro |
|---------|-----|--------|
| **Solo laboratorio** | disponibile su ogni URL, anche senza traffico | instabile fra misurazioni, geograficamente non rappresentativo, nessuno storico |
| **Solo campo** | e' cio' che gli utenti subiscono davvero | non dice mai *perche'*, e manca sotto una certa soglia di traffico |
| **Campo come metrica, lab come diagnosi** | ciascuna fonte usata per cio' che sa fare | va dichiarato in ogni riga del report quale delle due sta parlando |

## Decisione

Il campo e' la metrica: dice se il sito e' lento e se sta peggiorando. Il
laboratorio e' la diagnosi: dice quale elemento, quale file, quale fase.

Conseguenza operativa: **il punteggio PSI non entra in nessuna valutazione**.
Varia fra due misurazioni identiche, quindi non e' un dato su cui basare un
giudizio. Compare una sola volta in fondo al report, dichiarato come riferimento,
perche' e' il numero che il cliente vede aprendo pagespeed.web.dev e va spiegato
prima che lo chieda.

## Conseguenze

- Nessun numero di laboratorio va in serie storica.
- Le pagine senza dati di campo hanno solo la diagnosi, e il report lo dichiara
  invece di stimare dal dato di origin.
- La priorita' degli interventi si calibra sul campo: un'opportunita' che punta a
  una metrica gia' buona per gli utenti reali scende in fondo, anche quando
  Lighthouse le attribuisce il risparmio piu' alto.
- Serve una via d'uscita per i casi in cui il campo manca: e' l'ADR-005.

## Come si ribalta

Se Google rendesse i risultati di laboratorio deterministici, o se CrUX smettesse
di esporre i dati a livello di URL rendendo il campo inutilizzabile per pagina.
