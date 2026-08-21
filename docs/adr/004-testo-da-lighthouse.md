# ADR-004: Il testo delle raccomandazioni viene da Lighthouse, verbatim

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato

---

## Contesto

Le prime versioni del tool contenevano raccomandazioni scritte a mano, del tipo
"inventario dei tag attivi", "valutare una facade per gli embed pesanti". Sono
risultate indifendibili: generiche, non ancorate ai dati della pagina, e in un
caso in contraddizione con la misurazione — la facade veniva suggerita su una
pagina dove l'audit `third-party-facades` di Lighthouse non era nemmeno presente.

Poi la verifica: PageSpeed Insights accetta il parametro `locale`. Con `locale=it`
titoli, descrizioni e voci di checklist tornano **gia' in italiano**, con i link
alla documentazione Google, e le tabelle nominano i file colpevoli con i byte o i
millisecondi sprecati per ciascuno.

## Problema

Chi scrive le raccomandazioni che finiscono nel report del cliente?

## Opzioni valutate

| Opzione | Pro | Contro |
|---------|-----|--------|
| **Testo scritto da noi** | tono uniforme, adattabile al cliente | non verificabile, invecchia, e nulla impedisce di scrivere qualcosa che i dati non sostengono |
| **Testo generato da un LLM** | fluido, adattabile | inventa numeri e raccomandazioni plausibili: e' esattamente il rischio che il tool deve escludere |
| **Testo di Lighthouse verbatim** | e' la fonte, e' gia' in italiano, ed e' ancorato alla misurazione | registro non nostro, e qualche titolo tecnico |

## Decisione

Il tool non scrive raccomandazioni. Ogni riga del report e' una di tre cose, e il
report dichiara quale:

1. **testo di Lighthouse verbatim** — titoli, descrizioni, checklist, con i file
   nominati e i byte o i millisecondi;
2. **un dato misurato** — p75 di campo, storico, peso, ripartizione delle fasi;
3. **una classificazione nostra**, dichiarata come tale e derivata da dati: chi
   interviene, quanto e' prioritario, se e' azionabile.

L'invariante e' presidiato dal test `test_nessuna_azione_scritta_a_mano`.

## Conseguenze

- Serve `locale=it` su ogni chiamata PSI: senza, il report esce in inglese.
- I link markdown dentro le descrizioni vanno risolti conservando l'etichetta, non
  rimossi: toglierli mutilava frasi come "impostare `font-display` su swap".
- Gli artefatti di dati (`script-treemap-data`) hanno una `description` interna non
  localizzata: si esclude, e si dichiara che l'audit porta dati e non una
  raccomandazione. Il titolo resta quello di Lighthouse.
- Il tool non ha bisogno di un LLM. La dipendenza `anthropic`, prevista nel piano
  iniziale, e' stata rimossa.

## Come si ribalta

Se Lighthouse smettesse di localizzare, o se il registro del testo si rivelasse
inutilizzabile davanti a un cliente. In quel caso la strada non e' riscrivere il
testo, ma affiancarne una sintesi dichiarata come nostra.
