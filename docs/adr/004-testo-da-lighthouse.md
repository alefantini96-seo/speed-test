# ADR-004: Il testo delle raccomandazioni viene da Lighthouse, verbatim

**Data:** 2026-08-20 (ricostruito il 2026-08-21 dai docstring che lo citano)
**Stato:** Approvato — esteso il 2026-08-27 con la quarta origine del testo

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

Il tool non scrive raccomandazioni. Ogni riga del report e' una di quattro cose,
e il report dichiara quale:

1. **testo di Lighthouse verbatim** — titoli, descrizioni, checklist, con i file
   nominati e i byte o i millisecondi;
2. **un dato misurato** — p75 di campo, storico, peso, ripartizione delle fasi;
3. **una classificazione nostra**, dichiarata come tale e derivata da dati: chi
   interviene, quanto e' prioritario, se e' azionabile, come si chiama il problema
   (`ETICHETTA_PROBLEMA`);
4. **un'istruzione scritta da noi**, solo dove Lighthouse non ne ha una — vedi
   sotto. Enumerata per audit, limitata a una cella, dichiarata riga per riga.

L'invariante e' presidiato dal test `test_nessuna_azione_scritta_a_mano`.

## La quarta origine: istruzioni nostre, enumerate

La condizione prevista in «Come si ribalta» si e' verificata, su due audit e non
sull'intero registro. `font-display-insight` si intitola «Carattere visualizzato»
e `legacy-javascript-insight` «JavaScript precedente»: sono traduzioni dei nomi
tecnici (`font-display`, *legacy JavaScript*), non azioni. Il ripiego previsto —
l'etichetta del primo link markdown della descrizione, dove per altri audit
Lighthouse mette l'imperativo — qui prende un termine a meta' frase: «font-display»
e «di base» (da *baseline*). In una colonna «intervento» consegnata al cliente
nessuno dei due dice cosa fare.

Quindi: `masterplan.AZIONE_PER_AUDIT`, una tabella `audit -> istruzione` scritta
da noi. I vincoli che la tengono al suo posto:

- **enumerata**: vale per gli audit elencati, non per una classe di casi. Ogni
  voce porta in commento il titolo che sostituisce;
- **una cella sola**: sostituisce la cella `intervento` del master plan. Il titolo
  di Lighthouse resta invariato ovunque nel report — schede HTML, Word, interfaccia;
- **dichiarata**: ogni riga del frammento porta `fonte_intervento`
  (`lighthouse` | `nostra`), e `speed masterplan` elenca a terminale le righe con
  testo nostro;
- **ancorata**: l'istruzione dice quello che dice la descrizione di Lighthouse per
  quell'audit, all'imperativo. Non aggiunge raccomandazioni che i dati non
  sostengono, che era il difetto delle prime versioni.

## Conseguenze

- Serve `locale=it` su ogni chiamata PSI: senza, il report esce in inglese.
- I link markdown dentro le descrizioni vanno risolti conservando l'etichetta, non
  rimossi: toglierli mutilava frasi come "impostare `font-display` su swap".
- Gli artefatti di dati (`script-treemap-data`) hanno una `description` interna non
  localizzata: si esclude, e si dichiara che l'audit porta dati e non una
  raccomandazione. Il titolo resta quello di Lighthouse.
- Aggiungere una voce ad `AZIONE_PER_AUDIT` e' un cambio di comportamento verso il
  cliente, non una correzione: va motivata nel commit con il titolo che sostituisce.
- Il tool non ha bisogno di un LLM. La dipendenza `anthropic`, prevista nel piano
  iniziale, e' stata rimossa.

## Come si ribalta

Se Lighthouse smettesse di localizzare, o se il registro del testo si rivelasse
inutilizzabile davanti a un cliente. In quel caso la strada non e' riscrivere il
testo, ma affiancarne una sintesi dichiarata come nostra.

Il primo pezzo di quella strada e' gia' stato percorso, sui due audit sopra. Se un
giorno la tabella dovesse crescere oltre una manciata di voci, il segnale non e'
«scriviamo tutto noi»: e' che il testo di Lighthouse non regge piu' come fonte, e
la decisione va ripresa da capo con un ADR nuovo.
