# Metodologia scientifica — Oura Self-Analysis MVP

**Versione:** 1.4 — 1 novembre 2026. **Ambito:** statistiche personali descrittive, non diagnosi e non decisioni cliniche.

## Obiettivo

Fornire misure ricostruibili da SQLite, confronto con la propria storia, copertura e motivazioni trasparenti. Non calcoliamo un "Health Score", non generiamo probabilità di malattia e non usiamo AI, modelli predittivi o training ML sui dati Oura.

L'enrichment si esegue **localmente sul Mac**. La pubblicazione su Drive è facoltativa e richiede esplicitamente `--include-health`. Non inviare i dati a un LLM, nemmeno locale, senza verificare i termini Oura.

## 1. Sleep Intelligence

**Origine:** `sleep` (sessione `long_sleep` preferita ai sonnellini); `daily_sleep` per lo score. L'API usa il campo `day` come giorno di risveglio della sessione principale: non attribuire il sonno al giorno di inizio dell'intervallo.

**Feature:** durata totale in minuti, latenza, efficienza, orari locali `bedtime_start` / `bedtime_end`, frequenza respiratoria media (`average_breath`), media mobile di 7 giorni della durata. Calcoliamo anche la deviazione standard degli orari locali di coricamento su **14 giorni di calendario**, con almeno **7 osservazioni**.

**Scelta temporale:** l'orario è trasformato in minuti rispetto a mezzogiorno locale per gestire il passaggio dalle 23:50 alle 00:10. Si conserva l'offset del timestamp. Orari senza timezone non contribuiscono alla regolarità. Viaggi, turni e sonno diurno possono invalidare il proxy.

**Limiti:** la deviazione standard dell'ora di coricamento **non è** il *Sleep Regularity Index* usato negli studi prospettici, che richiede una serie sonno-veglia a risoluzione più elevata. Non etichettare una notte come "scarsa" sulla sola base delle fasi REM/profonda stimate.

## 1b. Sleep Intelligence 2.0 — tre livelli di lettura (schema 1.3)

Le elaborazioni di sleep intelligence sono deterministiche, locali e non diagnostiche. L'obiettivo è separare **cambiamenti osservati** da possibili interpretazioni cliniche non giustificate.

### Dati e scelta della sessione

- Oura API V2 collection sleep, usando esclusivamente **type=long_sleep** come sessione principale, associata al **giorno di risveglio** del campo day. Record di tipo rest/short sleep non sono sostituiti automaticamente a un sonno notturno.
- Campi disponibili per la singola notte: total_sleep_duration, time_in_bed, efficiency, latency, awake_time, deep_sleep_duration, rem_sleep_duration, light_sleep_duration, average_hrv, lowest_heart_rate, average_heart_rate, average_breath, restless_periods, bedtime_start e bedtime_end, oltre al punteggio daily_sleep.score.
- Le durate espresse in secondi sono convertite in minuti. Valori mancanti o inverosimili non diventano zero. Orari privi di timezone non contribuiscono ai confronti su orari; il midpoint deriva dall'intervallo reale dei due timestamp quando entrambi sono attendibili.
- I tempi REM, profondo e leggero **non vengono rinormalizzati** artificialmente a sommare 100%. Se la differenza fra somma delle fasi e durata totale supera max(5 minuti, 2% della durata), viene mostrato il flag phase_totals_do_not_match_sleep.
- awake_time è etichettato **tempo sveglio stimato**; non viene attribuito automaticamente tutto al Wake After Sleep Onset (WASO) e restless_periods non viene etichettato come numero certo di risvegli.

### 1. Andamento settimanale

**Settimana recente** = ultimi sette giorni di calendario, inclusa la data del report. **Riferimento** = i sette giorni immediatamente precedenti; **nessuna sovrapposizione**. La UI etichetta esplicitamente le date, perché i periodi **non coincidono necessariamente con lunedì–domenica**.

Per ciascuna finestra con almeno **4/7 notti principali con durata disponibile**, calcoliamo medie osservate di durata, efficienza, latenza, tempo sveglio e score, più deviazione standard della durata. Ogni metrica ha anche il suo numero di dati validi: se è inferiore a 4, la relativa media resta nulla. Il confronto tra settimane viene calcolato solo se entrambe superano le soglie minime; sono requisiti di copertura ingegneristici, non soglie cliniche.

L'orario di addormentamento e del risveglio è sintetizzato con una **deviazione standard circolare in minuti**, adatta agli orari distribuiti vicino alla mezzanotte; è un proxy circadiano e **non** lo Sleep Regularity Index (SRI) della letteratura, che richiede dati sonno/veglia a granularità temporale maggiore.

### 2. Confronto di ogni giorno

Per ogni notte principale del periodo visualizzato calcoliamo:
- **Delta giorno precedente:** misura della notte D meno la misura del **giorno di risveglio D−1 esatto**. Una notte mancante non è sostituita dalla più vicina disponibile.
- **Delta vs sette precedenti:** misura della notte D meno **media delle notti osservate in D−7…D−1**, purché ne siano presenti almeno 4 per quella specifica metrica. Il giorno D non entra mai nella propria baseline.
- Confronti disponibili per durata, efficienza, latenza, tempo sveglio, score, REM e profondo. Il delta efficienza è espresso in **punti percentuali**, non variazione percentuale relativa.

Nessun delta giornaliero prova un miglioramento o peggioramento clinico, soprattutto per la suddivisione delle fasi.

### 3. Dettaglio di una singola notte

Il selettore permette di scegliere una sessione principale all'interno dei 7/30/90 giorni visualizzati. Il dettaglio mostra in modo navigabile sonno totale, tempo a letto, orari locali, midpoint, efficienza, latenza, tempo sveglio, sonno leggero/REM/profondo, HRV, FC minima/media, respirazione e irrequietezza **soltanto quando questi campi sono presenti**. Le fasi sono frazioni delle durate fornite dal wearable e possono non sommare esattamente al totale.


### Fasi del sonno — grafico longitudinale Leggero/Profondo/REM (v1.4)

Il grafico **Sonno → Fasi del sonno nel tempo** usa le durate Oura V2 \`light_sleep_duration\`, \`deep_sleep_duration\`, \`rem_sleep_duration\` convertite in minuti, **solo da sessioni \`type=long_sleep\`** collegate al giorno di risveglio. L'analisi è deterministica e locale (\`sleep_stage_trends.py\`) e riutilizza il risultato già prodotto da \`sleep_intelligence.py\`.

- **Composizione (7/30 giorni):** tre componenti impilate per ogni notte osservata. Notti senza sessione principale o con fasi mancanti/incoerenti hanno una lacuna esplicita, NON tre barre a zero. Ogni componente rappresenta una durata in minuti o la rispettiva quota sul totale del sonno osservato.
- **Composizione a 90 giorni:** blocchi non sovrapposti di 7 giorni di calendario dal primo giorno della finestra (ultimo blocco potenzialmente parziale), con **media dei minuti per notte qualificata**, non somma del sonno per settimana. Ogni blocco richiede almeno quattro notti valide, inclusi i blocchi parziali; etichette e tabella mostrano n giorni di calendario e n notti valide.
- **Trend 7 giorni:** media mobile delle fasi su sette giorni di calendario per ogni data, utilizzando anche i sei giorni antecedenti all'intervallo visibile quando disponibili. Ogni punto richiede almeno quattro notti qualificate nella finestra di sette giorni; i punti insufficienti rimangono null, senza interpolazioni.
- **Percentuale giornaliera:** durata fase / durata totale del sonno nella notte. **Percentuale settimanale:** somma durate della fase / somma dei totali del sonno nelle notti qualificate (media pesata rispetto alla durata, non media aritmetica delle percentuali delle notti).
- **Confronto 7 vs 7 giorni:** medie per fase e differenza di durata (minuti) o composizione (punti percentuali) solo se ciascun periodo contiene almeno quattro notti qualificate, senza sovrapporre le finestre.
- **Qualità:** ogni notte richiede sessione principale, durata totale valida e tre durate di fase presenti; la loro somma deve concordare con \`total_sleep_duration\` entro \`max(5 min, 2% del totale)\`. Non si ricostruiscono fasi mancanti, non si sottrae il tempo sveglio per colmare differenze, non si rinormalizza artificialmente a 100% e non si deduce insonnia da notti non misurate.
- **UX accessibile:** colori e etichette distinti, grafico con asse in minuti o %, cursore da tastiera per leggere data e valori, tabella alternativa e copertura del campione esplicita.

I dati sulle fasi del sonno sono **stime da wearable**: confronti a breve termine possono contenere rumore di classificazione e non implicano miglioramenti clinici. La quota di REM/profondo presa isolatamente non misura la qualità complessiva del sonno. Le soglie n≥4 e coerenza 2% sono controlli di prodotto/ingegneristici, **non soglie diagnostiche**.

### Evidenze e interpretazione

- **Svensson et al. (2024), Sleep Medicine 115:251–263**, https://doi.org/10.1016/j.sleep.2024.01.020: validazione Oura Gen3 con PSG in 96 persone; buona concordanza per metriche globali, maggiore incertezza nelle fasi e nella rilevazione della veglia.
- **Windred et al. (2024), Sleep**, https://doi.org/10.1093/sleep/zsad253: coorte prospettica sulla regolarità sonno-veglia; risultati osservazionali, non valida il nostro proxy di orario né fornisce rischi individuali.
- **Oura API V2**, https://cloud.ouraring.com/v2/docs: definizione campi e disponibilità API.

Le due osservazioni narrative weekly e latest night contengono misure, numerosità, alternative e limiti. Il modello evita diagnostica, promesse di causalità e falsi indicatori di sleep debt.

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

## 3b. Exercise Recovery 2.0 — risposta nei risvegli D+1, D+2, D+3

**Versione dell'engine: 1.2**, analisi esplorativa. Questo modulo è una lettura osservazionale della fisiologia dopo un workout **registrato**: non valida né predice il recupero muscolare, atletico o clinico.

### Schemi API e feature

Dal record Oura V2 \`workout\` leggiamo esclusivamente i campi strutturati:

- \`day\`, \`activity\`, \`intensity\`, \`start_datetime\`, \`end_datetime\`, \`source\`.
- **Durata** = \`end_datetime - start_datetime\` tenendo conto dei fusi; valida solo con entrambi i timestamp timezone-aware, durata \`>0\` e non superiore a 24h. Eventi senza durata valida restano classificati come **durata sconosciuta**, mai 0.
- **Intensità Oura** = \`easy/moderate/hard\` se disponibile. **Non è session-RPE**: non moltiplichiamo arbitrariamente la durata per questi livelli, né ne ricaviamo un \`training load\` pseudo-clinico.
- **Tipologia** = gruppi conservativi (cross-training/HIIT, sport con racchetta, forza, corsa, bicicletta, camminata, altre attività). Eventi con attività non riconosciuta vanno in «altre attività», senza inventare CrossFit/Padel dalla \`label\` libera.
- \`label\`, ID e orari esatti del workout **non sono esportati nella dashboard**. Salviamo riepiloghi giornalieri aggregati ed eventuali curve di mediana, non un feed di record grezzi.

Il **giorno D** è il giorno di calendario Oura del workout; D+1, D+2 e D+3 sono i **giorni di risveglio** successivi. Non rappresentano esattamente 24/48/72 ore fisiche dall'ora di fine workout. La differenza riportata è: \`outcome al risveglio D+k − outcome al risveglio D\`, con \`k=1,2,3\`. Il risveglio D è un **riferimento di giornata**, non una baseline pre-workout verificata individualmente.

Gli outcome sono HRV notturna, **FC minima notturna** e minuti di sonno. Per ogni metrica/lag mostriamo \`n\` di coppie valide e la loro differenza mediana solo con almeno **4** coppie. Se mancano dati fisiologici, non riempiamo con zeri o valori interpolati.

### Eventi isolati vs sessioni sovrapposte

- **Coorte isolata:** giorno D senza altri workout *registrati* nei 3 giorni prima o dopo. Gli eventi degli ultimi 3 giorni sono esclusi perché D+3 non è osservabile.
- **Coorte osservazionale:** tutte le giornate con workout registrati per le quali esiste almeno una metrica al risveglio D; **include** allenamenti vicini. Serve per evitare che frequenze elevate di sport producano un report vuoto. È meno interpretabile.
- La dashboard preferisce la coorte isolata se ha almeno quattro giornate; altrimenti, se ci sono almeno quattro eventi nella coorte osservazionale, mostra esplicitamente il **rischio di sovrapposizione**.
- Le analisi per attività/intensità richiedono almeno quattro giornate in quella categoria e sono esplicitamente osservazionali.

La presenza di **nessun record workout** non implica riposo. Gli sport non registrati restano possibili. Non c'è correzione di intensità reale, stress, dieta, qualità del sonno, orari, stagionalità, trend precedenti o altre variabili confondenti. La differenza osservazionale **non identifica causalità** né il «tempo di recupero». Con campioni ridotti, autocorrelazione e allenamenti ripetuti, non calcoliamo p-value o intervalli di confidenza fittizi.

### Evidenze e interpretazione prudente

- Oura V2 API workout schema: [documentazione Oura](https://cloud.ouraring.com/v2/docs).
- Review narrativa HRV: [Monitoring Training Adaptation and Recovery Status in Athletes Using HRV](https://pmc.ncbi.nlm.nih.gov/articles/PMC12787763/), sottolinea la variabilità temporale e l'importanza di medie e CV.
- [Guidelines for rigor and reproducibility of HRV within human cardiovascular research (2026)](https://doi.org/10.1152/ajpheart.00041.2026): la ricerca non sostiene l'equivalenza automatica wearable HRV = misura di recupero.
- [Review/meta-analisi su allenamento intenso e HRV (2025)](https://doi.org/10.1007/s10286-024-01103-7) riguarda prevalentemente risposte nell'immediato post-esercizio; **non** valida la nostra curva notturna D+1/2/3.

Queste fonti motivano il monitoraggio longitudinale e le cautele, non validano i requisiti minimi, l'isolamento ±3 giorni né gli effetti individuali stimati.


## Cardiovascular Intelligence 2.0 — relazioni HRV/FC e sonno

**Implementazione:** \`cardio_context_analysis.py\`; valori mostrati nella sezione Recupero e, soltanto quando soddisfano i controlli esplorativi, come massimo due nuovi insight.

Quattro confronti **predefiniti prima di osservare i risultati**:
1. Durata del sonno ↔ HRV media notturna.
2. Durata del sonno ↔ FC minima notturna.
3. Efficienza del sonno ↔ HRV media notturna.
4. Efficienza del sonno ↔ FC minima notturna.

La data è quella di *risveglio* Oura, quindi sono misure dello **stesso episodio di sonno**, non "sonno che causa HRV/FC" o previsione dell'andamento successivo. Si utilizzano soltanto date distinte con coppie valide, massimo **90 giorni di calendario** e almeno **21 notti appaiate in quattro settimane distinte**. Le serie più corte e i valori costanti producono risultato assente/indeterminato.

La metrica è **Spearman rho** con gestione esplicita dei ranghi pari. Sensibilità: ricalcolo togliendo una settimana di calendario alla volta (quota di risultati che mantengono il segno) e correlazione fra segnali centrati entro ciascuna settimana (almeno 4 settimane con 3+ coppie). Le categorie \`weak_observed\`, \`unstable\`, \`consistent_exploratory\` ecc. sono etichette **di presentazione, non test clinici né significatività statistica**. In particolare rho ±0,2 e coerenza 75% sono euristiche ingegneristiche; nessun p-value, intervallo causale, previsione, score di salute o screening.

**Limitazioni:** misure dallo stesso dispositivo e dalla stessa notte, fattori confondenti (allenamento, alcol, stress, malessere, orari, routine), autocorrelazione tra notti, misure mancanti, campione piccolo e sensibilità a singole settimane. Il solo effetto di un fattore non può essere isolato. Per una fase successiva valutare diario di fattori contestuali *volontario*, previa verifica di privacy/retention, e disegni N-of-1 prespecificati.

### Integrazione allenamento

Si sfrutta il già esistente \`exercise_recovery.py\`: le curve per attività e intensità Oura vengono ora mostrate in Attività anche a livello di sottogruppo, se ci sono almeno 4 giornate osservate. I dati possono comprendere allenamenti ravvicinati, attività non registrate e durate non disponibili. Il confronto D+1/2/3 rappresenta **giorni di risveglio** e non ore esatte dopo il workout. Intensità Oura easy/moderate/hard **non equivale** a session-RPE. Non deduciamo causa, performance o tempo di recupero.

### Intranotte — FC minima e dispersione dei profili

Nel dettaglio \`cardio_night_comparisons.py\`, ogni intervallo da 30 minuti è una mediana di almeno 4 campioni validi nominalmente a 5 minuti. Il "minimo" è **la mediana minima di un intervallo qualificato**, non il battito minimo di Oura né il minimo HR in assoluto. Richiede almeno 4 bin qualificati. Il tempo indicato è l'inizio dell'intervallo dal coricamento. La dispersione intranotte è \`P90−P10\` delle mediane qualificate e richiede almeno **8 bin** per singola metrica. Mancanze e intervalli non standard non vengono riempiti/interpolati. Nessuna classificazione fisiologica o clinica è prodotta.

**Fonti metodologiche:** https://doi.org/10.1152/ajpheart.00041.2026 e https://www.ausport.gov.au/ais/position_statements/heart-rate-variability. Le fonti sostengono la prudenza nella lettura longitudinale e con potenziali confondenti, **non validano** i nostri coefficienti/limiti minimi né l'utilità clinica di questi confronti.

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
