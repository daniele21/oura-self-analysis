# Metodologia scientifica — Oura Self-Analysis MVP

**Versione:** 1.0 — 31 ottobre 2026. **Ambito:** statistiche personali descrittive, non diagnosi e non decisioni cliniche.

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
