# M1 — Profili notturni HR e HRV sincronizzati

## Stato e scopo

Prima implementazione deterministica e privata di due grafici HR/HRV sincronizzati per **una sola notte alla volta**. Le serie provengono da `sleep.heart_rate` e `sleep.hrv` già importate, senza nuove richieste OAuth né chiamate a servizi esterni.

## Metodo

- Nel database SQLite viene scelta soltanto la sessione `type=long_sleep` del giorno di risveglio richiesto. I sonnellini non sostituiscono il sonno principale.
- Ogni canale è ricostruito indipendentemente usando `PublicSample.timestamp + index × interval`. Tutti i confronti temporali usano istanti UTC consapevoli del fuso, non la posizione degli elementi nelle liste; il cambio ora legale/solare è gestito.
- La finestra considerata va da `bedtime_start` a `bedtime_end`, escluso il limite finale. I campioni esterni a questa finestra non entrano nella curva.
- Vengono prodotti bin di **30 minuti** dal momento di coricarsi. Un bin ha una mediana soltanto se ci sono **almeno quattro misure valide** per quella metrica, e l'intervallo nominale del campione è **300 secondi**. Sono criteri ingegneristici per la leggibilità delle curve, NON soglie validate per diagnosi.
- I valori mancanti, booleani, non finiti, implausibili, e i bin insufficientemente popolati diventano `null`, senza interpolazione; punti separati da un gap non sono collegati dalla linea.
- HR e HRV condividono soltanto l'asse del tempo trascorso dal coricamento; i due valori hanno unità e scale verticali distinte. Non confrontiamo gli assi Y direttamente.
- La copertura dell'intera notte è stimata come numero di campioni validi / numero teorico di campioni ottenibili nell'intervallo coricamento-risveglio: in questo modo serie brevi non risultano artificialmente complete. Viene distinta dalla frazione di valori validi tra i soli campioni presenti.
- Nessuna interpretazione fisiologica viene prodotta a partire da un singolo punto di 5 minuti; le curve sono descrittive e non permettono di diagnosticare stress, malattie, problemi cardiovascolari o recupero atletico.

## UX/UI

- `Recupero` → selezione notte → due grafici HR e HRV con **stesso tempo trascorso**. Il range 7/30/90 della panoramica resta indipendente dalla baseline personale 7/28.
- Slider usabile da tastiera, con cursore verticale sincronizzato e valori delle due metriche per ogni intervallo.
- Tabella numerica alternativa ai grafici, pannello di copertura separato per HR/HRV, spiegazioni dei dati mancanti.
- Da `Sonno` si raggiunge lo stesso dettaglio con la data già selezionata. Il percorso contiene solo sezione e data di risveglio.
- In caso di notte assente o curva inutilizzabile, si mostra uno stato vuoto esplicito senza numeri inventati.

## Backend privato e limiti

`GET /api/v2/recovery/night?day=YYYY-MM-DD` restituisce soltanto una notte negli ultimi 90 giorni, con un massimo di 48 bin e conteggi di copertura. Nessun record ID, payload completo, array grezzo di misure o token viene mandato al browser. Richieste duplicate, date inesistenti, parametri extra, richieste troppo ampie e host esterni vengono respinti. Il server resta vincolato a `127.0.0.1`, le API usano `Cache-Control: no-store`, senza analytics esterni.

Limiti in vigore: massimo 16 record di sleep per giornata, massimo 350 KB per record e 600 campioni per canale; file SQLite aperto in sola lettura. Nessuna conservazione aggiuntiva sul disco, cache di API o processi LLM.

## Test

Il test offline `tests/test_cardio_night_profiles.py` usa esclusivamente dati sintetici: formati validi/non validi, null, valori anomali, offset, DST, sessioni rest e long_sleep, copertura parziale, allineamento temporale, endpoint read-only, query e host invalidi.

## Sviluppi successivi

Confronto profili D−1 e sette notti precedenti usando tempo trascorso dal coricamento e numerosità comparabili; strumenti di differenze prima/seconda metà notte soltanto con campioni sufficienti; metadati di qualità esplicitati nei nuovi insight. Non aggiungere interpretazioni fisiologiche non validate.

## Vincoli Oura

L'accordo API Oura del 2026 limita conservazione, riuso e dati passati a modelli AI, e include restrizioni sulla creazione di servizi che replicano Oura. Il progetto rimane uso privato su dispositivi dell'utente, ma la conformità richiede una valutazione specifica. Riferimento: https://cloud.ouraring.com/legal/api-agreement

Roadmap: [Cardiovascular Intelligence UX](cardiovascular-intelligence-ux-roadmap.md).


## M1b — Confronto con notte precedente, sette notti precedenti e metà notte (1 novembre 2026)

Il modulo \`cardio_night_comparisons.py\` estende l'endpoint esistente \`GET /api/v2/recovery/night?day=YYYY-MM-DD\` con la chiave \`comparison\`. Non espone record ID, timestamp grezzi o misurazioni di 5 minuti; restituisce esclusivamente mediane dei bin da 30 minuti e numerosità. Legge sul Mac **solo il giorno richiesto e i sette giorni di risveglio precedenti**; niente nuove autorizzazioni, invii al cloud o storicizzazioni.

- **D−1 esatto:** il confronto della notte scelta considera esclusivamente il precedente giorno di calendario di risveglio, non l'ultima notte disponibile. Se D−1 manca, i valori restano null.
- **D−7…D−1:** in ogni bin da 30 minuti dal coricamento la mediana viene calcolata usando soltanto le notti precedenti con un bin qualificato alla **stessa posizione temporale**. È necessario almeno un gruppo di **4 notti valide per bin** (non semplicemente quattro notti complessive); se mancano, la mediana non è disponibile.
- **Scostamenti:** per HR e HRV, calcoliamo la differenza bin-per-bin fra notte scelta e riferimento soltanto dove entrambe hanno valori; mostriamo la **mediana delle differenze** se esistono **almeno 4 coppie di bin**. La media delle differenze non è equiparata alla differenza fra valori medi di sessione Oura.
- **Due metà della notte:** i bin vengono assegnati alla prima o seconda metà del **tempo a letto** mediante il centro dell'intervallo. La mediana e la differenza seconda−prima richiedono almeno **2 bin qualificati per metà per metrica**. Non identificano le fasi del sonno e non sono indicatori validati di recupero.
- **Durate diverse:** il confronto usa il tempo trascorso dall'inizio della sessione, non le 23:00 o l'ora locale. Se una notte precedente è più breve, gli intervalli non esistenti rimangono null. Nessuna interpolazione.
- **Qualità:** mancanza di D−1, notti insufficienti, valori invalidi, sessioni storiche non leggibili e lacune sono gestiti senza inventare misure o dichiarazioni di significatività statistica.

La UI include un selettore Solo notte / Notte precedente / Sette notti, due curve separate HR/HRV con riferimento tratteggiato, legenda, cursore sincronizzato, differenze numeriche con numerosità e tabella accessibile. Nessuna differenza viene etichettata automaticamente come miglioramento o peggioramento.

I criteri 4 notti, 4 coppie di intervalli e 2 bin per metà sono **soglie di completezza ingegneristiche**, non convalidate clinicamente. Il confronto è descrittivo e può dipendere da durata della notte, esercizio, variabilità delle fasi, stress, farmaci, qualità del sensore e altri fattori non misurati.

**Test sintetici:** \`tests/test_cardio_night_comparisons.py\` copre finestre disgiunte, mancata D−1, settimana incompleta, differenze di durata, metà notte, dati storici invalidi e privacy del JSON. L'API eredita le protezioni read-only, loopback, controllo Host e \`Cache-Control: no-store\`.
