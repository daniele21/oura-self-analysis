# Oura Insights — Piano Cardiovascular Intelligence e UX/UI

Stato: pianificazione, feature non ancora implementate. Data: 2026-11-01.
Repository: daniele21/oura-self-analysis. Destinazione: dashboard personale mobile-first su Mac mini, accesso remoto privato separato.

## Obiettivo prodotto

Consentire di capire: come sta cambiando il mio recupero fisiologico? Che cosa è successo nell'ultima notte? Come si collega a sonno e allenamenti? Quanto è affidabile ogni osservazione?

Non è un dispositivo medico, un motore predittivo, né uno score di salute. Solo statistiche personali, confronti espliciti, dati mancanti e interpretazioni limitate alle evidenze.

## 1. Stato attuale verificato

- health_analytics.py: HRV e FC minima notturna, confronto 7 giorni vs 28 precedenti.
- longitudinal_insights.py: dispersione robusta, persistenza e co-occorrenza di HRV e FC.
- sleep_intelligence.py: sintesi settimanale, comparazioni giornaliere e dettaglio singola notte.
- exercise_recovery.py: D+1/D+2/D+3 come giorni di risveglio successivi (NON ore esatte).
- dashboard/app.js: cinque tab, today/sleep/trends/insights/training, frontend JS monolitico ~41KB.
- dashboard_server.py: unica API /api/dashboard?days=7|30|90 con payload aggregato.
- Oura sleep è già fra le collezioni sincronizzate; heartrate ha scope separato e NON è tra le sincronizzazioni predefinite.
- Oura API V2 supporta serie HR e HRV notturne a 5 minuti, potenzialmente nei record sleep. Verificare sul Mac la struttura effettiva sleep.heart_rate / sleep.hrv e i campioni disponibili.

## 2. Decisione sull'information architecture

Massimo cinque voci nella bottom navigation su smartphone e nella sidebar desktop:

| Tab principale | Domanda | Contenuto proprietario |
|---|---|---|
| Oggi | Che cosa conta stamattina? | Sonno ultima notte, recupero recente, attività contestuale e 1–2 insight |
| Sonno | Come è andata la notte e la settimana? | Durata, regolarità, continuità, fasi, confronto notti |
| Recupero (nuova) | Come stanno cambiando HRV e FC? | Trend, baseline personali, profilo cardiovascolare notturno, HRV+FC |
| Attività | Cosa è successo dopo gli allenamenti registrati? | Workout, durata/intensità note, risposte dei risvegli D+1/D+2/D+3 |
| Insight | Quale osservazione vale approfondire? | Feed di osservazioni spiegabili e filtri per tema, dati a sostegno |

La scheda Trend scompare come destinazione di primo livello: un grafico approfondito è raggiunto dalla card relativa in Sonno, Recupero e Attività. La scelta riduce duplicazioni. La navigazione mobile resta a cinque voci.

Tre livelli progressivi di dettaglio, uguali in ogni dominio:
1. Panoramica: segnale, valore, confronto e freschezza, senza eccesso di grafici.
2. Esplora: trend, timeline, metriche comparate, selezione data e periodo.
3. Evidenza: quanti campioni, qualità, metodo, possibili confondenti e studio di riferimento.

## 3. Wireframe logico delle principali schermate

### Oggi

~~~text
Ultima notte registrata · dati aggiornati al ...
[Sonno 7hxx / vs settimana] [HRV xxms + FC min xxbpm / vs baseline]
Insight utile: "X cambiato rispetto alla media..."  [Perché?]
Ultima attività registrata                      [Apri Attività]
~~~

### Recupero — landing

~~~text
RECUPERO       grafico 7 | 30 | 90 giorni
"Rispetto ai tuoi valori abituali"
[HRV mediana 7g]   [FC minima mediana 7g]
[baseline precedenti 28g] [campione valido e copertura]
[Grafico HRV + fascia di riferimento]   → Dettaglio
[Grafico FC minima + fascia]             → Dettaglio
[Quante notti i due segnali si sono mossi insieme]
[Ultima notte]                            → Profilo notturno
[Possibili fattori da verificare]         → Sonno / Attività
~~~

Il selettore 7/30/90 cambia l'intervallo VISIBILE; la formula 7 vs 28 precedenti resta coerente e dichiarata. Etichetta esatta: FC minima notturna, non FC clinica a riposo.

### Profilo cardiovascolare della singola notte — schermata chiave

~~~text
← Recupero     notte del GG/MM          [<] [>]
[FC minima] [FC media] [HRV media] [campioni disponibili]
21:30        00:00         03:00         06:30
HR  (bpm) ────── linea, lacune non interpolate
HRV  (ms) ────── linea sincronizzata, aggregato 30 min
              [eventuale overlay fasi sonno se allineabili]
[Ora del minimo HR] [prima vs seconda metà] [HRV prima vs seconda metà]
[Vs notte precedente] [Vs 7 notti precedenti]
[Come è calcolato] [Dati mancanti] [Possibili spiegazioni]
~~~

Stesso asse X per HR e HRV, unità Y distinte, niente doppia scala che induce confronti spurî. Due modalità: orario locale (include DST) e tempo trascorso dall'addormentamento (confronto notti). Cursor sincronizzato sui due grafici; tabelle alternative per accessibilità.

### Sonno

La sezione mantiene overview settimanale e singola notte. Nel dettaglio notte compare SOLO una preview cardiovascolare con CTA "Apri HR e HRV di questa notte", che naviga in Recupero e mantiene la stessa data di risveglio. Nessun duplicato del grafico completo.

### Attività

Workout registrato → D+1/D+2/D+3 → click su un risveglio per aprire HR/HRV di quella notte in Recupero. Distinzione esplicita tra sessioni isolate e allenamenti sovrapposti, e fra intensità Oura e RPE soggettivo.

### Insight

Filtri Tutti | Sonno | Recupero | Attività. Ogni card contiene titolo concreto, differenza osservata, finestra, numerosità e collegamento al grafico fonte; dettaglio espandibile con statistiche, stabilità, alternative e limitazioni. Non inventare punteggi di rischio o etichette cliniche.

## 4. Backlog completo delle feature

| ID | Feature | Priorità | Dipendenze |
|---|---|---|---|
| DATA-01 | Audit privato dei campi sleep.heart_rate e sleep.hrv, sample interval, percentuale null, orari, copertura e presenza | P0 | SQLite |
| DATA-02 | Adapter per PublicSample(timestamp,interval,items): timezone, null, gap, duplicati, controlli numerici | P0 | DATA-01 |
| DATA-03 | Dizionario canonico metriche con fonte, unità, granularità, versione e disponibilità | P0 | DATA-01 |
| UX-01 | Riorganizzare le cinque voci, ripristino percorso e deep-link alla notte | P0 | decisione IA |
| UX-02 | Componenti riusabili: grafico lineare, due curve sincronizzate, baseline, qualità, evidence card | P0 | UX-01 |
| OPS-01 | Test sintetici, CI senza dati sanitari e controllo privacy/retention | P0 | trasversale |
| CV-01 | Recupero landing: trend HRV/FC, mediane 7/28 e qualità del campione | P1 | DATA-03, UX-01 |
| CV-02 | Serie HR e HRV 5-min della singola notte, con aggregati interpretativi >=30min | P1 | DATA-02, UX-02 |
| CV-03 | Momento del minimo HR, differenze prima/seconda metà, stabilità intranotte | P1 | CV-02 |
| CV-04 | Confronto della notte con D−1 esatto e con le sette notti precedenti; profili allineati per tempo trascorso | P1 | CV-02 |
| CV-05 | Trend longitudinali HRV/HR, dispersione robusta, percentili, persistenza, campione | P1 | CV-01 |
| UX-03 | Preview cardiovascolare in Sonno e link alla stessa notte in Recupero | P1 | CV-02 |
| INS-01 | Insight registry condiviso con fonte, metodo, numerosità e qualità; selezione per utilità | P1 | DATA-03, CV-01 |
| CV-06 | Co-occorrenza HRV↓ e FC↑ (o altri pattern) come analisi descrittiva e non clinica | P2 | CV-05 |
| CV-07 | Relazioni prespecificate HRV/FC con durata, efficienza, regolarità del sonno | P2 | CV-02, Sonno 2.0 |
| CV-08 | Annotazioni allenamenti e risposte dopo workout, lag e sovrapposizioni | P2 | CV-02, Exercise 2.0 |
| CV-09 | Finestra storica >90 giorni solo dopo verifica retention, consenso e qualità dati | P2-gated | OPS-01, DATA-03 |
| CTX-01 | Diario privato facoltativo con caffeina, alcol, stress percepito, RPE, routine | P2 | regole privacy e consenso |
| INS-02 | Associazioni con lag 0–3, confondenti, sensibilità e incertezza, senza mining indiscriminato | P3 | CTX-01, CV-07/08 |
| EXP-01 | Esperimenti personali N-of-1 con protocollo fissato prima di osservare i risultati | P3 | INS-02 |

## 5. Regole scientifiche e di qualità da rispettare

- Verificare che i record reali del Mac contengano array e metadati PublicSample. Oura supporta le serie notturne, ma completezza, null e disponibilità non sono garantiti.
- Ricostruire timestamp assoluti come sample timestamp + index × interval, conservando gli elementi null. Non allineare HRV/HR per sola posizione in array. Offset orari e DST sono casi obbligatori nei test.
- La risoluzione nominale può essere di 5 minuti. Per analisi interpretative preferire medie/mediane su almeno 30 minuti, dopo verifica della qualità dei campioni (letteratura qualità Oura HRV). I punti individuali sono ammessi solo come visualizzazione descrittiva.
- Soglie tecniche PROPOSTE, non cliniche: un bin 30-min contiene 6 campioni nominali; per calcolarlo chiedere almeno 4 validi. Confronto fra metà notte solo con almeno 2 bin validi per ciascuna metà. Calibrare dopo audit reale.
- Non riempire mancanze con zeri; mostrare gaps reali e copertura per canale.
- La FC minima notturna di Oura non è identica a una media clinica a riposo; le serie e i summary possono usare aggregazioni differenti.
- Baseline longitudinale coerente: 7 notti recenti contro 28 notti precedenti SENZA sovrapposizione. Mostrare mediana, n, dispersione, periodo, limitazioni.
- I dati sul sonno hanno il giorno del risveglio; il workout ha il giorno di registrazione. I lag D+1/2/3 sono risvegli, non precisamente 24/48/72 ore.
- La combinazione HRV/FC non è un test diagnostico di infezione, malattia, overtraining, squilibrio simpatico/parasimpatico né età biologica.
- Fasi REM/profondo incrociate con HRV solo dopo accertamento dell'allineamento tra epoche e campioni; sempre esplorative.
- Associazioni comportamentali soltanto con ipotesi predefinite, campione, analisi di sensibilità, confondenti, e nessuna causalità ingiustificata.

## 6. Architettura proposta

~~~text
Oura API autorizzata → SQLite locale
       ↓
cardio_data_quality.py         (profilo e audit di campioni)
cardio_night_profiles.py      (serie 5-min e aggregati 30-min)
cardio_longitudinal.py        (7/28, notte, settimana, storico)
cardio_associations.py        (successivamente, relazioni esplorative)
insight_registry.py           (unico motore spiegabile)
       ↓
dashboard_server.py           (API HTTP private, versionate)
dashboard/
  app.js                      (router + bootstrap)
  components/                 (metric-card, charts, evidence-card)
  views/                      (today, sleep, recovery, activity, insights, night)
  styles/                     (tokens, layout, chart)
~~~

Evitare un big-bang refactor. Estrarre moduli e contratti gradualmente dall'attuale app.js, preservando il funzionamento delle sezioni esistenti.

Endpoint orientativi:
- GET /api/v2/overview?days=30
- GET /api/v2/recovery?days=7|30|90
- GET /api/v2/recovery/night?day=YYYY-MM-DD (una sola notte, risposta bounded)
- GET /api/v2/sleep?days=...
- GET /api/v2/insights?topic=...

Conservare temporaneamente /api/dashboard per compatibilità. Validazione severa degli input, nessun parametro file path/SQL, no-cache dati sanitari, nessuna pubblicazione pubblica, accesso Tailscale privato solo se configurato e autorizzato.

## 7. Dipendenze e parallelizzazione

~~~mermaid
flowchart TD
  A[DATA-01 audit privato] --> B[DATA-02 adapter campioni]
  A --> C[DATA-03 registro metriche]
  D[UX-01 navigazione] --> E[UX-02 componenti]
  B --> F[CV-02 profili notturni]
  E --> F
  C --> G[CV-01 Recupero landing]
  D --> G
  F --> H[CV-03 e CV-04 dettaglio notte]
  G --> I[CV-05 trend]
  H --> J[UX-03 collegamento Sonno]
  I --> K[CV-06-08 relazioni]
  K --> L[INS-02 associazioni]
  L --> M[EXP-01 esperimenti]
~~~

Lane A: ingestion, audit, normalizzazione e qualità. Lane B: IA, UX mobile e visualizzazioni. Lane C: API privacy, persistenza, retention e test. Lane D: analytics, insight registry e integrazione. Lane A/B/C possono iniziare in parallelo dopo approvazione del contratto dati.

## 8. Definition of done

1. Audit Mac su dati reali, nel filesystem privato, stampa solo stato e non valori fisiologici nei log Actions.
2. Test sintetici: 5-min null, percentuale dati mancanti, DST, overlap record, duplicati, sessione corta, notte assente, allineamento HR vs HRV.
3. Tutti i grafici con unità, asse data/ora e legenda, coverage, assenza di interpolazione e alternativa tabellare. Contrasto WCAG 2.2 AA; significato non espresso solo dal colore.
4. Da Oggi a profilo cardiovascolare di una notte in massimo due tap; stessa notte conservata quando si naviga Sonno ↔ Recupero.
5. Per ogni insight: campione, finestra, formula, limite, possibile confondente, riferimento, data aggiornamento e link al relativo grafico.
6. Performance mobile: le serie di una notte si caricano on demand, non 90 notti di campioni per apertura. Payload limitato e caching sanitario disabilitato.
7. API read-only/loopback, test senza dati reali, logs e output CI senza dati sanitari. Retention e condizioni di accesso Oura verificate prima di ampliare conservazione e prodotto.
8. CI verde, smoke test Mac con solo schema e HTTP status, rollback e tag di checkpoint.

## 9. Milestone

- M0: DATA-01, gate contrattuale/privacy, UX-01 wireframe con dati sintetici, contratti API (nessuna feature clinica).
- M1: adapter notturno + Recupero landing + doppio grafico notturno + confronto notti + link Sonno.
- M2: longitudinal insights, marker allenamenti, sleep × HRV/HR, ranking spiegabile.
- M3: diario volontario, correlazioni preregistrate, piccoli esperimenti personali.

Non-obiettivi: score medico proprietario, previsione malattia/aritmie, diagnosi di stress, interpretazione clinica di ogni intervallo da 5 minuti, uso di LLM sui dati Oura, cloud analytics pubblico.

## 10. Riferimenti

- Oura API metrics: https://partnersupport.ouraring.com/hc/en-us/articles/28571089902227-Metrics-Available-via-the-Oura-API
- Oura API Gen3: https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API
- Oura API and MCP Agreement: https://cloud.ouraring.com/legal/api-agreement
- Dial et al. (2025), HR/HRV nocturnal validation: https://doi.org/10.14814/phy2.70527
- Validation of HR/rMSSD Oura and 30-min aggregation: https://pubmed.ncbi.nlm.nih.gov/39686012/
- NN/g progressive disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- WCAG 2.2: https://www.w3.org/TR/wcag/
