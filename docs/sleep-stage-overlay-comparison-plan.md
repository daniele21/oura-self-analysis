# Sleep Intelligence — Confronto sovrapposto delle fasi di sonno

**Data:** 2026-11-02  
**Ambito:** Sonno → Fasi del sonno nel tempo  
**Stato:** piano tecnico/UX; la checklist di rilascio viene aggiornata separatamente dopo i test.

## Obiettivo

Confrontare **Leggero, Profondo e REM** tra due periodi di uguale durata in modo immediato, con **tre piccoli grafici sovrapposti** (due linee ciascuno), riassunti A/B e delta, scelta minuti/% e dati mancanti espliciti. Non introdurre una seconda pagina di analisi né ripetere il generico «Come cambia il tuo sonno»; questa è una vista specializzata sulle tre fasi stimabili dal dispositivo.

### Informazione gerarchica
1. **Decisione rapida:** media per notte del periodo A (recente), periodo B (precedente), differenza A−B e copertura n/N per ciascuna fase.
2. **Distribuzione:** tre piccoli grafici, uno per Leggero, uno per Profondo e uno per REM. Due linee per pannello con asse «Giorno del periodo» (G1…G7 / G1…G30): **A continua**, **B tratteggiata**. Missing = interruzione, mai zero/interpolazione.
3. **Verifica:** cursore accessibile per confrontare lo stesso giorno relativo, valori A/B, giorni assoluti di provenienza, metodo, limiti, tabella alternativa e navigazione alla singola notte.

## Wireframe mobile-first

~~~text
SONNO › Fasi del sonno
[Composizione] [Trend 7g] [Confronta periodi]
Periodo:  [ 7 vs 7 ▾ ]            [ Minuti | % ]
Ultima notte misurata: 2 nov
A: 27 ott – 2 nov | n=7/7
B: 20 ott – 26 ott | n=6/7

[LEGGERO]     A: 246 min | B: 233 min | Δ +13
[   ━━ A ... − − B ... (G1…G7)             ]

[PROFONDO]    A: 91 min  | B: 103 min | Δ −12
[   ━━ A ... − − B ... (G1…G7)             ]

[REM]         A: 111 min | B: 104 min | Δ +7
[   ━━ A ... − − B ... (G1…G7)             ]

● G4     A 28 ott: 109 min     B 21 ott: 100 min
▸ Tabella accessibile      ▸ Come leggere il grafico
~~~

Valori nel wireframe **esemplificativi**, non misurazioni reali.

## V1 — scope chiuso

- Un nuovo terzo controllo «Confronta periodi» nella stessa componente Sleep Stage; mantenere le modalità esistenti «Composizione» e «Trend 7 giorni».
- Preset **7 vs 7** (ultimo 7 giorni vs 7 precedenti) e **30 vs 30** (ultimo 30 vs 30 precedenti), ancorati all'**ultima notte principale valida disponibile**, non automaticamente a oggi.
- Periodi senza sovrapposizioni, **uguale lunghezza**, allineati per **indice del giorno nel periodo**. Per 7v7 coincidono anche i giorni della settimana; per 30v30 non sempre: NON etichettare l'asse come «lunedì» in V1.
- Due linee per ogni fase, più numeri A, B, Δ; A più recente linea continua e B più vecchio tratteggiata. Colore identifica la fase, tratteggio la coorte: il grafico non dipende solo dal colore.
- Unico controllo «Minuti / Percentuale» riutilizzato da Sleep Stage. Delta minuti oppure **punti percentuali**; per % utilizzare il rapporto somma fase / somma totale sonno per ciascun periodo, non la media dei rapporti.
- **Copertura esplicita:** 7v7 richiede ≥4 notti qualificate per ciascun periodo; 30v30 richiede ≥21 per periodo, coerente con i gate esistenti dei confronti lunghi. Sotto soglia il riepilogo A/B/Δ è assente, ma i punti validi del grafico possono essere osservati con avviso «insufficiente».
- Notti valide: solo \`long_sleep\` e tutte e tre le fasi coerenti col totale, come già definito in \`sleep_stage_trends.qualified\`. **Dati mancanti non sono zero**. Date assolute dei due periodi sempre visibili.
- **Vincolo di privacy delle finestre:** non esporre in una risposta 7 giorni gli altri 7 valori individuali. Se l'utente seleziona 7v7 e la vista contiene solo 7 giorni, proporre/attivare il caricamento esplicito di 30 giorni; per 30v30 occorrono 90 giorni. Tutti i dati restano local-only; gli endpoint esistenti \`/api/dashboard?days=7|30|90\` non cambiano.
- Interazione smartphone: selettori/tasti touch-friendly ≥44px, cursore da tastiera, tabella accessibile, screenreader labels, tooltip/inspector con giorno A e giorno B reali. Altezza piccola per ciascuno dei 3 grafici (small multiples).
- In assenza di risultati non mostrare frasi «più REM = miglioramento»: le fasi sono stime; % maggiore può derivare dal denominatore più basso.

### Non includere in V1
- Date custom, settimane arbitrarie, confronto sovrapposto di più di due periodi, test significatività statistica, p-value, «recovery score», inferenze mediche o causalità.
- I grafici «differenza giorno per giorno» sono V2; in V1 il delta aggregato nelle tre schede è già presente.

## Criteri statistici e semantici

Sia fase \(s\), periodi \(A,B\), giorni validi \(V_A,V_B\).

- \(\overline{s}_A = \sum_{d\in V_A} s_d / |V_A|\) (minuti per notte valida). B analogo.
- \(p_A = 100 \sum_{d\in V_A} s_d / \sum_{d\in V_A} \mathrm{sleepMinutes}_d\). B analogo.
- \(\Delta_{min}=\overline{s}_A-\overline{s}_B\); \(\Delta_{pp}=p_A-p_B\).
- Linee V1 mostrano singole durate giornaliere e rispettive percentuali, **non una media mobile** (quella rimane nell'altra tab).
- \`as_of\` = giorno di risveglio dell'ultima notte principale qualificata, non necessariamente la data di richiesta. Rendere esplicita la freschezza.

## Architettura e dipendenze

**Riutilizzare** \`sleep_stage_trends.py\` e \`sleep_intelligence.stage_trends.daily\`, senza nuova duplicazione dei record Oura. L'output giornaliero qualificato comprende durata delle fasi, percentuali e **totale sonno**; aggiungere quest'ultimo alla sola API già autorizzata, nel periodo 7/30/90 selezionato. Un helper deterministico prepara 7v7 e 30v30 a partire da date, evitando il rischio DST usando aritmetica dei giorni di calendario, e produce solo schema riferimenti/aggregati quando non è autorizzata la visualizzazione delle singole giornate precedenti.

In frontend:
- State \`stageMode: composition|trend|compare\`, \`stageComparison: 7v7|30v30\`, \`stageUnit: minutes|percent\`.
- Una componente \`sleepStagePeriodComparison(data)\` integra tre grafici, non la chart generic \`periodComparisonView\`, che confronta una sola metrica alla volta.
- Fissare range necessario: 7v7 richiede 14 giorni, quindi usare la vista 30; 30v30 richiede 60, quindi usare la vista 90. Se dati non disponibili, mostrare una CTA coerente.
- Usare gli stessi colori Light, Deep, REM presenti in styles.css e pattern A/B per leggibilità.

## Lavori in ordine e test di accettazione

| ID | Lavoro | Dipendenza | Done quando… |
|---|---|---|---|
| SLP-C01 | Helper puro per estrarre 7v7/30v30 con n, medie e delta; date esatte, qualifica coerente | \`stage_trends.daily\` | Synthetic tests su offset, mancanze, percentuali pesate, stale data |
| SLP-C02 | Terza modalità «Confronta periodi», dropdown preset, unità | C01 | Non degrada Composition/Trend e conserva lo stato durante la navigazione |
| SLP-C03 | Tre grafici piccoli con A continuo e B tratteggiato | C01–02 | G1..GN, gap reali, assi e scale confrontabili entro la stessa fase |
| SLP-C04 | Cursore sincronizzato, A/B per medesimo giorno relativo, tabella | C03 | Mobile 360px, tastiera, label, data precisa, niente solo colore |
| SLP-C05 | QA privacy/UX e documentazione metodo | C01–04 | Suite offline verde e no raw data in GitHub |
| SLP-C06 | Deploy Mac mini tramite Actions con pin SHA e smoke-test API | C05 | Statico/API ok e 7/30/90; no metriche fisiologiche nei log |

### V2 (successiva, solo dopo verifica della V1)

- Date custom A/B di uguale durata 3–30 giorni e confronto per settimana lunedì–domenica.
- Toggle grafico differenza per giorno \`A−B\`, mantenendo i gap.
- Esportazione locale PNG/CSV solo esplicitamente richiesta e con privacy/retention controllate.
- Confronto anche del sonno totale, efficienza e awake time sfruttando il framework metriche esistente.

## Rischi da prevenire
- Rottura tra anchor «oggi» della dashboard e l'ultima notte effettivamente registrata.
- Tracciare la data con UTC a mezzogiorno per evitare spostamenti DST durante la sottrazione dei giorni.
- Uso erroneo della mediana settimanale anziché media in minuti nella comparazione fasi.
- Notti diverse come denominatori nei tre pannelli, se una fase manca (richiedere tutte e tre consistenti).
- Due periodi di 30 notti oltre il limite 30-day API: **no** leak della serie giornaliera precedente; richiedere esplicitamente 90d.
- Colori della fase diversi tra le visualizzazioni.
- Conclusioni sulla qualità del sonno basate solo sul numero di minuti REM o Deep.

**Metodo di riferimento:** \`docs/scientific-methods.md\`, \`sleep_stage_trends.py\`, \`period_comparisons.py\`.