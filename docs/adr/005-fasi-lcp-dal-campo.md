# ADR-005: La ripartizione dell'LCP si prende dal campo, il laboratorio e' il ripiego

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato

---

## Contesto

La fase in cui si perde il tempo dell'LCP — risposta del server, attesa prima del
download, download, rendering — decide **chi deve intervenire**: infrastruttura,
sviluppo o redazione. E' la classificazione con la conseguenza operativa piu'
diretta di tutto il tool.

Misurato su misurazioni indipendenti della stessa pagina:

    resourceLoadDelay:  260 ms   1204 ms   1238 ms   3118 ms

Un fattore dodici. Su tre run consecutivi la fase dominante si e' ribaltata da
"attesa pre-download 92%" a "rendering 79%": due diagnosi diverse, due squadre
diverse, sulla stessa pagina.

Poi la scoperta: CrUX espone le stesse quattro fasi misurate sugli utenti reali
(`largest_contentful_paint_image_*`), con lo storico a 40 settimane. Sulla pagina
di prova il campo indicava l'attesa pre-download al 39%, il laboratorio il
rendering al 58% — e il TTFB era 27% nel campo contro il 2% del lab, coerente con
il fatto che Lighthouse gira dai server Google.

## Problema

Da dove si prende la ripartizione dell'LCP?

## Decisione

**Prima scelta: il campo.** Quando CrUX espone tutte e quattro le fasi, si usano
quelle. Servono tutte: una ripartizione parziale darebbe una fase dominante
falsata da cio' che manca.

**Ripiego: il laboratorio**, quando il campo non le espone — le fornisce solo con
elemento LCP immagine e traffico sufficiente. In quel caso si misura piu' volte, si
riporta la mediana e si dichiara quante misurazioni concordano. Se non concordano,
il report lo scrive invece di scegliere, e il responsabile diventa "da confermare".

Il numero di misurazioni e' deciso dal tool: **una** se le fasi arrivano dal campo,
**tre** altrimenti.

## Conseguenze

- Le durate di laboratorio si leggono come **proporzioni**, mai come millisecondi
  confrontabili: il breakdown e' sul trace osservato mentre la metrica riportata e'
  simulata con throttling, e su una pagina di prova le fasi sommavano 3,4 s contro
  un LCP dichiarato di 10,9 s.
- I valori di campo sono percentili indipendenti: non sommano esattamente all'LCP
  complessivo, e va detto.
- PSI serve dalla cache le chiamate ravvicinate — tre risposte identiche non sono
  tre misurazioni. Si deduplica per `analysisUTCTimestamp` e i giri si distanziano
  nel tempo.
- L'elemento LCP e la checklist di scopribilita' sono stabili in ogni caso: sono
  proprieta' dell'HTML, non della rete.

## Domanda aperta

**Perche' tre misurazioni e non cinque?** Il numero non e' ricostruibile dal codice
ne' da una misura registrata: tre e' il minimo che permette una maggioranza, ma non
risulta che sia stata verificata la stabilita' della mediana a tre campioni su una
distribuzione cosi' dispersa. Con quattro osservazioni fra 260 e 3.118 ms, la
mediana di tre potrebbe non essere piu' informativa di una singola misurazione. Da
verificare su una pagina che manchi delle fasi di campo, che oggi non e' fra le
fixture.

## Come si ribalta

Se CrUX esponesse le fasi anche per LCP testuale e con soglie di traffico piu'
basse, il ripiego di laboratorio — e con esso tutto il modulo del consenso —
diventerebbe superfluo.
