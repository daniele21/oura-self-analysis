# Privacy Policy — Oura Self-Analysis

**Last updated: 31 October 2026**

## Scope

This is a non-commercial personal application for the repository owner to access and analyze **their own** Oura Ring records. It is not a hosted or publicly offered service, and does not collect third-party Oura accounts.

## Data and purposes

After account authorization, the local Mac client requests only the Oura API categories granted through OAuth, such as daily sleep, readiness, activity, HRV, workouts and SpO₂. These may include sensitive health information. Processing is for personal local recordkeeping and descriptive trend analysis; it does not provide medical advice or employ AI models.

Local enrichment produces daily scores, sleep-stage duration, heart rate/HRV, activity counts, descriptive moving averages and differences from historical baselines. Missing values remain unknown rather than being imputed.

## Local storage and credentials

Original API records are stored on the owner's Mac in a local SQLite database outside this public repository. API client credentials, access tokens and refresh tokens are stored in **macOS Keychain**, not in the repository.

The local enrichment exports a daily CSV and manifest in the Mac's application-support directory. The optional evidence-informed analytics module also produces a **health_features.csv** file with daily physiological aggregates and a **health_insights.json** file with descriptive observations and scientific references, computed entirely on the Mac. These two additional files remain local unless the owner explicitly uses the `--include-health` option when publishing to Drive. The tool does not use external AI or analytics services, and does not upload raw SQLite records, API request logs or authentication credentials to Google Drive.

## Optional Google Drive storage

Google Drive integration is **off by default**. If the owner explicitly chooses a destination folder and runs the publish or automated-run command, the tool copies the enriched daily CSV and its manifest to the selected private Drive destination (Google Drive for desktop or an individually authorized rclone remote). Only if `--include-health` is explicitly selected does it also copy the two additional analytical files.

Google Drive for desktop (or rclone, if configured) then synchronizes those files to the owner's Google account, subject to Google's own privacy policies and account sharing settings. This is cloud storage of personal health-related derivatives. **The current integration does not provide end-to-end encryption of the CSV.** The owner must ensure the destination folder remains private and must evaluate whether Google Drive meets their confidentiality requirements.

## Retention and deletion

The optional Drive export contains one overwritten rolling snapshot of **up to 90 days**, with 30 days as the default. A snapshot is not a permanent append-only history. Google Drive may retain earlier revisions of overwritten files under its own policies. The owner controls deletion of exported files and any Drive revisions from their Google account.

The local SQLite database is not automatically pruned by this version; the owner must periodically evaluate retention and delete data when it is no longer necessary. Oura's [API/MCP Agreement](https://cloud.ouraring.com/legal/api-agreement) restricts keeping API-derived data longer than strictly needed for the authorized purpose, including enriched derivatives. The 30/90-day window is a technical bound, **not a guarantee of compliance** in every situation.

Revoking app authorization from Oura stops future authorized API requests but does not automatically erase local or already-uploaded copies. To fully stop and remove copies, uninstall the macOS schedule, delete the local database and enrichment files, delete Google Drive copies/revisions, and revoke Oura OAuth authorization.

## Security, sharing and contact

Do not commit secrets, SQLite databases, exported files, or personal health data to GitHub. Never share the destination Drive folder publicly. Only the account owner is intended to access the data. For project questions, contact the maintainer through [GitHub](https://github.com/daniele21) without publishing personal health or account information.

Oura data is accessed through Oura's own systems and Google Drive synchronization (if enabled) is provided by Google. This is an independent project, not affiliated with or endorsed by Oura. This document will be revised before enabling any materially different data processing.
