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
