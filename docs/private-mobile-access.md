# Accesso privato da telefono a Oura Insights — Tailscale Serve

**Stato verificato (2026-11-01):** dashboard Oura in ascolto solo su \`127.0.0.1:8765\`; il Mac mini esegue i test self-hosted. Il comando \`tailscale\` **non è disponibile nel PATH dell'account runner**, ma questo non dimostra che l'app Tailscale sia assente dal sistema. Nessun accesso remoto è stato abilitato.

## Principio di sicurezza

Utilizzare **Tailscale Serve**, non Funnel. Serve è accessibile ai membri autorizzati del tailnet secondo le ACL/grants; Funnel può esporre pubblicamente il servizio e non deve essere usato per dati di salute.

Per tutelare la privacy prima di pubblicare Serve:
1. Verificare che Mac mini e telefono siano autenticati sulla stessa rete privata Tailscale.
2. Controllare i membri, le condivisioni dei dispositivi e le regole ACL/grants del tailnet: chi ha accesso al Mac può potenzialmente aprire la dashboard, che non ha un'autenticazione autonoma.
3. Abilitare i certificati HTTPS nella console Tailscale quando richiesto (può richiedere un consenso interattivo).
4. Mantenere il backend legato a \`127.0.0.1\` e non utilizzare Funnel o porte esposte dal router.
5. Non pubblicare URL personali tailnet nei log Actions o GitHub pubblico.

## Procedura di installazione sul Mac e sul telefono

Su Mac: installare/attivare Tailscale dall'app ufficiale o un'installazione CLI autorizzata. Se si usa l'app macOS, potrebbe essere necessario abilitare/installare separatamente il comando \`tailscale\` nel PATH. Sul telefono: installare Tailscale e accedere **allo stesso tailnet**.

Sul Mac, in Terminale (non nell'Actions runner finché il CLI non è configurato):

~~~bash
tailscale version
tailscale status
tailscale serve status
~~~

Questi comandi consentono di verificare che il tailnet sia attivo e che **non** esistano configurazioni Serve/Funnel già in uso sul medesimo nodo/porta. Non sovrascrivere servizi esistenti; esaminare i loro utilizzi prima.

Dopo aver verificato autorizzazioni e requisiti HTTPS, configurare una sola volta:

~~~bash
tailscale serve --bg --https=443 127.0.0.1:8765
tailscale serve status
~~~

Aprire sul telefono, con Tailscale connesso, l'URL HTTPS \`*.ts.net\` che viene mostrato **localmente** dal comando. La dashboard risponderà ai percorsi già esistenti, ad esempio la vista \`/#/recovery\`.

Per disabilitare Serve senza modificare il server locale:

~~~bash
tailscale serve --https=443 off
~~~

**Non usare** \`tailscale funnel\`, \`tailscale serve --http=80\` o inoltri NAT del router.

## Criteri di verifica

- Dall'host Mac: \`http://127.0.0.1:8765/\` e \`/api/dashboard?days=7\` rispondono correttamente.
- Da telefono: HTTPS Tailscale connesso, accesso con autorizzazioni tailnet; la dashboard non è accessibile da un dispositivo non autorizzato.
- Le API rimangono read-only, con \`Cache-Control: no-store\`, CSP e nessun servizio di analytics remoto.
- L'accesso remoto non equivale a una revisione completa della sicurezza. Considerare un controllo dell'identità esplicito lato backend qualora il tailnet sia condiviso.

## Fonti ufficiali

- Tailscale Serve: https://tailscale.com/docs/features/tailscale-serve
- Sintassi aggiornata del comando: https://tailscale.com/docs/reference/tailscale-cli/serve
- Tailscale Funnel (da non utilizzare): https://tailscale.com/docs/features/tailscale-funnel
