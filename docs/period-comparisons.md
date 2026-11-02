# Period Comparisons — Sonno e Recupero (v1)

## Obiettivo e perimetro
Un solo motore deterministico (`period_comparisons.py`) per comparare quantità,
continuità e regolarità del sonno, HRV e FC minima con finestre personali
calendario **non sovrapposte**. Non deduce cause, stati di malattia, recupero
muscolare o benefici clinici.

## Finestre
Il giorno D è **il giorno di risveglio Oura**, incluso nel periodo recente.
- **7v7:** D−6…D contro D−13…D−7.
- **7v28:** D−6…D contro D−34…D−7.
- **28v28:** D−27…D contro D−55…D−28.

Soglie per metrica con valore osservato:
- Sonno: almeno 4/7 per periodi di 7 giorni; 14/28 per baseline 7v28;
  21/28 per entrambe le finestre 28v28.
- Recupero: almeno 5/7 e 14/28 per 7v28; 5/7 e 4/7 per 7v7
  (dove il riferimento di sette giorni richiede 4 notti);
  21/28 per 28v28.
- Le soglie sono criteri ingegneristici di **completezza**; non descrivono
  accuratezza clinica né significatività statistica.
- I record di score senza sessione `type=long_sleep` NON contribuiscono
  ai confronti del sonno. I sonnellini non riempiono le lacune.

## Aggregazioni
- Sonno: **medie** per durata, efficienza, latenza, minuti svegli, fasi e
  Sleep Score; differenze in minuti, punti percentuali o punti score.
- Regolarità del sonno: **deviazione standard circolare** di orari locali
  di coricamento/risveglio, non Sleep Regularity Index.
- Recupero: **mediane** per HRV notturna, FC minima, durata del sonno e
  frequenza respiratoria.
- Delta assoluto = valore recente − riferimento. Delta percentuale solo
  per metriche numeriche positive; non per deviazione standard circolare.
- Dispersione robusta storica = 1,4826 × MAD; scostamento standardizzato
  = delta / dispersione solo se la dispersione è positiva.
  Nessuna banda MAD è una soglia medica.
- Persistenza = notti misurate dalla stessa parte del centro precedente
  nella direzione del delta, più sequenza massima di giorni **calendario**
  consecutivi. Notti mancanti interrompono la sequenza.
  Questo NON misura la probabilità del cambiamento.

## Sovrapposizioni del grafico
Grafico e tabella condividono metrica e periodo selezionati. Le curve
utilizzano **solo** i record giornalieri già resi visibili dal browser
nella finestra 7/30/90 giorni scelta.

- 7v7: notte per notte, con giorno della settimana allineato.
- 7v28: una notte per ciascuno dei sette giorni recenti contro
  media/mediana della stessa posizione settimanale nelle quattro
  settimane precedenti; il punto baseline richiede almeno 2/4 notti.
- 28v28: quattro blocchi settimanali non sovrapposti per ciascun periodo;
  ogni punto richiede almeno 4/7 osservazioni.
- Per regolarità dell'orario, mostrare solo le deviazioni standard
  aggregate: non esiste una curva giornaliera equivalente.
- Se il periodo storico non è contenuto nella vista selezionata, mostrare
  le **statistiche aggregate** ma non dati giornalieri più vecchi.
  La UI offre l'azione esplicita per passare a 30 o 90 giorni.
- Punti mancanti sono discontinuità, non zeri o interpolazioni.

## Livelli di interpretazione
1. Panoramica: variazione nelle metriche principali.
2. Comparazioni: entità, numerosità e copertura per ogni metrica.
3. Persistenza: supporto osservato nella stessa direzione, senza causalità.
4. Dettaglio: grafico sovrapposto e tabella; da qui alle viste quotidiane
   e ai profili cardiaci notturni già esistenti.

Non ordinare tutte le metriche per un numero di "importanza" costruito
sommando unità di misura diverse. HRV e FC vanno letti congiuntamente,
non come una diagnosi. Le fasi REM/deep/light sono stime Oura e
più incerte della durata globale del sonno; la dashboard non assegna
un punteggio "miglior REM".

## Privacy e test
La risposta `sleep_intelligence.comparisons` e quella
`period_comparisons` contengono solo aggregati per finestra.
La selezione 7 giorni non esporta notti individuali da D−7…D−55,
pur potendo derivare medie storiche sul Mac.
Nessuna nuova autorizzazione, invio dati ai servizi AI, endpoint di
scrittura o salvataggio delle curve di confronto.
Test solo su SQLite e serie **sintetici**.

Eseguire:
```bash
python3 -m unittest discover -s tests -v
```

## Limiti aperti
- Il confronto dei periodi non corregge per autocorrelazione,
  allenamenti, alcol, malessere, farmaci, stagionalità o qualità del sensore.
- Periodi di durata diversa (7v28) hanno variabilità stimata diversa.
  La curva per weekday del riferimento è descrittiva, non una
  proiezione individuale.
- Le finestre si ancorano alla data corrente, anche se non è ancora
  disponibile la notte conclusa quel giorno: la copertura lo rende visibile.
- Futuro: ranking esplicabile delle differenze solo dopo valutazione
  dei falsi positivi su dati sintetici e una revisione utente di
  esempi di insight reali (eseguita privatamente sul Mac).

## Audit qualitativo locale (v1.1)
La media settimanale può aumentare mentre il segmento più recente peggiora:
per ogni metrica **non-oraria** viene quindi aggiunta una lettura prefissata
"ultime 3 notti vs prime 4 notti" **della stessa settimana**. La finestra
recente deve avere tutte le tre notti valide e la prima parte almeno 3/4:
il dato incompleto non viene presentato come zero. L'aggregazione resta
coerente con la metrica (media sonno, mediana FC/HRV).
`opposes_weekly_comparison` confronta esclusivamente i SEGNI della
differenza interna alla settimana e del 7v7, non misura causalità,
effetto clinico o probabilità del cambiamento.

Le nuove comparazioni sono ancorate **all'ultimo giorno con misura
utilizzabile** per ciascuna area, e mostrano `as_of_day`. Se il sync è
datato, la UI lo dice esplicitamente; non suggerisce che le misure
rappresentino la notte odierna. Le altre analisi storiche che usano
la data del report mantengono i loro periodi dichiarati: non devono
essere confuse con questo comparatore.

### Procedura ripetibile
L'audit dettagliato è progettato per essere eseguito **solo sul Mac
dell'utente**, non su un runner pubblico o un repository GitHub.
Legge SQLite senza scrittura, usa l'analytics engine locale e salva
solo aggregati con permessi file `0600`:

```bash
cd ~/Projects/oura-self-analysis
git pull --ff-only
python3 scripts/validate_oura_insights.py
```

Il file privato è
`~/Library/Application Support/OuraSelfAnalysis/enriched/quality_review.json`.
Lo stdout restituisce esclusivamente contatori dei controlli e non
stampa date, HRV, FC o identificativi personali. Un'esecuzione con
`AUDIT_COMPLETED` significa **consistenza strutturale** delle differenze,
non che gli insight siano clinicamente validati.
Non caricare il report su Actions, GCS pubblico o nel repository.
Usare uno snapshot del ring aggiornato e almeno 56 notti qualificate
per valutare integralmente 28v28 (copertura minima 21/28 per periodo).

Il repository pubblico Oura non è incluso automaticamente nella
allowlist di `daniele21/local-runner-infra`; l'audit privato non
modifica i permessi di esecuzione del Mac.

## Parità tra dashboard e insight (v2)

L'audit locale ora confronta le viste API 7/30/90, i dettagli delle notti, le metriche strutturate delle schede Insight e i periodi storici. Segnala valori contraddittori senza stampare dati sanitari nei log. In caso di sincronizzazione in ritardo, la lettura storica 28v28 parte dall'ultima notte disponibile e recupera l'intera baseline necessaria dal database locale.

In Oggi e Insight compaiono al massimo due approfondimenti editoriali predefiniti: inversione della durata del sonno fra settimana e ultime tre notti, e variazioni HRV/FC minima di segno opposto. Copertura, persistenza e ampiezza minima evitano suggerimenti generati da differenze trascurabili; sono filtri di presentazione, **non soglie mediche**. L'assenza di una scheda non indica che sonno e recupero siano ottimali.

Eseguire solo sul Mac: `python3 scripts/validate_oura_insights.py`. Il JSON privato contiene aggregati e codici di controllo, senza osservazioni individuali. Non va pubblicato nei log, artifact CI o repository.
