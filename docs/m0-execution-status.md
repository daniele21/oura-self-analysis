# M0 — Stato di implementazione (2026-11-01)

Milestone: fondazioni UX e audit privato delle serie cardiovascolari, NON le nuove curve intranotturne.

## Implementato

- Cinque sezioni in sidebar e bottom navigation: Oggi, Sonno, Recupero, Insight, Attività. La vecchia voce Trend non compare più nella navigazione.
- Prima pagina Recupero alimentata da dati notturni reali: HRV e FC minima, trend, baseline 7 vs 28 giorni precedenti. Selezione notte e passaggio da Sonno a Recupero mantenendo la data.
- Routing locale con soli nome sezione e giorno selezionato, nessun valore sanitario nell'URL.
- Dizionario delle metriche in cardio_metric_registry.py: distinzione tra HRV media, FC minima, FC media e serie HR/HRV.
- Audit locale in scripts/audit_cardio_series.py: legge solo sessioni long_sleep e verifica presenza, struttura PublicSample, intervalli, campioni null e copertura in modo aggregato; nessun dato individuale è stampato o pubblicato.
- Test offline delle caratteristiche UX, della struttura delle serie e della privacy. Test specifici per CLI diretta e modulo Python.
- Gate aggiuntivo: conteggio dei giorni con entrambi i canali e almeno 24 campioni validi per canale, copertura almeno 75% e intervallo di 300 secondi. Stato locale: ready (7+ giornate), limited (1-6), insufficient (0). Queste sono convenzioni tecniche per avviare un prototipo, NON soglie mediche.

## Verifica su Mac mini

Il workflow self-hosted in local-runner-infra esegue l'audit sui dati già presenti su Mac senza richiedere nuovi scope Oura. Il report dettagliato rimane privato in ~/Library/Application Support/OuraSelfAnalysis/private-audits/cardio-series-coverage.json. Il workflow comunica soltanto uno stato categorico sulla presenza di entrambi i canali.

Il deploy non abilita Tailscale Serve né alcuna porta pubblica. Il servizio della dashboard resta legato a 127.0.0.1:8765.

## Gate per M1

- Verifica del risultato dell'audit: se le serie sono assenti, prima occorre chiarire disponibilità e acquisizione autorizzata, senza inferire che i dati esistano.
- Adapter sample per timestamp/interval/items con null, duplicati, DST e limiti di dimensione.
- Grafici HR e HRV sincronizzati con aggregazione per analisi su finestre sufficientemente lunghe e rappresentazione esplicita dei dati mancanti.
- Endpoint read-only per singola notte, senza caricare le serie di 90 notti in una sola richiesta.
- Dettaglio notturno accessibile da Sonno e Recupero, metodo e qualità sempre visibili.

## Vincoli

L'accordo Oura API/MCP in vigore dall'8 giugno 2026 (https://cloud.ouraring.com/legal/api-agreement) prevede limiti su retention, uso per modelli AI e sviluppo di prodotti che replicano Oura. I dati API non vengono trasmessi a LLM e il progetto resta locale e personale; questo non equivale a una valutazione di conformità legale. Prima di estendere storico e distribuzione, definire retention e cancellazione coerenti con i termini.

Roadmap completa: docs/cardiovascular-intelligence-ux-roadmap.md.
