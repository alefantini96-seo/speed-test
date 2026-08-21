# speed-audit

Analisi una tantum della velocità dei template principali di un sito, con diagnosi
e interventi assegnabili. Gira in locale, non ha database, non ha niente da schedulare.

## Come funziona

Due fonti, con due ruoli distinti che non vanno mescolati:

| Fonte | Cosa dà | Come si usa |
|---|---|---|
| **CrUX API + History** | p75 degli utenti reali, 40 settimane di storico | è **la metrica**: dice se il sito è lento e se sta peggiorando |
| **PageSpeed Insights** | elemento LCP, fasi, peso, risorse bloccanti, **e il testo delle raccomandazioni** | è **la diagnosi**: dice perché. Il punteggio non viene usato |

Il punteggio PSI non entra in nessuna valutazione: varia fra due misurazioni identiche.
Compare solo in fondo al report come riferimento, perché è il numero che il cliente
vede aprendo pagespeed.web.dev.

## Il tool non scrive raccomandazioni

Ogni riga del report è tracciabile a una di tre origini, dichiarata nel report stesso:

1. **Testo di Lighthouse** — titoli, descrizioni e checklist arrivano da PSI con
   `locale=it`, già in italiano e con i link alla documentazione Google. Vanno nel
   report verbatim, insieme ai file che causano il problema e ai byte o millisecondi
   sprecati per ciascuno.
2. **Dati misurati** — p75 di campo, storico, peso, ripartizione delle fasi.
3. **Tre classificazioni nostre**, tutte derivate da dati e dichiarate come tali:
   - **chi interviene**, dalla quota di spreco su risorse di terze parti: se il 90%
     del JavaScript inutilizzato sta su script altrui, non è un lavoro da sviluppo;
   - **quanto è prioritario**, dal campo e non dal laboratorio. Lighthouse ordina per
     risparmio stimato in lab; il tool riordina su ciò che gli utenti reali subiscono,
     e un'opportunità che punta a una metrica di campo già buona scende in fondo;
   - **se è azionabile**: un intervento di cache i cui file sono tutti di terze parti
     non è nelle vostre mani, e il report lo marca invece di metterlo in lista.

## Da dove viene la ripartizione dell'LCP

La fase in cui si perde il tempo decide **chi deve intervenire**, quindi conta da dove
la si prende.

**Prima scelta: il campo.** CrUX espone le quattro fasi misurate sugli utenti reali
(`largest_contentful_paint_image_*`), con lo storico a 40 settimane. Sono stabili, e
comprendono un TTFB realistico — cosa che il laboratorio non può dare, girando dai
server Google.

**Ripiego: il laboratorio**, quando CrUX non le espone: le fornisce solo con elemento
LCP immagine e traffico sufficiente. Lì il dato oscilla parecchio — sulla stessa pagina
`resourceLoadDelay` è passato da 260 a 3.118 ms fra misurazioni — quindi il tool ne fa
più d'una, riporta la mediana e dichiara quante concordano. Se non concordano lo scrive,
invece di scegliere.

Il numero di misurazioni è deciso dal tool: **una** se le fasi arrivano dal campo, **tre**
altrimenti. `--ripetizioni` lo forza a mano. Attenzione: PSI serve dalla cache le chiamate
ravvicinate — tre risposte identiche non sono tre misurazioni, e il tool le deduplica per
`analysisUTCTimestamp` invece di contarle.

L'elemento LCP e la checklist di scopribilità sono invece stabili in ogni caso: sono
proprietà dell'HTML, non della rete.

## Versione online

Oltre alla CLI c'è un'interfaccia web pensata per Vercel: incolli gli URL, il browser
li manda **uno alla volta** e i risultati compaiono mano a mano. Una pagina richiede
~20-60 secondi, quindi sta dentro i 300 secondi di una funzione Vercel anche sul piano
gratuito, senza code né database.

```
public/index.html    interfaccia
api/analizza.py      POST {url, password} -> analisi di una singola pagina
api/report.py        POST {pagine}         -> report Word da scaricare
```

Due variabili d'ambiente sul progetto Vercel: `GOOGLE_API_KEY` (resta lato server, non
passa mai dal browser) e `SPEED_PASSWORD` (senza, chiunque abbia il link consuma la
tua quota).

Lo storico non si accumula: CrUX History restituisce dieci mesi a ogni esecuzione,
quindi anche la prima scansione contiene già l'andamento.

## Installazione

```bash
pip install -r requirements.txt
cp .env.example .env     # e compilare GOOGLE_API_KEY
```

La chiave Google serve per entrambe le API ed è gratuita. Sul progetto Google Cloud
vanno **abilitate tutte e due** — *PageSpeed Insights API* e *Chrome UX Report API* —
e se la chiave ha restrizioni, entrambe vanno aggiunte anche lì.

## Uso

```bash
python -m speed check-config clienti/cliente.yaml   # quali URL hanno dati di campo
python -m speed run          clienti/cliente.yaml   # scansione -> JSON + HTML + DOCX
python -m speed run          clienti/cliente.yaml --desktop
python -m speed run          clienti/cliente.yaml --formato docx
python -m speed run          clienti/cliente.yaml --ripetizioni 5
python -m speed report       "out/dati velocita 20082026.json"   # rigenera i report
```

Il report esce in **HTML e Word**, dallo stesso run: `--formato html|docx|entrambi`
(default: entrambi). Il DOCX e' pensato per la consegna al cliente ed e' modificabile;
l'HTML si stampa in PDF con Ctrl+P, il CSS ha gia' le interruzioni di pagina per template.

`check-config` va lanciato **prima** di fissare la lista URL: con un URL per template,
se quella pagina non ha traffico sufficiente CrUX non ha dati e resta solo la diagnosi
lab, senza metrica né storico. Dove manca, si sostituisce con la pagina più trafficata
dello stesso template.

## Configurazione

Un file YAML per cliente, un URL per template — vedi `clienti/esempio.yaml`.
`output` vuoto scrive in `./out`; altrimenti si punta alla cartella del cliente.
Il nome del cliente finisce nel nome del file **solo** quando il file non e' gia' dentro
la sua cartella, secondo la convenzione del workspace.

## Struttura

```
speed/core/     funzioni pure, nessuna I/O — qui stanno i test
  extract.py    JSON PSI -> fatti tipizzati
  diagnose.py   fatti -> problemi, con la mappa fase LCP -> intervento
  thirdparty.py aggregazione per host, first vs third party
  soglie.py     soglie Core Web Vitals
speed/io/       rete e filesystem
fixtures/       risposte reali di PSI e CrUX, base dei test
```

Le chiavi degli audit Lighthouse sono fissate su risposte reali, non sulla
documentazione: Lighthouse 13 ha sostituito i vecchi audit diagnostici con gli
"Insights" (`lcp-breakdown-insight`, `lcp-discovery-insight`). Quando cambieranno
ancora, saranno i test su `fixtures/` a segnalarlo.

## Limiti dichiarati

- **Un URL per template**: non distingue un problema del template da un problema di
  quella specifica pagina. Il report lo dichiara in testa.
- **Le fasi LCP sono proporzioni**, non millisecondi confrontabili: il breakdown è sul
  trace osservato, la metrica riportata è simulata con throttling.
- **INP non è misurabile in laboratorio**: Lighthouse dà solo TBT e long task come
  proxy. L'attribuzione è meno precisa che sull'LCP, e il report lo dice.
- **Il campo è una media mobile a 28 giorni**: un intervento messo online oggi si legge
  pulito solo dopo quattro settimane.
- **Solo URL pubblici**: PSI non raggiunge staging o pagine dietro autenticazione.
