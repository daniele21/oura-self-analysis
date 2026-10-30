# Oura Self-Analysis

A personal, experimental integration for accessing and analyzing **my own Oura Ring data** via the official [Oura API V2](https://cloud.ouraring.com/docs/authentication).

> **Project status:** registration and documentation only. There is not yet a deployed data ingestion service, scheduled synchronization, or dashboard. The repository is public; **personal health data and authentication secrets are not**.

## Oura OAuth application registration

Register an application at [Oura Developer Portal](https://developer.ouraring.com/).

| Application field | Value |
| --- | --- |
| Display Name | `Self-Analysis` |
| Description | `Private, personal Oura Ring data analysis and tracking` |
| Contact Email | Your email (enter it privately in the Oura portal) |
| Website | `https://github.com/daniele21/oura-self-analysis` |
| Privacy Policy | `https://github.com/daniele21/oura-self-analysis/blob/main/PRIVACY.md` |
| Terms of Service | `https://github.com/daniele21/oura-self-analysis/blob/main/TERMS.md` |
| Redirect URI | `http://localhost:8989/callback` |

Choose only the scopes you need. Initial candidates: `daily` (sleep/activity/readiness), `heartrate`, `workout`, `tag`, and `spo2`; these can be adjusted in the Oura app configuration and OAuth authorization. The `email` and `personal` scopes are not required for a basic personal health dashboard.

**The redirect URI must exactly match the value used by your local OAuth callback server.** Registering the URI alone does not start a server: a local callback listener is required before you can authorize this app.

## Privacy and safety

- [Privacy Policy](PRIVACY.md)
- [Terms of Service](TERMS.md)
- Never commit your client secret, OAuth tokens, exports, health records, or local databases.
- Do not upload personal health data to GitHub Issues, public logs, or pull requests.
- If cloud storage, an AI provider, or multi-user access is added later, update the policies **before** activating that processing.

## Next implementation steps

1. Register the Oura OAuth app with the URLs above.
2. Add a local OAuth authorization-code + PKCE callback flow; use secure private token storage and handle refresh token rotation.
3. Fetch the selected Oura API V2 endpoints, with pagination, retries, and idempotent local ingestion.
4. Add a local database and analytics; consider optional cloud sync only after explicit configuration and a privacy-policy update.

Oura's [authentication guide](https://cloud.ouraring.com/docs/authentication) is the source of truth for OAuth endpoints and scopes. This is an independent personal project, not affiliated with or endorsed by Oura.
