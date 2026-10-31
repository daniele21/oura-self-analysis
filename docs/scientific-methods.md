# Metodologia scientifica — Oura Self-Analysis MVP

**Versione:** 1.1 — 31 ottobre 2026. **Ambito:** statistiche personali descrittive, non diagnosi e non decisioni cliniche.

## Obiettivo

Fornire misure ricostruibili da SQLite, confronto con la propria storia, copertura e motivazioni trasparenti. Non calcoliamo un "Health Score", non generiamo probabilità di malattia e non usiamo AI, modelli predittivi o training ML sui dati Oura.

L'enrichment si esegue **localmente sul Mac**. La pubblicazione su Drive è facoltativa e richiede esplicitamente `--include-health`. Non inviare i dati a un LLM, nemmeno locale, senza verificare i termini Oura.

## 1. Sleep Intelligence

**Origine:** `sleep` (sessione `long_sleep` preferita ai sonnellini); `daily_sleep` per lo score. L'API usa il campo `day` come giorno di risveglio della sessione principale: non attribuire il sonno al giorno di inizio dell'intervallo.

**Feature:** durata totale in minuti, latenza, efficienza, orari locali `bedtime_start` / `bedtime_end`, frequenza respiratoria media (`average_breath`), media mobile di 7 giorni della durata. Calcoliamo anche la deviazione standard degli orari locali di coricamento su **14 giorni di calendario**, con almeno **7 osservazioni**.

**Scelta temporale:** l'orario è trasformato in minuti rispetto a mezzogiorno locale per gestire il passaggio dalle 23:50 alle 00:10. Si conserva l'offset del timestamp. Orari senza timezone non contribuiscono alla regolarità. Viaggi, turni e sonno diurno possono invalidare il proxy.

**Limiti:** la deviazione standard dell'ora di coricamento **non è** il *Sleep Regularity Index* usato negli studi prospettici, che richiede una serie sonno-veglia a risoluzione più elevata. Non etichettare una notte come "scarsa" sulla sola base delle fasi REM/profonda stimate.

## 2. Autonomic Recovery

**Origine:** HRV media notturna `average_hrv` e **frequenza cardiaca minima** della sessione `lowest_heart_rate`. Il campo `rhr_bpm` dell'export attuale rappresenta precisamente il valore **minimo notturno**, non una diagnosi o una misura clinica standard della frequenza a riposo.

**Finestre non sovrapposte:**
- **Recente:** mediana degli ultimi 7 giorni di calendario, giorno corrente incluso, almeno **5** osservazioni.
- **Baseline:** mediana dei **28 giorni immediatamente precedenti** il blocco recente (da 7 a 34 giorni prima del giorno corrente), almeno **14** osservazioni.
- HRV: variazione `(mediana7 - mediana28) / mediana28 * 100`, solo se la baseline è positiva.
- Frequenza cardiaca minima: `mediana7 - mediana28`, in bpm.

I requisiti minimi per il numero di osservazioni sono scelte ingegneristiche conservative **non soglie validate clinicamente**. Le finestre non sovrapposte evitano che una fluttuazione recente entri anche nel riferimento. Le lacune non sono interpolate e i valori fisiologicamente inverosimili sono marcati mancanti, non zero.

**Limiti:** HRV e frequenza cardiaca variano con malattia, alcol, sonno, ciclo di allenamento, farmaci, stress, viaggio, sensore e contesto. Non è appropriato tradurre il segno della variazione in un giudizio automatico di salute.

## 2b. Longitudinal Insights — robustezza statistica (v1.1)

Aggiunto \`longitudinal_insights.py\`: tre analisi di variabilità individuale (**HRV notturna, FC minima notturna, durata del sonno**) e una analisi congiunta HRV/FC, quando i dati lo consentono. Sono **descrittive, esplorative, non diagnostiche**.

### Finestre e qualità

- Ultimi **7 giorni di calendario** rispetto ai **precedenti 28** (escludendo esattamente i sette più recenti).
- Minimo **5/7** osservazioni recenti e **14/28** nella baseline. Con meno osservazioni, l'analisi è **soppressa**, non sostituita con zeri o previsioni.
- Qualità della copertura \`adequate\` con almeno **6/7** e **21/28** osservazioni, altrimenti \`limited\`. Questo livello descrive soltanto la **completezza del campione**, **non** la certezza dell'interpretazione scientifica.
- Anche se la UI mostra solo 7 giorni, il motore usa sul Mac 35 giorni per la baseline: le righe giornaliere antecedenti al periodo richiesto **non vengono esportate** al browser.

### Formule e robustezza

- Centro storico: \`m = mediana(baseline)\`.
- Dispersione: \`MAD = mediana(|x - m|)\`; \`sigma_robusta = 1,4826 × MAD\`, interpretazione appropriata principalmente per distribuzioni non eccessivamente asimmetriche.
- Scostamento: \`delta = mediana(recente) - m\`; \`delta_% = 100 × delta / m\` quando \`m ≠ 0\`.
- **Banda descrittiva personale**: \`[m - 2 × sigma_robusta, m + 2 × sigma_robusta]\`. Il moltiplicatore 2 è una **euristica ingegneristica e non una soglia clinica validata**; non è un test di significatività.
- Frequenza delle giornate fuori dalla banda e **massima sequenza consecutiva** negli ultimi sette giorni, con lacune che interrompono le sequenze.
- Coefficiente di variazione degli ultimi sette giorni: \`CV% = 100 × deviazione standard / media\`, quando la media è positiva.
- **Leave-one-out:** quota di mediane, ottenute omettendo a turno una notte, che mantengono la direzione della differenza osservata. Misura di sensibilità descrittiva, non probabilità causale.
- **Intervallo esplorativo bootstrap 80%:** 300 ripetizioni deterministiche con campionamento circolare a blocchi da **tre giorni**, separatamente per finestra recente e baseline. Esclusivamente con **35/35 giornate complete**; in caso di lacune, l'intervallo non è generato. Non rappresenta una probabilità di malattia né un intervallo di confidenza clinicamente validato.
- Se la baseline ha dispersione nulla o quasi nulla, lo scostamento numerico resta visibile ma **non** viene calcolato uno score standardizzato né una banda per definire "insolito".

### Co-movimento HRV/FC

Quando esistono due baseline utilizzabili, contiamo i giorni con **HRV sotto la banda personale e FC minima sopra la propria banda** contemporaneamente. Il risultato è un conteggio associativo descrittivo, non uno score di infezione o di overtraining; la stima rimane fragile senza intensità di allenamento, alcol, farmaci, stress e condizioni ambientali.

### Evidence gate e gestione dell'incertezza

Ogni insight include: \`measurements\` riproducibili, \`quality\` con numerosità/copertura, \`interpretation\` contestualizzata, \`alternative_explanations\`, \`limitations\`, \`evidence_urls\`, \`medical_alert=false\` e \`evidence_class=exploratory\`.

Un livello \`adequate\` indica **solo una copertura sufficiente al calcolo**, non una "alta confidenza" medica. Con molte analisi esplorative, le coincidenze casuali sono attese; non riportiamo p-value o causalità. I dettagli sono consultabili dalla dashboard mobile.

**Evidenze:** AIS best-practice HRV (2023), [PDF](https://www.ais.gov.au/__data/assets/pdf_file/0013/1130260/HRV-BPG_FINAL.pdf); [Review HRV per adattamento e recupero (2025/2026)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12787763/); [Regularità del sonno (Windred et al.)](https://doi.org/10.1093/sleep/zsad253). Queste fonti motivano la lettura longitudinale e prudente, **non** validano i nostri limiti di campione, bootstrap o le bande ±2MAD.

### Audit di copertura sul Mac

Per verificare quali **campi** sono stati importati:

~~~bash
uv run --no-project --with keyring python scripts/audit_oura_coverage.py --days 65
~~~

Il report privato \`coverage_audit.json\` viene scritto accanto agli altri file elaborati nella directory \`~/Library/Application Support/OuraSelfAnalysis/enriched/\`, con permessi restrittivi. Contiene **solo contatori aggregati di presenza campi/collezioni**, non HRV, frequenza cardiaca, date/ore di sonno dettagliate, identificativi, payload o token; non viene inviato a GitHub né al cloud. Non mostra mai i risultati numerici direttamente nei log dei runner.

**Limite dell'audit:** la presenza di un campo non garantisce un segnale misurato correttamente e un totale di 35 record non garantisce 35 giorni consecutivi. Le metriche derivate mantengono controlli separati di sufficienza dei dati.

## 3. Exercise Recovery — fase esplorativa

**Origine:** `workout`, acquisito opzionalmente dallo scope `workout`, e HRV della sessione principale `sleep` il mattino dopo.

- Associazione **giorno workout D → HRV del risveglio D+1** (non alla stessa data).
- Se non sono disponibili record workout: `training_sessions` e `prior_day_training` rimangono **null** (sconosciuto), mai zero presunto.
- Se esiste storico nel periodo osservato, per giorno sono contate le sessioni registrate. Un confronto "giorno precedente con workout registrato" contro gli altri giorni viene prodotto **solo con almeno 4 osservazioni per gruppo**.
- Rapporto descrittivo delle mediane HRV, senza inferenze causali o prescrizioni sportive.

**Limiti importanti:** giorni senza record non garantiscono che non sia stato svolto sport; intensità, durata, session-RPE, orari, tipo di allenamento, sonno e altre variabili confondenti non sono corretti in questa versione. Non chiamare la differenza "tempo di recupero".

## 4. Data Quality e spiegabilità

Ogni riga include `data_quality` (assenza sonno principale, assenza HRV, orari senza offset, storico workout non disponibile). Gli insight includono:

- `id`, `title`, `summary`, `observation_window`
- `measurements` numerici, riferimenti `evidence_urls`
- `limitations`, `medical_alert=false`, `evidence_class=exploratory`.

Nessun alert medico automatico, soglie patologiche, medicina personalizzata predittiva o claim di causalità. I testi sono template deterministici costruiti da Python, **non** prompt a LLM.

## 5. Dati, privacy e conservazione

L'app conserva in SQLite record originali fuori dal repository pubblico, poi genera in modo locale:

- `health_features.csv` — una riga per giorno osservato.
- `health_insights.json` — osservazioni sintetiche, evidenze e limitazioni.

Per includerli nella pubblicazione del già esistente `daily_enriched.csv` su Drive bisogna utilizzare `local_enrichment.py ... --include-health`. La pubblicazione manda **solo file arricchiti**, non SQLite, token o serie raw di battiti cardiaci. `manifest.json` contiene SHA-256 per identificare gli artefatti analitici dell'ultima esecuzione. Sul mount Drive Desktop, l'avvenuta copia locale non prova upload cloud completato.

**Retention:** Oura pone restrizioni sulla conservazione dei dati ottenuti tramite API e di possibili derivati. Rivedere la durata di conservazione e i file/versioni Drive in base allo scopo autorizzato e ai termini applicabili. Non creare archivi perpetui per default.

## Fonti verificabili

1. **Windred et al. (2024)**, *Sleep regularity is a stronger predictor of mortality risk than sleep duration*, Sleep 47(1), zsad253. https://doi.org/10.1093/sleep/zsad253 — studio osservazionale prospettico; non valida il nostro proxy di orario.
2. **Dial et al. (2025)**, *Validation of nocturnal resting heart rate and heart rate variability in consumer wearables*, Physiological Reports 13(16), e70527. https://doi.org/10.14814/phy2.70527 — validazione vs ECG su campione piccolo (13 adulti), 536 notti.
3. **Deriving Accurate Nocturnal Heart Rate, rMSSD and Frequency HRV from the Oura Ring** (2024), Sensors 24(23), 7475. https://doi.org/10.3390/s24237475 — importanza della qualità del segnale e delle medie su periodi sufficientemente ampi.
4. **Documentazione Oura API V2** https://cloud.ouraring.com/v2/docs e **Metriche disponibili** https://partnersupport.ouraring.com/hc/en-us/articles/28571089902227-Metrics-Available-via-the-Oura-API — definizione campi e disponibilità API.
5. **Oura API and MCP Agreement**, effettivo 8 giugno 2026: https://cloud.ouraring.com/legal/api-agreement — vincoli su accesso, retention e modelli AI.

Questa letteratura motiva la scelta di trend personali e risoluzione temporale, **non** le soglie ingegneristiche minime né la validazione clinica dell'algoritmo.
