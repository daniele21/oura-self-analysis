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
