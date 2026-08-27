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
45-165 secondi — due giri di PageSpeed quando le fasi LCP non arrivano dal campo, che
è il caso frequente — senza code né database.

Il tetto è `maxDuration`, 300 secondi: oltre quello Vercel uccide la funzione e
restituisce un 504 anonimo, cioè l'utente perde l'errore con rimedio che il tool
avrebbe consegnato. Perciò il percorso web dichiara un **budget di tempo esplicito**
(`web.Budget`) e lo passa ai client: timeout più corti e meno tentativi della CLI, con
il caso peggiore a 249 secondi. La CLI non ha limiti di durata e tiene i valori
generosi. `Budget.peggior_caso()` fa il conto, e un test lo confronta con `vercel.json`.

```
app.py               applicazione WSGI: instrada tutto, nessuna dipendenza
speed/web.py         la logica, testabile senza alzare un server
public/index.html    interfaccia
```

Vercel tratta il progetto come applicazione Python — c'è un `pyproject.toml` — e in
quella modalità manda **tutte** le richieste a un unico entrypoint, dichiarato in
`[tool.vercel]`. Non esiste l'instradamento file-per-file di `api/`: le due cose non
convivono. Per provarla in locale, `python scripts/serve_locale.py` serve la stessa
identica app.

Una sola variabile d'ambiente sul progetto Vercel: `GOOGLE_API_KEY`, che resta lato
server e non passa mai dal browser.

L'app **non ha autenticazione**: chiunque abbia il link analizza, e ogni analisi
consuma la quota Google di chi la ospita (25.000 richieste PSI al giorno). L'unico
freno lato applicazione è il limite di 40 analisi all'ora per indirizzo, che vive
nella memoria della singola istanza e quindi argina un abuso da una sola sorgente,
non uno distribuito. Se serve una barriera vera, si mette **davanti** all'app —
Deployment Protection di Vercel — non nel codice.

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
python -m speed run          clienti/cliente.yaml --formato nota    # nota per lo sviluppo
python -m speed run          clienti/cliente.yaml --formato tutti   # tutti e quattro
python -m speed run          clienti/cliente.yaml --ripetizioni 5
python -m speed report       "out/dati velocita 20082026.json"   # rigenera i report
python -m speed report --formato md "out/dati velocita 20082026.json"
```

Il report esce in **HTML e Word**, dallo stesso run: `--formato html|docx|entrambi`
(default: entrambi). Il DOCX e' pensato per la consegna al cliente ed e' modificabile;
l'HTML si stampa in PDF con Ctrl+P, il CSS ha gia' le interruzioni di pagina per template.

Ci sono altri due formati, che non sono il report al cliente in un'altra veste ma
documenti con un altro lettore: `nota`, la [nota tecnica per lo
sviluppo](#nota-tecnica-per-lo-sviluppo) che si consegna, e `md`, il [riferimento
completo](#documento-tecnico-per-gli-sviluppatori) per ticket e PR. `--formato tutti`
emette tutti e quattro; `entrambi` resta HTML+Word, che è quello che significava prima.

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

## Cosa mostra la pagina

**Per ogni URL: i Core Web Vitals reali con l'andamento e il peso della pagina.**
Restano per template perche' sono numeri diversi per pagina, ed e' tutto il motivo
per cui si misurano i template invece del solo dominio.

**Gli interventi stanno invece in una lista sola per il sito.** Misurato su una
scansione reale a tre template: 10 interventi su 13 comparivano su tutti e tre,
cioe' 20 schede su 37 erano ripetizioni dello stesso titolo. I file su cui agire
pero' quasi non coincidono — dal 43% allo 0% di sovrapposizione, perche' il codice
e' splittato per rotta e le immagini sono contenuto della pagina.

Quindi il titolo si dice una volta, e i bersagli si raggruppano per template. I
file presenti su **tutti** i template si isolano in cima: sono il bundle condiviso,
e sistemarli una volta vale per tutto il sito, mentre gli altri sono lavoro per
pagina. Su un run reale le schede passano da 36 a 15.

Ogni intervento dice tre cose e basta:

- **cosa fare** — il titolo di Lighthouse, che e' gia' un'istruzione;
- **su cosa** — i file, i selettori DOM col percorso, o i vendor. Su una pagina
  reale sono nominati per tutti e quattordici gli interventi;
- **quanto vale** — i millisecondi che Lighthouse stima di risparmiare.

Sul terzo punto vale una precisazione, perche' e' un limite del dato e non del
tool: **Lighthouse dichiara un tempo solo per una parte degli interventi** — su
quattordici di una pagina reale erano sei. Per altri da' un peso in KB. Per i
restanti non da' niente, e li' non compare nessun numero: convertire byte in
secondi con una regola nostra sarebbe inventare. Ed e' comunque una stima di
laboratorio, in millisecondi simulati: non il tempo che gli utenti recuperano.

Tutto il resto — evidenza, provenienza del testo, note metodologiche — sta dietro
un «perche'» richiudibile. Serve a difendere il dato davanti a un cliente, non a
decidere cosa fare. I primi cinque interventi sono visibili, gli altri dietro un
bottone: sotto il quinto nessuno agisce subito.

## Nota tecnica per lo sviluppo

    python -m speed run clienti/x.yaml --formato nota
    python -m speed report --formato nota "out/dati velocita 21082026.json"

Scrive `Interventi Performance <ddmmyyyy>.docx`. È **il documento che si consegna**:
poche pagine, i problemi accorpati per tema e ordinati, la citazione di PageSpeed e
il rimando alla documentazione Google per ognuno. Esempio committato:
[`docs/esempio-interventi-performance.docx`](docs/esempio-interventi-performance.docx).

La differenza dal riferimento completo non è di formattazione ma di contenuto:

| | Nota (`--formato nota`) | Riferimento (`--formato md`) |
|---|---|---|
| Voci | ~8 temi | ~15 audit per template |
| Raggruppa | per tema, attraverso i template | per template |
| Liste | i primi bersagli per tema | complete, senza tetti |
| Serve a | decidere cosa mettere a piano | aprire i file e lavorare |

**Cosa decide il tool da solo**, e come:

- **L'accorpamento per tema** — `unused-javascript`, `third-parties` e la catena di
  richieste sono lo stesso lavoro per chi lo deve fare. La mappa `TEMI` in
  `core/nota.py` è enumerata: ogni voce dice quali audit raccoglie.
- **Il valore di un tema** è il **massimo**, non la somma: `bootup-time` attribuisce
  agli script il lavoro che `mainthread-work` ripartisce per categoria, e sommarli
  lo conterebbe due volte. Per questo il titolo dice «fino a».
- **`BLOCCANTE`** è una soglia dichiarata — tre volte il valore accettabile, o
  cinque megabyte su una pagina — non un giudizio.
- **Le frasi di sintesi** vengono da `REGOLE_SINTESI`: condizione sui numeri e
  modello. Compaiono se e solo se i dati le rendono vere.

**Laboratorio e campo.** Il quadro di sintesi porta le metriche di laboratorio,
perché sono le uniche che esistono ovunque — staging compreso — e dove CrUX ha dati
aggiunge le colonne reali accanto. L'escalation a `BLOCCANTE` sulle metriche invece
scatta **solo quando il campo manca**: con i dati di campo disponibili decide il
campo (ADR-001), e dichiarare bloccante un LCP che in laboratorio è 10 s e sugli
utenti reali è 1,1 s riporterebbe la priorità al laboratorio dalla porta di
servizio. Il documento dichiara in quale delle due modalità è stato prodotto.

## Documento tecnico per gli sviluppatori

    python -m speed run clienti/x.yaml --formato tutti
    python -m speed report --formato md "out/dati velocita 21082026.json"

Scrive `Interventi tecnici <ddmmyyyy>.md` accanto agli altri report. È il terzo
deliverable, e **ha un lettore diverso**: il report HTML e il Word rispondono a «il
sito è lento, e quanto costa sistemarlo»; questo risponde a «quale file, quale riga
di configurazione, quale elemento del DOM». Markdown perché finisce in un ticket o
in una PR: si diffa, si greppa, non ha dipendenze.

C'è un esempio committato, generato dai fixture:
[`docs/esempio-interventi-tecnici.md`](docs/esempio-interventi-tecnici.md). Si
rigenera con `python scripts/esempio_md.py`, e un test verifica che sia allineato
al renderer.

Le tre differenze dal report al cliente, tutte volute:

- **Le liste sono complete.** Le schede del cliente si fermano a sei risorse per
  audit: bastano a decidere, non a lavorare. Qui `cache-insight` porta i suoi 24
  file e `script-treemap-data` i suoi 83. Le liste lunghe stanno dentro un
  `<details>`, non vengono tagliate.
- **Si raggruppa per template, non per sito.** Il report cliente fa una lista sola
  perché su tre template 20 schede su 37 erano ripetizioni dello stesso titolo. Ma
  i *file* su cui agire quasi non coincidono — dal 43% allo 0% di sovrapposizione,
  misurato — e chi sviluppa lavora per rotta. Le due scelte sono giuste entrambe,
  per lettori diversi.
- **C'è la chiave dell'audit**, `cache-insight` e non solo «Utilizza durate della
  memorizzazione nella cache efficienti»: serve a rilanciare Lighthouse e a cercare
  nei changelog quando un audit cambia nome.

Vale ADR-004 come altrove, e più che altrove: nessuna raccomandazione scritta da
noi. I link alla documentazione sono quelli che Lighthouse mette nella descrizione,
e dove non ce n'è uno — `script-treemap-data` — non se ne cerca un sostituto.
Le classificazioni nostre (chi interviene, priorità, azionabilità) sono marcate come
tali riga per riga. Gli audit non azionabili e gli artefatti di dati non spariscono:
compaiono col motivo per cui nessuno li ha assegnati.

**Solo da riga di comando, in questa versione.** La versione web non può generarlo:
`web.fatti_essenziali` scarta le opportunità complete per stare nel limite di 4,5 MB
del corpo di una richiesta Vercel, e portarle al browser costerebbe 59 KB per pagina
contro i 37 attuali — a 40 pagine si passerebbe da 1,5 a 3,8 MB, cioè quasi tutto il
margine. Troncarle per farcele stare sarebbe l'opposto di questa feature. Un run
salvato dalla versione web produce comunque il documento, che però dichiara in testa
alla sezione interventi di essere incompleto.

## Master plan: il frammento per l'xlsx

    python -m speed masterplan "out/dati velocita 21082026.json"

Scrive `masterplan.json` accanto al JSON di scansione. **Il consumatore e' esterno
a questo repo**: e' lo script che impagina l'xlsx dell'audit tecnico. Qui non si
scrive nessun xlsx — se un giorno servisse autonomo, `openpyxl` sta in
`[project.optional-dependencies]` e va importata lazy, mai in `requirements.txt`,
da cui installa Vercel.

```json
{
  "masterplan": [
    {"id": 1, "problema": "LCP: risorsa scoperta tardi su 6 template su 9",
     "priorita": "Alta",
     "evidenza": "LCP p75 4.180 ms. Attesa prima del download 61% del tempo LCP.",
     "intervento": "Deve essere applicata fetchpriority=high",
     "fonte_intervento": "lighthouse",
     "tab": "URL - LCP oltre soglia"}
  ],
  "tab": [
    {"nome": "URL - LCP oltre soglia",
     "intestazioni": ["Template", "URL", "LCP p75"],
     "larghezze": [24, 74, 14],
     "righe": [["Home", "https://…", "4.180 ms"]]}
  ]
}
```

Le regole che governano il contenuto:

- **Si aggrega per sito**, non per template: una riga per tipo di intervento, con
  quanti template ne sono toccati. N template per M problemi darebbero centinaia di
  righe che nessuno legge.
- **Ogni riga ha un intervento eseguibile.** Le righe non azionabili, le
  constatazioni e gli artefatti di dati restano fuori, e il motivo compare a
  terminale come «fuori master plan».
- **`problema`** e' una classificazione nostra nella forma «X su Y».
  **`evidenza`** sono numeri misurati. **`intervento`** e' testo di Lighthouse
  verbatim — il titolo, o l'etichetta del link quando il titolo e' un sostantivo
  ("Terze parti" -> "Riduci e posticipa il caricamento del codice di terze parti").
  Fanno eccezione i pochi audit il cui titolo localizzato non e' un'istruzione e
  la cui descrizione non ne offre una — "Carattere visualizzato" per `font-display`,
  "JavaScript precedente" per il *legacy JavaScript*: li' l'istruzione la scriviamo
  noi, da una tabella enumerata per audit, e la riga lo dichiara in
  **`fonte_intervento`** (`lighthouse` | `nostra`). Vedi ADR-004.
- **Registro telegrafico**: niente conseguenze, niente metodo o data, niente
  confronto con misure precedenti, niente elenco di pagine quando c'e' gia' un tab.
  Un numero che da solo non dice cosa misura viene qualificato con l'etichetta del
  problema — "1,7 s" diventa "Tempo di esecuzione JavaScript 1,7 s" — e l'evidenza
  dell'LCP conserva il nome della fase, che e' tutto il contenuto della riga.
- **Un tab si crea solo se la lista serve a chi implementa**, con un tetto di cinque.
  Il crawl completo e le liste informative non sono tab.

## Confronto fra due scansioni

    python -m speed confronta "out/dati velocita 20062026.json"                               "out/dati velocita 21082026.json"

Per ogni template: quali problemi sono spariti, quali sono comparsi, quali
restano, e come si e' mosso il p75 di campo. Esce a terminale e come
`confronto.html` accanto alla scansione piu' recente.

Due avvertenze compaiono nell'output, non solo nel codice:

- **il campo e' una media mobile a 28 giorni**: un intervento pubblicato oggi si
  legge pulito solo dopo quattro settimane;
- **i problemi confrontati vengono dal laboratorio, che oscilla fra run**: la
  comparsa o la scomparsa di una singola opportunita' non e' di per se' un
  risultato. Il movimento del p75 di campo si'.

Quanto conti la seconda avvertenza si vede provando: due scansioni della stessa
pagina a poche ore di distanza danno metriche di campo **identiche** — e' la stessa
finestra di 28 giorni — mentre tre problemi compaiono o spariscono. Sono rumore.

Il confronto si regge sugli URL e non sui nomi dei template, che possono cambiare
fra una scansione e l'altra. E non richiede di accumulare nulla: CrUX History
restituisce 40 settimane a ogni esecuzione, quindi l'andamento lungo sta gia'
dentro ciascuna delle due scansioni.

## Decisioni architetturali

Sei decisioni non si cambiano senza aggiornare l'ADR corrispondente in
`docs/adr/`. Sono citate dai docstring dei moduli che le applicano.

| # | Decisione |
|---|-----------|
| 1 | Il campo e' la metrica, il laboratorio la diagnosi; il punteggio PSI non entra in nessuna valutazione |
| 2 | Il campo si legge da CrUX API, non da `loadingExperience` di PSI |
| 3 | Nessun database: lo storico arriva da CrUX History a ogni esecuzione |
| 4 | Il testo delle raccomandazioni viene da Lighthouse verbatim, il tool non ne scrive |
| 5 | La ripartizione dell'LCP si prende dal campo, il laboratorio e' il ripiego |
| 6 | Nessuna autenticazione nell'app: se serve una barriera si mette davanti, non nel codice |

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
