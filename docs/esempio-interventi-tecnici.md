# Interventi tecnici — Esempio

Sito: https://www.bbc.com  
Scansione del 2026-08-20  
Template misurati: 2 (piu' 1 non riuscita)

## Come e' stato misurato

- Laboratorio: PageSpeed Insights, strategia **mobile**, rete e CPU **simulate con throttling**.
- Lighthouse 13.4.1, benchmark index 1300 (velocita' della macchina che ha misurato: numeri diversi su macchine diverse sono attesi).
- Per template, quando e' stata misurata e su quante misurazioni di laboratorio distinte poggia la ripartizione dell'LCP:

| Template | analysisUTCTimestamp | Misurazioni lab | Campo fino al |
|---|---|---|---|
| Home | `2026-08-20T15:03:28.124Z` | 1 distinta, 1 concorde | 2026-08-18 |
| Articolo | `2026-08-20T15:04:57.074Z` | 1 distinta, 1 concorde | 2026-08-18 |

- Il p75 di campo e' CrUX: utenti reali, media mobile a 28 giorni.

### Limiti dichiarati

- Un URL per template: il documento non distingue un problema del template da un problema di quella specifica pagina.
- Le fasi LCP sono proporzioni, non millisecondi confrontabili: il breakdown e' sul trace osservato, la metrica riportata e' simulata con throttling.
- L'INP non e' misurabile in laboratorio: Lighthouse da' solo TBT e long task come proxy, e l'attribuzione e' meno precisa che sull'LCP.
- Il campo e' una media mobile a 28 giorni: un intervento messo online oggi si legge pulito solo dopo quattro settimane.
- Il punteggio PageSpeed non entra in nessuna valutazione (ADR-001): e' rumoroso e cambia fra due chiamate identiche. Sta in fondo come numero di vetrina.

## Pagine analizzate

| Template | URL | Campo | LCP p75 | INP p75 | CLS p75 | Peso | Interventi |
|---|---|---|---|---|---|---|---|
| Home | `https://www.bbc.com/` | URL | 1162 ms (buono) | 109 ms (buono) | 0.03 (buono) | 2574 KB (20% 3P) | 15 |
| Articolo | `https://www.bbc.com/news` | URL | 1162 ms (buono) | 109 ms (buono) | 0.03 (buono) | 2598 KB (21% 3P) | 15 |
| Video | `https://www.bbc.com/video` | **non riuscita** | — | — | — | — | — |

## Home

`https://www.bbc.com/`

**Elemento LCP**
- selettore: `div.Westminster-styles__MediaWrapperStyled-sc-348bb4b5-5 > div.Westminster-styles__MediaStyled-sc-348bb4b5-1 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0`
- markup: `<img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" loading="lazy" alt="A firefighter helps an old lady out a building holding her arm as they ste…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">`

**Ripartizione LCP** — origine: campo CrUX (utenti reali).

| Fase | Quota | Durata |
|---|---|---|
| Attesa prima del download | 39% | 498 ms |
| Risposta del server (TTFB) | 27% | 339 ms |
| Rendering dell'elemento | 20% | 257 ms |
| Download della risorsa | 14% | 176 ms |

**Scopribilita' della risorsa LCP** — checklist di Lighthouse.

| Esito | Controllo | Chiave |
|---|---|---|
| **fallito** | Deve essere applicata fetchpriority=high | `priorityHinted` |
| superato | La richiesta è rilevabile nel documento iniziale | `requestDiscoverable` |
| **fallito** | Le risorse LCP non devono utilizzare loading=lazy | `eagerlyLoaded` |

**Peso per tipo di risorsa** — JavaScript 1391 KB · Immagini 599 KB · Font 395 KB · HTML 99 KB · Chiamate XHR 82 KB · CSS 7 KB

**Entita' per peso**

| Entita' | Parte | Peso | Richieste |
|---|---|---|---|
| bbci.co.uk | 1P | 1927 KB | 96 |
| privacy-mgmt.com | 3P | 216 KB | 12 |
| piano | 3P | 137 KB | 1 |
| bbc.com | 1P | 122 KB | 7 |
| Optimizely | 3P | 103 KB | 4 |
| Google/Doubleclick Ads | 3P | 57 KB | 1 |
| DotMetrics | 3P | 10 KB | 4 |
| bbc.co.uk | 3P | 1 KB | 1 |

> Una sola misurazione di laboratorio distinta: la ripartizione in fasi dell'LCP varia molto fra run, quindi la fase dominante qui e' indicativa e non un risultato consolidato.

### Interventi

#### `bootup-time` — Riduci il tempo di esecuzione di JavaScript

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 850 ms su TBT.

1,7 s · risparmio dichiarato: TBT 850 ms · score 0.00

Potresti ridurre i tempi di analisi, compilazione ed esecuzione di JavaScript. A questo scopo potrebbe essere utile pubblicare payload JavaScript di dimensioni inferiori. Scopri come ridurre il tempo di esecuzione di JavaScript.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/bootup-time/)

<details>
<summary>11 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Tempo |
|---|---|---|---|
| 1 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 977 ms |
| 2 | `https://www.bbc.com/` | 1P | 480 ms |
| 3 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 172 ms |
| 4 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 141 ms |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0t7a3088d.epq.js` | 1P | 109 ms |
| 6 | `https://static.bbci.co.uk/frameworks/requirejs/0.13.0/sharedmodules/require.js` | 1P | 95 ms |
| 7 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 66 ms |
| 8 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 64 ms |
| 9 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0tvp5jqt08de_.js` | 1P | 58 ms |
| 10 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 54 ms |
| 11 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0yv_0~sh~88vc.js` | 1P | 53 ms |

</details>

#### `mainthread-work-breakdown` — Riduci al minimo il lavoro del thread principale

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 600 ms su TBT.

2,8 s · risparmio dichiarato: TBT 600 ms · score 0.00

Potresti ridurre i tempi di analisi, compilazione ed esecuzione di JavaScript. A questo scopo potrebbe essere utile pubblicare payload JavaScript di dimensioni inferiori. Scopri come minimizzare il lavoro del thread principale

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/mainthread-work-breakdown/)

| Voce | duration |
|---|---|
| `Script Evaluation` | 1743 ms |
| `Style & Layout` | 359 ms |
| `Other` | 282 ms |
| `Script Parsing & Compilation` | 246 ms |
| `Garbage Collection` | 139 ms |
| `Parse HTML & CSS` | 32 ms |
| `Rendering` | 30 ms |

#### `unused-javascript` — Riduci il codice JavaScript inutilizzato

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo + marketing/tag · guadagno stimato in lab: 1.350 ms su LCP.

Risparmio stimato di 498 KiB · risparmio dichiarato: LCP 1350 ms · score 0.00

Riduci il codice JavaScript inutilizzato e rimanda il caricamento degli script finché non sono necessari al fine di ridurre i byte consumati dall'attività di rete. Scopri come ridurre il codice JavaScript inutilizzato.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)

<details>
<summary>11 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati | Quota |
|---|---|---|---|---|---|
| 1 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 136 KB | 105 KB | 77% |
| 2 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 92 KB | 62 KB | 67% |
| 3 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 119 KB | 58 KB | 49% |
| 4 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d2lp0c_d9lc8.js` | 1P | 49 KB | 49 KB | 100% |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0uu598vg94c03.js` | 1P | 62 KB | 43 KB | 68% |
| 6 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 50 KB | 42 KB | 84% |
| 7 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 40 KB | 35 KB | 89% |
| 8 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 97 KB | 34 KB | 34% |
| 9 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0sm_sfi0c1mq-.js` | 1P | 32 KB | 25 KB | 78% |
| 10 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 58 KB | 24 KB | 41% |
| 11 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r330~rwdc1_z.js` | 1P | 49 KB | 22 KB | 44% |

</details>

#### `cache-insight` — Utilizza durate della memorizzazione nella cache efficienti

> **Classificazione nostra** — priorita' **bassa** · interviene: infrastruttura · guadagno stimato in lab: 300 ms su LCP.

Risparmio stimato di 567 KiB · risparmio dichiarato: LCP 300 ms, FCP 150 ms · score 0.00

La memorizzazione nella cache per un lungo periodo di tempo può velocizzare le visite abituali alla tua pagina. Scopri di più sulla memorizzazione nella cache.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/cache)

<details>
<summary>24 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati |
|---|---|---|---|---|
| 1 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 99 KB | 97 KB |
| 2 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 137 KB | 93 KB |
| 3 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 93 KB | 74 KB |
| 4 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 41 KB | 39 KB |
| 5 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 40 KB | 32 KB |
| 6 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp` | 1P | 75 KB | 30 KB |
| 7 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp` | 1P | 67 KB | 27 KB |
| 8 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp` | 1P | 56 KB | 22 KB |
| 9 | `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 1P | 23 KB | 22 KB |
| 10 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp` | 1P | 49 KB | 19 KB |
| 11 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp` | 1P | 42 KB | 17 KB |
| 12 | `https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp` | 1P | 42 KB | 17 KB |
| 13 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp` | 1P | 38 KB | 15 KB |
| 14 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp` | 1P | 30 KB | 12 KB |
| 15 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p137l0.jpg.webp` | 1P | 23 KB | 9 KB |
| 16 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0myp4.jpg.webp` | 1P | 22 KB | 9 KB |
| 17 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dskf.jpg.webp` | 1P | 19 KB | 8 KB |
| 18 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dl75.jpg.webp` | 1P | 17 KB | 7 KB |
| 19 | `https://cdn.privacy-mgmt.com/Notice.1c267.css` | 3P | 7 KB | 5 KB |
| 20 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p54p6m.jpg.webp` | 1P | 11 KB | 4 KB |
| 21 | `https://uk-script.dotmetrics.net/Scripts/ncs-script.js?v=366` | 3P | 3 KB | 3 KB |
| 22 | `https://cdn.privacy-mgmt.com/polyfills.01516.js` | 3P | 2 KB | 2 KB |
| 23 | `https://gn-web-assets.api.bbc.com/assets/imgs/BBC_Logo_Black_RGB_64px.png` | 1P | 2 KB | 2 KB |
| 24 | `https://rm-script.dotmetrics.net/hit.gif?id=13934&url=https%3A%2F%2Fwww.bbc.com%2F&dom=www.bbc.com&r=1787238210296&pvs=1&pvid=629607b8-6ce8-4aa4-ac86-82fd9bff2b3c&c=false&tzOffset=420` | 3P | 1 KB | 1 KB |

</details>

#### `font-display-insight` — Carattere visualizzato

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 200 ms su FCP.

Risparmio stimato di 200 ms · risparmio dichiarato: FCP 200 ms · score 0.00

Valuta la possibilità di impostare font-display su swap o optional per assicurarti che il testo sia visibile in modo coerente. swap può essere ulteriormente ottimizzato per ridurre gli spostamenti del layout con override delle metriche dei caratteri.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/font-display)

| # | Risorsa | Parte | Tempo |
|---|---|---|---|
| 1 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Md.woff2` | 1P | 200 ms |
| 2 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Rg.woff2` | 1P | 105 ms |
| 3 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_ExBd.woff2` | 1P | 70 ms |
| 4 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Md.woff2` | 1P | 20 ms |
| 5 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Rg.woff2` | 1P | 20 ms |
| 6 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Bd.woff2` | 1P | 15 ms |

#### `legacy-javascript-insight` — JavaScript precedente

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo + marketing/tag · guadagno stimato in lab: 150 ms su LCP.

Risparmio stimato di 97 KiB · risparmio dichiarato: LCP 150 ms · score 0.00

Polyfill e trasformazioni consentono ai browser precedenti di usare nuove funzionalità JavaScript. Tanti non sono però necessari per i browser moderni. Valuta la possibilità di modificare il processo di compilazione di JavaScript in modo da non transcompilare le funzionalità di base, a meno che non sia necessario supportare i browser precedenti. Scopri perché la maggior parte dei siti può eseguire il deployment del codice ES6+ senza transcompilazione

[Documentazione Google](https://web.dev/articles/baseline-and-polyfills)

| # | Risorsa | Parte | Sprecati |
|---|---|---|---|
| 1 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 36 KB |
| 2 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 19 KB |
| 3 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/12w5u9fluro3i.js` | 1P | 14 KB |
| 4 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 9 KB |
| 5 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 8 KB |
| 6 | `https://cdn.privacy-mgmt.com/unified/4.40.2/gdpr-tcf.27718c8cb9d29947d2c1.bundle.js` | 3P | 7 KB |
| 7 | `https://cdn.privacy-mgmt.com/unified/4.40.2/usnat.f12613136193900e32e2.bundle.js` | 3P | 4 KB |

#### `lcp-resourceLoadDelay` — Il browser scopre la risorsa LCP tardi: il tempo si perde prima ancora che il download inizi

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

- Fase dominante (utenti reali): Attesa prima del download — 39% del tempo LCP
- Ripartizione: Risposta del server (TTFB) 27%, Attesa prima del download 39%, Download della risorsa 14%, Rendering dell'elemento 20%
- Elemento LCP: &lt;img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="
- LCP di campo (p75 utenti reali): 1162 ms — buono

Voci di checklist non superate, testuali da Lighthouse:

- Deve essere applicata fetchpriority=high
- Le risorse LCP non devono utilizzare loading=lazy

#### `unminified-css` — Minimizza CSS

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: Risparmio stimato di 2 KiB.

Risparmio stimato di 2 KiB · score 0.50

Minimizza i file CSS per ridurre le dimensioni dei payload di rete. Scopri come minimizzare i file CSS.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/unminified-css/)

| # | Risorsa | Parte | Peso | Sprecati | Quota |
|---|---|---|---|---|---|
| 1 | `CSS inline` | 1P | 16 KB | 2 KB | 14% |

#### `script-treemap-data` — Script Treemap Data

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · **fuori dal master plan** — artefatto di dati: Lighthouse non allega una raccomandazione.

score 1.00

<details>
<summary>83 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati |
|---|---|---|---|---|
| 1 | `https://cdn.tinypass.com/api/tinypass.min.js` | 1P | 465 KB | 359 KB |
| 2 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 1P | 369 KB | 247 KB |
| 3 | `https://cdn.privacy-mgmt.com/unified/4.40.2/usnat.f12613136193900e32e2.bundle.js` | 1P | 404 KB | 217 KB |
| 4 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 397 KB | 193 KB |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0uu598vg94c03.js` | 1P | 264 KB | 180 KB |
| 6 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d2lp0c_d9lc8.js` | 1P | 175 KB | 175 KB |
| 7 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 188 KB | 158 KB |
| 8 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 1P | 384 KB | 132 KB |
| 9 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 132 KB | 118 KB |
| 10 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r330~rwdc1_z.js` | 1P | 175 KB | 78 KB |
| 11 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 187 KB | 76 KB |
| 12 | `https://cdn.privacy-mgmt.com/unified/4.40.2/gdpr-tcf.27718c8cb9d29947d2c1.bundle.js` | 1P | 160 KB | 75 KB |
| 13 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0sm_sfi0c1mq-.js` | 1P | 89 KB | 70 KB |
| 14 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02v.984noe-cm.js` | 1P | 122 KB | 61 KB |
| 15 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 1P | 138 KB | 56 KB |
| 16 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0a--~b-snp6to.js` | 1P | 70 KB | 52 KB |
| 17 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04vy5cnax5avz.js` | 1P | 43 KB | 39 KB |
| 18 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0_a80-qmpyc3s.js` | 1P | 38 KB | 38 KB |
| 19 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04x.wea_ofqc1.js` | 1P | 37 KB | 37 KB |
| 20 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/073u89hsadvk0.js` | 1P | 32 KB | 32 KB |
| 21 | `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 1P | 65 KB | 31 KB |
| 22 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0qji2plo1nsg7.js` | 1P | 31 KB | 31 KB |
| 23 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0k530rgixl5kt.js` | 1P | 36 KB | 30 KB |
| 24 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.ws-k_jzc8i2.js` | 1P | 44 KB | 26 KB |
| 25 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0zpz-874su9ks.js` | 1P | 29 KB | 25 KB |
| 26 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0db7s2w9wmo8-.js` | 1P | 31 KB | 22 KB |
| 27 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0s_kjwmep8yf2.js` | 1P | 25 KB | 22 KB |
| 28 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02w2j6a0szhem.js` | 1P | 25 KB | 22 KB |
| 29 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0pr885e78gdj8.js` | 1P | 23 KB | 21 KB |
| 30 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0-a6nanpwqpag.js` | 1P | 23 KB | 21 KB |
| 31 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0dygf8~f-ark~.js` | 1P | 19 KB | 19 KB |
| 32 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/035cetiu1lmqz.js` | 1P | 23 KB | 19 KB |
| 33 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ogvtm3jmac~r.js` | 1P | 22 KB | 17 KB |
| 34 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/07ayn82l6sni1.js` | 1P | 41 KB | 17 KB |
| 35 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/00w89utsyp_2c.js` | 1P | 17 KB | 17 KB |
| 36 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ublkb91cfh9r.js` | 1P | 28 KB | 17 KB |
| 37 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0~pb6..0m3xkm.js` | 1P | 24 KB | 16 KB |
| 38 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0p-.8yh27~p-n.js` | 1P | 25 KB | 14 KB |
| 39 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/06nzlhdny82mu.js` | 1P | 31 KB | 13 KB |
| 40 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r-xplh.6.-03.js` | 1P | 12 KB | 12 KB |
| 41 | `https://static.bbci.co.uk/frameworks/requirejs/0.13.0/sharedmodules/require.js` | 1P | 26 KB | 9 KB |
| 42 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/05el2iwpn3pyx.js` | 1P | 25 KB | 9 KB |
| 43 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0tvp5jqt08de_.js` | 1P | 11 KB | 9 KB |
| 44 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/12w5u9fluro3i.js` | 1P | 33 KB | 8 KB |
| 45 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0j3_87fm46g32.js` | 1P | 231 KB | 8 KB |
| 46 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/13ad5orspgznk.js` | 1P | 29 KB | 8 KB |
| 47 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0z3rjge5m4grx.js` | 1P | 15 KB | 8 KB |
| 48 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0m7zovr3x8k7x.js` | 1P | 8 KB | 8 KB |
| 49 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02xyfoe1v.vkw.js` | 1P | 8 KB | 8 KB |
| 50 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ney8voxt0l76.js` | 1P | 16 KB | 8 KB |
| 51 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d9awe5d081.2.js` | 1P | 34 KB | 7 KB |
| 52 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/072l.y87lhy8o.js` | 1P | 15 KB | 7 KB |
| 53 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/09.09l9881bul.js` | 1P | 37 KB | 6 KB |
| 54 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.44191m_y6r1.js` | 1P | 5 KB | 5 KB |
| 55 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.gu_l8v2fg11.js` | 1P | 5 KB | 5 KB |
| 56 | `https://uk-script.dotmetrics.net/Scripts/ncs-script.js?v=366` | 1P | 8 KB | 4 KB |
| 57 | `https://cdn.privacy-mgmt.com/polyfills.01516.js` | 1P | 5 KB | 4 KB |
| 58 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/004vauwu48azs.js` | 1P | 7 KB | 4 KB |
| 59 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0t7a3088d.epq.js` | 1P | 11 KB | 4 KB |
| 60 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0a7h_kuj3flvo.js` | 1P | 23 KB | 3 KB |
| 61 | `https://cdn.privacy-mgmt.com/index.html?hasCsp=true&message_id=1489022&consentUUID=null&consent_origin=https%3A%2F%2Fcdn.privacy-mgmt.com%2Fconsent%2Ftcfv2&preload_message=true&version=v1` | 1P | 3 KB | 3 KB |
| 62 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04_rrh.j6.wba.js` | 1P | 3 KB | 3 KB |
| 63 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0b-tgv1_m1uo9.js` | 1P | 6 KB | 2 KB |
| 64 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/127xbfgjo2hre.js` | 1P | 4 KB | 2 KB |
| 65 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0w54l~99pq3b9.js` | 1P | 2 KB | 2 KB |
| 66 | `https://uk-script.dotmetrics.net/door.js?d=www.bbc.com&t=homestudio` | 1P | 13 KB | 1 KB |
| 67 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0na6onp8uomzi.js` | 1P | 5 KB | 1 KB |
| 68 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r3he0rx_9z1a.js` | 1P | 19 KB | 1 KB |
| 69 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0wk8cccl75zp6.js` | 1P | 3 KB | 1 KB |
| 70 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0yv_0~sh~88vc.js` | 1P | 1 KB | 1 KB |
| 71 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0gmos.wajd.qx.js` | 1P | 1 KB | 1 KB |
| 72 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0fi49hn5~2abh.js` | 1P | 1 KB | 1 KB |
| 73 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0~~24znpk8vc1.js` | 1P | 1 KB | 0 KB |
| 74 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0u17oyz1d609w.js` | 1P | 1 KB | 0 KB |
| 75 | `https://a4621041136.cdn.optimizely.com/client_storage/a4621041136.html` | 1P | 2 KB | 0 KB |
| 76 | `https://www.bbc.com/` | 1P | 3 KB | 0 KB |
| 77 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/01ahds4cdfgmx.js` | 1P | 1 KB | 0 KB |
| 78 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/178~uy1pz6ka4.js` | 1P | 1 KB | 0 KB |
| 79 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0jcf7ay9pl-s0.js` | 1P | 2 KB | 0 KB |
| 80 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/05u0ya7obj7ro.js` | 1P | 7 KB |  |
| 81 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_buildManifest.js` | 1P | 1 KB |  |
| 82 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_ssgManifest.js` | 1P | 0 KB |  |
| 83 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_clientMiddlewareManifest.js` | 1P | 0 KB |  |

</details>

#### `third-parties-insight` — Terze parti

> **Classificazione nostra** — priorita' **bassa** · interviene: marketing/tag.

score 1.00

Il codice di terze parti può incidere notevolmente sulle prestazioni del caricamento. Riduci e posticipa il caricamento del codice di terze parti per dare la priorità ai contenuti della pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/third-parties)

| Voce | transferSize | mainThreadTime |
|---|---|---|
| `bbci.co.uk` | 1927 KB | 1032 ms |
| `privacy-mgmt.com` | 216 KB | 155 ms |
| `piano` | 137 KB | 45 ms |
| `Optimizely` | 103 KB | 127 ms |
| `Google/Doubleclick Ads` | 57 KB | 0 ms |
| `DotMetrics` | 10 KB | 3 ms |
| `bbc.co.uk` | 1 KB | 0 ms |

#### `image-delivery-insight` — Migliora il caricamento delle immagini

> **Classificazione nostra** — priorita' **bassa** · interviene: cms/redazione · guadagno stimato in lab: Risparmio stimato di 225 KiB.

Risparmio stimato di 225 KiB · score 0.50

La riduzione del tempo di download delle immagini può migliorare il tempo di caricamento percepito della pagina e il l'LCP. Scopri di più sull'ottimizzazione delle dimensioni delle immagini

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/image-delivery)

| # | Risorsa | Parte | Peso | Sprecati | Motivo |
|---|---|---|---|---|---|
| 1 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp` | 1P | 74 KB | 53 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 2 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp` | 1P | 66 KB | 45 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 3 | `https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a291-b542ee92de7c.jpg.webp` | 1P | 92 KB | 44 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 4 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp` | 1P | 48 KB | 27 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 5 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp` | 1P | 55 KB | 17 KB | Questo file immagine è più grande del necessario (800x450) per le dimensioni visualizzate (665x374). Utilizza le immagini adattabili per ridurre le dimensioni di download delle immagini. |
| 6 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp` | 1P | 38 KB | 16 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 7 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp` | 1P | 42 KB | 13 KB | Questo file immagine è più grande del necessario (800x450) per le dimensioni visualizzate (665x374). Utilizza le immagini adattabili per ridurre le dimensioni di download delle immagini. |
| 8 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp` | 1P | 30 KB | 8 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,6,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p419g7.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp" loading="lazy" alt="The Documentary Podcast, The Kansas City cycling revolution" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 53 KB |
| 2 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,3,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p5dys9.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp" loading="lazy" alt="The Documentary Podcast, LA: Rising from the ashes" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 45 KB |
| 3 | `div.Westminster-styles__MediaWrapperStyled-sc-348bb4b5-5 > div.Westminster-styles__MediaStyled-sc-348bb4b5-1 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,2,SECTION,0,SECTION,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" loading="lazy" alt="A firefighter helps an old lady out a building holding her arm as they ste…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 44 KB |
| 4 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,9,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p0p2rw.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp" loading="lazy" alt="Witness History, The battle of Mandalay in WW2" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 27 KB |
| 5 | `div.Edinburgh-styles__MediaWrapperStyled-sc-73f6adba-1 > div.Edinburgh-styles__MediaStyled-sc-73f6adba-2 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,4,SECTION,0,DIV,1,DIV,1,DIV,0,DIV,0,A,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 600px) 50vw, 100vw" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p5843m.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp" loading="lazy" alt="Pill packet with the metal cut to the shape of a person's profile.The pack…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 17 KB |
| 6 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,8,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p53w4l.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp" loading="lazy" alt="Business Daily, Founders: From sleeping under a bridge to SEO success in t…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 16 KB |
| 7 | `div.Edinburgh-styles__MediaWrapperStyled-sc-73f6adba-1 > div.Edinburgh-styles__MediaStyled-sc-73f6adba-2 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,4,SECTION,0,DIV,1,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 600px) 50vw, 100vw" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p536fl.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp" loading="lazy" alt="A drone view shows people swimming near a sunken WW2 warship in Prahovo, S…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 13 KB |
| 8 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,4,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p551xx.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp" loading="lazy" alt="Business Daily, Power Players: The battle over AI's data centres" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 8 KB |

#### `network-dependency-tree-insight` — Albero delle dipendenze di rete

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 0.00

Evita di concatenare le richieste fondamentali riducendo la lunghezza delle catene e le dimensioni del download delle risorse oppure rimandando il download delle risorse non necessarie per velocizzare il caricamento pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/network-dependency-tree)

<details>
<summary>9 voci</summary>

| Voce | navStartToEndTime | transferSize |
|---|---|---|
| `https://www.bbc.com/` | 237 ms | 95 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Rg.woff2` | 233 ms | 79 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Md.woff2` | 232 ms | 78 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Rg.woff2` | 418 ms | 66 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Md.woff2` | 418 ms | 65 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Bd.woff2` | 232 ms | 59 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_ExBd.woff2` | 252 ms | 48 KB |
| `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 255 ms | 23 KB |
| `https://www.bbc.co.uk/userinfo` | 825 ms | 1 KB |

</details>

#### `forced-reflow-insight` — Adattamento dinamico forzato del contenuto

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 0.00

Si verifica un adattamento dinamico forzato del contenuto quando JavaScript esegue query sulle proprietà geometriche (ad esempio offsetWidth) dopo che gli stili sono stati invalidati da una modifica allo stato DOM. Ciò può causare un rendimento scadente. Scopri di più sugli adattamenti dinamici forzati del contenuto e sulle possibili mitigazioni.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/forced-reflow)

| Voce | reflowTime |
|---|---|
| `[senza attributi]` | 126 ms |

#### `unsized-images` — Gli elementi immagine non hanno `width` e `height` esplicite

> **Classificazione nostra** — priorita' **bassa** · interviene: cms/redazione.

score 0.50

Imposta larghezza e altezza esplicite negli elementi immagine per ridurre le variazioni di layout e migliorare la metrica CLS. Scopri come impostare le dimensioni delle immagini

[Documentazione Google](https://web.dev/articles/optimize-cls#images_without_dimensions)

| # | Risorsa | Parte |
|---|---|---|
| 1 | `https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp` | 1P |

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ashford-styles__AshfordCardStyled-sc-648c73f6-0 > div.Ashford-styles__BackgroundImageWrapperStyled-sc-648c73f6-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,7,DIV,0,DIV,0,DIV,1,DIV,0,DIV,0,DIV,0,A,0,DIV,1,DIV,0,IMG` | `&lt;img sizes="96vw" srcset="https://ichef.bbci.co.uk/images/ic/160xn/p0nyldpb.jpg.webp 160w, https://i…" src="https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp" loading="lazy" alt="Queen Victoria's Men" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` |  |

#### `cls-culprits-insight` — Responsabili delle variazioni del layout

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 1.00

Le variazioni del layout si verificano quando gli elementi si spostano senza alcuna interazione da parte dell'utente. Esamina le cause delle variazioni del layout, come l'aggiunta o la rimozione di elementi o la modifica dei relativi caratteri durante il caricamento della pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/cls-culprit)

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `div.message-safe-area-holder > div.message-safe-area > div.message-container > div#notice` | `1,HTML,1,BODY,1,DIV,0,DIV,0,DIV,0,DIV` | `&lt;div id="notice" class="message type-modal" style="padding: 28px; border-width: 0px; border-color: rgb(0, 0, 0);">` | 0.095 |
| 2 | `section.Section-layouts-styles__SectionLayoutWrapper-sc-40ef2d4a-0 > section.Container-styles__ContainerStyled-sc-8b855a6c-0 > div.Grid-styles__GridStyled-sc-70d90311-0 > div.GridItem-styles__GridItemStyled-sc-6cc20e4a-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,2,SECTION,0,SECTION,0,DIV,1,DIV` | `&lt;div class="GridItem-styles__GridItemStyled-sc-6cc20e4a-0 bAYjOH">` | 0.006 |

## Articolo

`https://www.bbc.com/news`

**Elemento LCP**
- selettore: `div.Westminster-styles__MediaWrapperStyled-sc-348bb4b5-5 > div.Westminster-styles__MediaStyled-sc-348bb4b5-1 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0`
- markup: `<img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" loading="lazy" alt="A firefighter helps an old lady out a building holding her arm as they ste…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">`

**Ripartizione LCP** — origine: campo CrUX (utenti reali).

| Fase | Quota | Durata |
|---|---|---|
| Attesa prima del download | 39% | 498 ms |
| Risposta del server (TTFB) | 27% | 339 ms |
| Rendering dell'elemento | 20% | 257 ms |
| Download della risorsa | 14% | 176 ms |

**Scopribilita' della risorsa LCP** — checklist di Lighthouse.

| Esito | Controllo | Chiave |
|---|---|---|
| **fallito** | Deve essere applicata fetchpriority=high | `priorityHinted` |
| superato | La richiesta è rilevabile nel documento iniziale | `requestDiscoverable` |
| **fallito** | Le risorse LCP non devono utilizzare loading=lazy | `eagerlyLoaded` |

**Peso per tipo di risorsa** — JavaScript 1416 KB · Immagini 599 KB · Font 395 KB · HTML 99 KB · Chiamate XHR 81 KB · CSS 7 KB

**Entita' per peso**

| Entita' | Parte | Peso | Richieste |
|---|---|---|---|
| bbci.co.uk | 1P | 1925 KB | 96 |
| privacy-mgmt.com | 3P | 215 KB | 12 |
| piano | 3P | 137 KB | 1 |
| bbc.com | 1P | 122 KB | 7 |
| Optimizely | 3P | 103 KB | 4 |
| Google/Doubleclick Ads | 3P | 57 KB | 1 |
| DotMetrics | 3P | 38 KB | 5 |
| bbc.co.uk | 3P | 1 KB | 1 |

> Una sola misurazione di laboratorio distinta: la ripartizione in fasi dell'LCP varia molto fra run, quindi la fase dominante qui e' indicativa e non un risultato consolidato.

### Interventi

#### `legacy-javascript-insight` — JavaScript precedente

> **Classificazione nostra** — priorita' **media** · interviene: sviluppo + marketing/tag · guadagno stimato in lab: Risparmio stimato di 96 KiB.

Risparmio stimato di 96 KiB · score 0.50

Polyfill e trasformazioni consentono ai browser precedenti di usare nuove funzionalità JavaScript. Tanti non sono però necessari per i browser moderni. Valuta la possibilità di modificare il processo di compilazione di JavaScript in modo da non transcompilare le funzionalità di base, a meno che non sia necessario supportare i browser precedenti. Scopri perché la maggior parte dei siti può eseguire il deployment del codice ES6+ senza transcompilazione

[Documentazione Google](https://web.dev/articles/baseline-and-polyfills)

| # | Risorsa | Parte | Sprecati |
|---|---|---|---|
| 1 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 35 KB |
| 2 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 19 KB |
| 3 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/12w5u9fluro3i.js` | 1P | 14 KB |
| 4 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 9 KB |
| 5 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 8 KB |
| 6 | `https://cdn.privacy-mgmt.com/unified/4.40.2/gdpr-tcf.27718c8cb9d29947d2c1.bundle.js` | 3P | 7 KB |
| 7 | `https://cdn.privacy-mgmt.com/unified/4.40.2/usnat.f12613136193900e32e2.bundle.js` | 3P | 4 KB |

#### `unused-javascript` — Riduci il codice JavaScript inutilizzato

> **Classificazione nostra** — priorita' **media** · interviene: sviluppo + marketing/tag · guadagno stimato in lab: Risparmio stimato di 519 KiB.

Risparmio stimato di 519 KiB · score 0.50

Riduci il codice JavaScript inutilizzato e rimanda il caricamento degli script finché non sono necessari al fine di ridurre i byte consumati dall'attività di rete. Scopri come ridurre il codice JavaScript inutilizzato.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/unused-javascript/)

<details>
<summary>12 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati | Quota |
|---|---|---|---|---|---|
| 1 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 136 KB | 105 KB | 77% |
| 2 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 92 KB | 62 KB | 67% |
| 3 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 116 KB | 57 KB | 49% |
| 4 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d2lp0c_d9lc8.js` | 1P | 49 KB | 49 KB | 100% |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0uu598vg94c03.js` | 1P | 62 KB | 43 KB | 68% |
| 6 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 50 KB | 42 KB | 84% |
| 7 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 40 KB | 35 KB | 89% |
| 8 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 97 KB | 34 KB | 34% |
| 9 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0sm_sfi0c1mq-.js` | 1P | 32 KB | 25 KB | 78% |
| 10 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 58 KB | 24 KB | 41% |
| 11 | `https://uk-script.dotmetrics.net/Scripts/script.js?v=366` | 3P | 29 KB | 22 KB | 76% |
| 12 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r330~rwdc1_z.js` | 1P | 49 KB | 22 KB | 44% |

</details>

#### `bootup-time` — Riduci il tempo di esecuzione di JavaScript

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 1.650 ms su TBT.

2,6 s · risparmio dichiarato: TBT 1650 ms · score 0.00

Potresti ridurre i tempi di analisi, compilazione ed esecuzione di JavaScript. A questo scopo potrebbe essere utile pubblicare payload JavaScript di dimensioni inferiori. Scopri come ridurre il tempo di esecuzione di JavaScript.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/bootup-time/)

<details>
<summary>12 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Tempo |
|---|---|---|---|
| 1 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 1432 ms |
| 2 | `https://www.bbc.com/` | 1P | 488 ms |
| 3 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 319 ms |
| 4 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0t7a3088d.epq.js` | 1P | 178 ms |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0yv_0~sh~88vc.js` | 1P | 164 ms |
| 6 | `https://static.bbci.co.uk/frameworks/requirejs/0.13.0/sharedmodules/require.js` | 1P | 145 ms |
| 7 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 127 ms |
| 8 | `https://cdn.privacy-mgmt.com/unified/4.40.2/usnat.f12613136193900e32e2.bundle.js` | 3P | 115 ms |
| 9 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 109 ms |
| 10 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0tvp5jqt08de_.js` | 1P | 102 ms |
| 11 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 91 ms |
| 12 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 85 ms |

</details>

#### `mainthread-work-breakdown` — Riduci al minimo il lavoro del thread principale

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 1.400 ms su TBT.

4,0 s · risparmio dichiarato: TBT 1400 ms · score 0.00

Potresti ridurre i tempi di analisi, compilazione ed esecuzione di JavaScript. A questo scopo potrebbe essere utile pubblicare payload JavaScript di dimensioni inferiori. Scopri come minimizzare il lavoro del thread principale

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/mainthread-work-breakdown/)

| Voce | duration |
|---|---|
| `Script Evaluation` | 2520 ms |
| `Script Parsing & Compilation` | 459 ms |
| `Style & Layout` | 407 ms |
| `Other` | 330 ms |
| `Garbage Collection` | 202 ms |
| `Parse HTML & CSS` | 61 ms |
| `Rendering` | 61 ms |

#### `cache-insight` — Utilizza durate della memorizzazione nella cache efficienti

> **Classificazione nostra** — priorita' **bassa** · interviene: infrastruttura · guadagno stimato in lab: 300 ms su FCP.

Risparmio stimato di 594 KiB · risparmio dichiarato: LCP 100 ms, FCP 300 ms · score 0.00

La memorizzazione nella cache per un lungo periodo di tempo può velocizzare le visite abituali alla tua pagina. Scopri di più sulla memorizzazione nella cache.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/cache)

<details>
<summary>24 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati |
|---|---|---|---|---|
| 1 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 3P | 99 KB | 97 KB |
| 2 | `https://cdn.tinypass.com/api/tinypass.min.js` | 3P | 137 KB | 93 KB |
| 3 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 3P | 93 KB | 74 KB |
| 4 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 41 KB | 39 KB |
| 5 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 3P | 40 KB | 32 KB |
| 6 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp` | 1P | 75 KB | 30 KB |
| 7 | `https://uk-script.dotmetrics.net/Scripts/script.js?v=366` | 3P | 30 KB | 30 KB |
| 8 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp` | 1P | 67 KB | 27 KB |
| 9 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp` | 1P | 56 KB | 22 KB |
| 10 | `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 1P | 23 KB | 22 KB |
| 11 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp` | 1P | 49 KB | 19 KB |
| 12 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp` | 1P | 42 KB | 17 KB |
| 13 | `https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp` | 1P | 42 KB | 17 KB |
| 14 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp` | 1P | 38 KB | 15 KB |
| 15 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp` | 1P | 30 KB | 12 KB |
| 16 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p137l0.jpg.webp` | 1P | 23 KB | 9 KB |
| 17 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0myp4.jpg.webp` | 1P | 22 KB | 9 KB |
| 18 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dskf.jpg.webp` | 1P | 19 KB | 8 KB |
| 19 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dl75.jpg.webp` | 1P | 17 KB | 7 KB |
| 20 | `https://cdn.privacy-mgmt.com/Notice.1c267.css` | 3P | 7 KB | 5 KB |
| 21 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p54p6m.jpg.webp` | 1P | 11 KB | 4 KB |
| 22 | `https://cdn.privacy-mgmt.com/polyfills.01516.js` | 3P | 2 KB | 2 KB |
| 23 | `https://gn-web-assets.api.bbc.com/assets/imgs/BBC_Logo_Black_RGB_64px.png` | 1P | 2 KB | 2 KB |
| 24 | `https://rm-script.dotmetrics.net/hit.gif?id=13934&url=https%3A%2F%2Fwww.bbc.com%2F&dom=www.bbc.com&r=1787238300024&pvs=1&pvid=ee92a0cf-173a-46e8-bd81-aad8a7ea05cf&c=true&tzOffset=420` | 3P | 1 KB | 1 KB |

</details>

#### `font-display-insight` — Carattere visualizzato

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: 200 ms su FCP.

Risparmio stimato di 220 ms · risparmio dichiarato: FCP 200 ms · score 0.00

Valuta la possibilità di impostare font-display su swap o optional per assicurarti che il testo sia visibile in modo coerente. swap può essere ulteriormente ottimizzato per ridurre gli spostamenti del layout con override delle metriche dei caratteri.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/font-display)

| # | Risorsa | Parte | Tempo |
|---|---|---|---|
| 1 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Rg.woff2` | 1P | 215 ms |
| 2 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Md.woff2` | 1P | 70 ms |
| 3 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_ExBd.woff2` | 1P | 50 ms |
| 4 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Md.woff2` | 1P | 45 ms |
| 5 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Bd.woff2` | 1P | 45 ms |
| 6 | `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Rg.woff2` | 1P | 10 ms |

#### `lcp-resourceLoadDelay` — Il browser scopre la risorsa LCP tardi: il tempo si perde prima ancora che il download inizi

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

- Fase dominante (utenti reali): Attesa prima del download — 39% del tempo LCP
- Ripartizione: Risposta del server (TTFB) 27%, Attesa prima del download 39%, Download della risorsa 14%, Rendering dell'elemento 20%
- Elemento LCP: &lt;img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="
- LCP di campo (p75 utenti reali): 1162 ms — buono

Voci di checklist non superate, testuali da Lighthouse:

- Deve essere applicata fetchpriority=high
- Le risorse LCP non devono utilizzare loading=lazy

#### `script-treemap-data` — Script Treemap Data

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · **fuori dal master plan** — artefatto di dati: Lighthouse non allega una raccomandazione.

score 1.00

<details>
<summary>84 file — 1P sono vostri, 3P di terze parti</summary>

| # | Risorsa | Parte | Peso | Sprecati |
|---|---|---|---|---|
| 1 | `https://cdn.tinypass.com/api/tinypass.min.js` | 1P | 465 KB | 359 KB |
| 2 | `https://cdn.privacy-mgmt.com/Notice.97af9.js` | 1P | 369 KB | 247 KB |
| 3 | `https://cdn.privacy-mgmt.com/unified/4.40.2/usnat.f12613136193900e32e2.bundle.js` | 1P | 404 KB | 207 KB |
| 4 | `https://mybbc-analytics.files.bbci.co.uk/echo-client-js/echo-2.6.0-avi.min.js` | 1P | 397 KB | 193 KB |
| 5 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0uu598vg94c03.js` | 1P | 264 KB | 180 KB |
| 6 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d2lp0c_d9lc8.js` | 1P | 175 KB | 175 KB |
| 7 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0n-kjrsnwe2tb.js` | 1P | 188 KB | 158 KB |
| 8 | `https://cdn.optimizely.com/public/4621041136/s/bbcx_prod.js` | 1P | 384 KB | 132 KB |
| 9 | `https://emp.bbci.co.uk/emp/bump-4/bump-4.js` | 1P | 132 KB | 118 KB |
| 10 | `https://cdn.privacy-mgmt.com/unified/4.40.2/gdpr-tcf.27718c8cb9d29947d2c1.bundle.js` | 1P | 160 KB | 84 KB |
| 11 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r330~rwdc1_z.js` | 1P | 175 KB | 78 KB |
| 12 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0y-nyl-getpga.js` | 1P | 187 KB | 76 KB |
| 13 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0sm_sfi0c1mq-.js` | 1P | 89 KB | 70 KB |
| 14 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02v.984noe-cm.js` | 1P | 122 KB | 61 KB |
| 15 | `https://uk-script.dotmetrics.net/Scripts/script.js?v=366` | 1P | 79 KB | 58 KB |
| 16 | `https://cdn.privacy-mgmt.com/unified/wrapperMessagingWithoutDetection.js` | 1P | 138 KB | 56 KB |
| 17 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0a--~b-snp6to.js` | 1P | 70 KB | 52 KB |
| 18 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04vy5cnax5avz.js` | 1P | 43 KB | 39 KB |
| 19 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0_a80-qmpyc3s.js` | 1P | 38 KB | 38 KB |
| 20 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04x.wea_ofqc1.js` | 1P | 37 KB | 37 KB |
| 21 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/073u89hsadvk0.js` | 1P | 32 KB | 32 KB |
| 22 | `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 1P | 65 KB | 31 KB |
| 23 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0qji2plo1nsg7.js` | 1P | 31 KB | 31 KB |
| 24 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0k530rgixl5kt.js` | 1P | 36 KB | 30 KB |
| 25 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.ws-k_jzc8i2.js` | 1P | 44 KB | 26 KB |
| 26 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0zpz-874su9ks.js` | 1P | 29 KB | 25 KB |
| 27 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0db7s2w9wmo8-.js` | 1P | 31 KB | 22 KB |
| 28 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0s_kjwmep8yf2.js` | 1P | 25 KB | 22 KB |
| 29 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02w2j6a0szhem.js` | 1P | 25 KB | 22 KB |
| 30 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0pr885e78gdj8.js` | 1P | 23 KB | 21 KB |
| 31 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0-a6nanpwqpag.js` | 1P | 23 KB | 21 KB |
| 32 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0dygf8~f-ark~.js` | 1P | 19 KB | 19 KB |
| 33 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/035cetiu1lmqz.js` | 1P | 23 KB | 19 KB |
| 34 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ogvtm3jmac~r.js` | 1P | 22 KB | 17 KB |
| 35 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/07ayn82l6sni1.js` | 1P | 41 KB | 17 KB |
| 36 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/00w89utsyp_2c.js` | 1P | 17 KB | 17 KB |
| 37 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ublkb91cfh9r.js` | 1P | 28 KB | 17 KB |
| 38 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0~pb6..0m3xkm.js` | 1P | 24 KB | 16 KB |
| 39 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0p-.8yh27~p-n.js` | 1P | 25 KB | 14 KB |
| 40 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/06nzlhdny82mu.js` | 1P | 31 KB | 13 KB |
| 41 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r-xplh.6.-03.js` | 1P | 12 KB | 12 KB |
| 42 | `https://static.bbci.co.uk/frameworks/requirejs/0.13.0/sharedmodules/require.js` | 1P | 26 KB | 9 KB |
| 43 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/05el2iwpn3pyx.js` | 1P | 25 KB | 9 KB |
| 44 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0tvp5jqt08de_.js` | 1P | 11 KB | 9 KB |
| 45 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/12w5u9fluro3i.js` | 1P | 33 KB | 8 KB |
| 46 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0j3_87fm46g32.js` | 1P | 231 KB | 8 KB |
| 47 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/13ad5orspgznk.js` | 1P | 29 KB | 8 KB |
| 48 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0z3rjge5m4grx.js` | 1P | 15 KB | 8 KB |
| 49 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0m7zovr3x8k7x.js` | 1P | 8 KB | 8 KB |
| 50 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/02xyfoe1v.vkw.js` | 1P | 8 KB | 8 KB |
| 51 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0ney8voxt0l76.js` | 1P | 16 KB | 8 KB |
| 52 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0d9awe5d081.2.js` | 1P | 34 KB | 7 KB |
| 53 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/072l.y87lhy8o.js` | 1P | 15 KB | 7 KB |
| 54 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/09.09l9881bul.js` | 1P | 37 KB | 6 KB |
| 55 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.44191m_y6r1.js` | 1P | 5 KB | 5 KB |
| 56 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0.gu_l8v2fg11.js` | 1P | 5 KB | 5 KB |
| 57 | `https://cdn.privacy-mgmt.com/polyfills.01516.js` | 1P | 5 KB | 4 KB |
| 58 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/004vauwu48azs.js` | 1P | 7 KB | 4 KB |
| 59 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/turbopack-0t7a3088d.epq.js` | 1P | 11 KB | 4 KB |
| 60 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0a7h_kuj3flvo.js` | 1P | 23 KB | 3 KB |
| 61 | `https://cdn.privacy-mgmt.com/index.html?hasCsp=true&message_id=1489022&consentUUID=null&consent_origin=https%3A%2F%2Fcdn.privacy-mgmt.com%2Fconsent%2Ftcfv2&preload_message=true&version=v1` | 1P | 3 KB | 3 KB |
| 62 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/04_rrh.j6.wba.js` | 1P | 3 KB | 3 KB |
| 63 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0b-tgv1_m1uo9.js` | 1P | 6 KB | 2 KB |
| 64 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/127xbfgjo2hre.js` | 1P | 4 KB | 2 KB |
| 65 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0w54l~99pq3b9.js` | 1P | 2 KB | 2 KB |
| 66 | `https://uk-script.dotmetrics.net/door.js?d=www.bbc.com&t=homestudio` | 1P | 13 KB | 1 KB |
| 67 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0na6onp8uomzi.js` | 1P | 5 KB | 1 KB |
| 68 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0r3he0rx_9z1a.js` | 1P | 19 KB | 1 KB |
| 69 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0wk8cccl75zp6.js` | 1P | 3 KB | 1 KB |
| 70 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0yv_0~sh~88vc.js` | 1P | 1 KB | 1 KB |
| 71 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0gmos.wajd.qx.js` | 1P | 1 KB | 1 KB |
| 72 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0fi49hn5~2abh.js` | 1P | 1 KB | 1 KB |
| 73 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0~~24znpk8vc1.js` | 1P | 1 KB | 0 KB |
| 74 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0u17oyz1d609w.js` | 1P | 1 KB | 0 KB |
| 75 | `https://a4621041136.cdn.optimizely.com/client_storage/a4621041136.html` | 1P | 2 KB | 0 KB |
| 76 | `https://www.bbc.com/` | 1P | 3 KB | 0 KB |
| 77 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/01ahds4cdfgmx.js` | 1P | 1 KB | 0 KB |
| 78 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/178~uy1pz6ka4.js` | 1P | 1 KB | 0 KB |
| 79 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/0jcf7ay9pl-s0.js` | 1P | 2 KB | 0 KB |
| 80 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/chunks/05u0ya7obj7ro.js` | 1P | 7 KB |  |
| 81 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_buildManifest.js` | 1P | 1 KB |  |
| 82 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_ssgManifest.js` | 1P | 0 KB |  |
| 83 | `https://static.files.bbci.co.uk/bbcdotcom/web/20260817-125657-b933f830d3-web-3.18.0-12/_next/static/ktdMmvJVYs3w0V5E2sSBt/_clientMiddlewareManifest.js` | 1P | 0 KB |  |
| 84 | `https://uk-script.dotmetrics.net/SiteEvent.dotmetrics?r=1787238300451&v=eyJpZCI6MTM5MzQsImZsIjp0cnVlLCJkb20iOiJ3d3cuYmJjLmNvbSIsImxzbyI6bnVsbCwidXJsIjoiaHR0cHM6Ly93d3cuYmJjLmNvbS8iLCJydXJsIjoiIiwiZWNpZCI6ImVlOTJhMGNmLTE3M2EtNDZlOC1iZDgxLWFhZDhhN2VhMDVjZiIsImRjIjoiMDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAwIiwidmVyIjozNjYsImRmcGgiOiIiLCJ0ek9mZnNldCI6NDIwLCJvc3MiOnRydWUsIm9zZXMiOnRydWV9` | 1P | 0 KB |  |

</details>

#### `third-parties-insight` — Terze parti

> **Classificazione nostra** — priorita' **bassa** · interviene: marketing/tag.

score 1.00

Il codice di terze parti può incidere notevolmente sulle prestazioni del caricamento. Riduci e posticipa il caricamento del codice di terze parti per dare la priorità ai contenuti della pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/third-parties)

| Voce | transferSize | mainThreadTime |
|---|---|---|
| `bbci.co.uk` | 1925 KB | 1509 ms |
| `privacy-mgmt.com` | 215 KB | 279 ms |
| `piano` | 137 KB | 71 ms |
| `Optimizely` | 103 KB | 104 ms |
| `Google/Doubleclick Ads` | 57 KB | 0 ms |
| `DotMetrics` | 38 KB | 22 ms |
| `bbc.co.uk` | 1 KB | 0 ms |

#### `forced-reflow-insight` — Adattamento dinamico forzato del contenuto

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 0.00

Si verifica un adattamento dinamico forzato del contenuto quando JavaScript esegue query sulle proprietà geometriche (ad esempio offsetWidth) dopo che gli stili sono stati invalidati da una modifica allo stato DOM. Ciò può causare un rendimento scadente. Scopri di più sugli adattamenti dinamici forzati del contenuto e sulle possibili mitigazioni.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/forced-reflow)

| Voce | reflowTime |
|---|---|
| `[senza attributi]` | 114 ms |

#### `unsized-images` — Gli elementi immagine non hanno `width` e `height` esplicite

> **Classificazione nostra** — priorita' **bassa** · interviene: cms/redazione.

score 0.50

Imposta larghezza e altezza esplicite negli elementi immagine per ridurre le variazioni di layout e migliorare la metrica CLS. Scopri come impostare le dimensioni delle immagini

[Documentazione Google](https://web.dev/articles/optimize-cls#images_without_dimensions)

| # | Risorsa | Parte |
|---|---|---|
| 1 | `https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp` | 1P |

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ashford-styles__AshfordCardStyled-sc-648c73f6-0 > div.Ashford-styles__BackgroundImageWrapperStyled-sc-648c73f6-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,7,DIV,0,DIV,0,DIV,1,DIV,0,DIV,0,DIV,0,A,0,DIV,1,DIV,0,IMG` | `&lt;img sizes="96vw" srcset="https://ichef.bbci.co.uk/images/ic/160xn/p0nyldpb.jpg.webp 160w, https://i…" src="https://ichef.bbci.co.uk/images/ic/800xn/p0nyldpb.jpg.webp" loading="lazy" alt="Queen Victoria's Men" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` |  |

#### `network-dependency-tree-insight` — Albero delle dipendenze di rete

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 0.00

Evita di concatenare le richieste fondamentali riducendo la lunghezza delle catene e le dimensioni del download delle risorse oppure rimandando il download delle risorse non necessarie per velocizzare il caricamento pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/network-dependency-tree)

<details>
<summary>9 voci</summary>

| Voce | navStartToEndTime | transferSize |
|---|---|---|
| `https://www.bbc.com/` | 121 ms | 95 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Rg.woff2` | 237 ms | 79 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSerif_W_Md.woff2` | 240 ms | 78 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Rg.woff2` | 428 ms | 66 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Md.woff2` | 238 ms | 65 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_Bd.woff2` | 239 ms | 59 KB |
| `https://static.files.bbci.co.uk/fonts/reith/2.512/BBCReithSans_W_ExBd.woff2` | 239 ms | 48 KB |
| `https://gn-web-assets.api.bbc.com/ngas/latest/dotcom-bootstrap.js` | 269 ms | 23 KB |
| `https://www.bbc.co.uk/userinfo` | 995 ms | 1 KB |

</details>

#### `unminified-css` — Minimizza CSS

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo · guadagno stimato in lab: Risparmio stimato di 2 KiB.

Risparmio stimato di 2 KiB · score 0.50

Minimizza i file CSS per ridurre le dimensioni dei payload di rete. Scopri come minimizzare i file CSS.

[Documentazione Google](https://developer.chrome.com/docs/lighthouse/performance/unminified-css/)

| # | Risorsa | Parte | Peso | Sprecati | Quota |
|---|---|---|---|---|---|
| 1 | `CSS inline` | 1P | 16 KB | 2 KB | 14% |

#### `image-delivery-insight` — Migliora il caricamento delle immagini

> **Classificazione nostra** — priorita' **bassa** · interviene: cms/redazione · guadagno stimato in lab: Risparmio stimato di 225 KiB.

Risparmio stimato di 225 KiB · score 0.50

La riduzione del tempo di download delle immagini può migliorare il tempo di caricamento percepito della pagina e il l'LCP. Scopri di più sull'ottimizzazione delle dimensioni delle immagini

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/image-delivery)

| # | Risorsa | Parte | Peso | Sprecati | Motivo |
|---|---|---|---|---|---|
| 1 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp` | 1P | 74 KB | 53 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 2 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp` | 1P | 66 KB | 45 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 3 | `https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a291-b542ee92de7c.jpg.webp` | 1P | 92 KB | 44 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 4 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp` | 1P | 48 KB | 27 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 5 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp` | 1P | 55 KB | 17 KB | Questo file immagine è più grande del necessario (800x450) per le dimensioni visualizzate (665x374). Utilizza le immagini adattabili per ridurre le dimensioni di download delle immagini. |
| 6 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp` | 1P | 38 KB | 16 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |
| 7 | `https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp` | 1P | 42 KB | 13 KB | Questo file immagine è più grande del necessario (800x450) per le dimensioni visualizzate (665x374). Utilizza le immagini adattabili per ridurre le dimensioni di download delle immagini. |
| 8 | `https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp` | 1P | 30 KB | 8 KB | Aumentare il fattore di compressione dell'immagine potrebbe migliorare le dimensioni del download di questa immagine. |

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,6,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p419g7.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p419g7.jpg.webp" loading="lazy" alt="The Documentary Podcast, The Kansas City cycling revolution" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 53 KB |
| 2 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,3,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p5dys9.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p5dys9.jpg.webp" loading="lazy" alt="The Documentary Podcast, LA: Rising from the ashes" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 45 KB |
| 3 | `div.Westminster-styles__MediaWrapperStyled-sc-348bb4b5-5 > div.Westminster-styles__MediaStyled-sc-348bb4b5-1 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,2,SECTION,0,SECTION,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1008px) 33vw, (min-width: 600px) 66vw, 100vw" srcset="https://ichef.bbci.co.uk/news/240/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" src="https://ichef.bbci.co.uk/news/800/cpsprodpb/04db/live/0a124600-9c81-11f1-a…" loading="lazy" alt="A firefighter helps an old lady out a building holding her arm as they ste…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 44 KB |
| 4 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,9,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p0p2rw.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p0p2rw.jpg.webp" loading="lazy" alt="Witness History, The battle of Mandalay in WW2" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 27 KB |
| 5 | `div.Edinburgh-styles__MediaWrapperStyled-sc-73f6adba-1 > div.Edinburgh-styles__MediaStyled-sc-73f6adba-2 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,4,SECTION,0,DIV,1,DIV,1,DIV,0,DIV,0,A,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 600px) 50vw, 100vw" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p5843m.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/800x450/p0p5843m.jpg.webp" loading="lazy" alt="Pill packet with the metal cut to the shape of a person's profile.The pack…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 17 KB |
| 6 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,8,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p53w4l.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p53w4l.jpg.webp" loading="lazy" alt="Business Daily, Founders: From sleeping under a bridge to SEO success in t…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 16 KB |
| 7 | `div.Edinburgh-styles__MediaWrapperStyled-sc-73f6adba-1 > div.Edinburgh-styles__MediaStyled-sc-73f6adba-2 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,4,SECTION,0,DIV,1,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 600px) 50vw, 100vw" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p536fl.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/800x450/p0p536fl.jpg.webp" loading="lazy" alt="A drone view shows people swimming near a sunken WW2 warship in Prahovo, S…" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 13 KB |
| 8 | `a.Anchor-styles__AnchorStyled-sc-651d33db-0 > div.Ipswich-styles__ImageContainerStyled-sc-9e107448-0 > div.Image-styles__ImageCardStyled-sc-8c99a12b-1 > img.Image-styles__ImageStyled-sc-8c99a12b-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,6,SECTION,0,DIV,1,DIV,0,DIV,4,DIV,0,DIV,0,DIV,0,A,0,DIV,0,DIV,0,IMG` | `&lt;img sizes="(min-width: 1280px) 347px, (min-width: 1020px) calc(35.42vw - 31px), (min-…" srcset="https://ichef.bbci.co.uk/images/ic/160x90/p0p551xx.jpg.webp 160w, https://…" src="https://ichef.bbci.co.uk/images/ic/640x360/p0p551xx.jpg.webp" loading="lazy" alt="Business Daily, Power Players: The battle over AI's data centres" class="Image-styles__ImageStyled-sc-8c99a12b-0 cVsHni">` | 8 KB |

#### `cls-culprits-insight` — Responsabili delle variazioni del layout

> **Classificazione nostra** — priorita' **bassa** · interviene: sviluppo.

score 1.00

Le variazioni del layout si verificano quando gli elementi si spostano senza alcuna interazione da parte dell'utente. Esamina le cause delle variazioni del layout, come l'aggiunta o la rimozione di elementi o la modifica dei relativi caratteri durante il caricamento della pagina.

[Documentazione Google](https://developer.chrome.com/docs/performance/insights/cls-culprit)

| # | Selettore | Percorso DOM | Markup | Misura |
|---|---|---|---|---|
| 1 | `div.message-safe-area-holder > div.message-safe-area > div.message-container > div#notice` | `1,HTML,1,BODY,1,DIV,0,DIV,0,DIV,0,DIV` | `&lt;div id="notice" class="message type-modal" style="padding: 28px; border-width: 0px; border-color: rgb(0, 0, 0);">` | 0.054 |
| 2 | `div.message-safe-area-holder > div.message-safe-area > div.message-container > div#notice` | `1,HTML,1,BODY,1,DIV,0,DIV,0,DIV,0,DIV` | `&lt;div id="notice" class="message type-modal" style="padding: 28px; border-width: 0px; border-color: rgb(0, 0, 0);">` | 0.038 |
| 3 | `section.Section-layouts-styles__SectionLayoutWrapper-sc-40ef2d4a-0 > section.Container-styles__ContainerStyled-sc-8b855a6c-0 > div.Grid-styles__GridStyled-sc-70d90311-0 > div.GridItem-styles__GridItemStyled-sc-6cc20e4a-0` | `1,HTML,1,BODY,0,DIV,0,DIV,10,MAIN,0,ARTICLE,2,SECTION,0,SECTION,0,DIV,1,DIV` | `&lt;div class="GridItem-styles__GridItemStyled-sc-6cc20e4a-0 bAYjOH">` | 0.006 |

## Video

`https://www.bbc.com/video`

**Misurazione non riuscita.** PageSpeed Insights: non e' riuscito ad analizzare la pagina.

---

Punteggi PageSpeed Insights al momento della rilevazione: Home 48, Articolo 35. Numero di vetrina: non entra in nessuna valutazione di questo documento (ADR-001).
