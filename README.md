# Oura Self-Analysis

Personal Oura Ring data pipeline: **Oura API → local SQLite → local deterministic enrichment → optional Google Drive Desktop sync**. No cloud runtime, external AI, or credentials stored in this public repository.

## 1. Connect and sync Oura

Requires macOS, Python 3.10+, [uv](https://docs.astral.sh/uv/) and Oura API access. Configure the OAuth callback in the Oura portal as http://localhost:8989/callback.

~~~bash
git clone https://github.com/daniele21/oura-self-analysis.git
cd oura-self-analysis
uv run --no-project --with keyring python oura_self_analysis.py login
uv run --no-project --with keyring python oura_self_analysis.py sync --days 30
uv run --no-project --with keyring python oura_self_analysis.py report
~~~

Enter your Oura Client ID and Secret only in the **local Terminal prompt**. OAuth tokens and credentials are stored in macOS Keychain, never committed. The database is:

    ~/Library/Application Support/OuraSelfAnalysis/oura.sqlite3

The original collector handles scopes with Oura's extapi: prefix, pagination, token refresh, and idempotent upserts.

## 2. Enrich your data locally

~~~bash
uv run --no-project --with keyring python local_enrichment.py enrich --days 30
~~~

Two files are generated **outside the repository**:

    ~/Library/Application Support/OuraSelfAnalysis/enriched/daily_enriched.csv
    ~/Library/Application Support/OuraSelfAnalysis/enriched/manifest.json

The CSV has one row for each available day in the rolling 30-day window (configurable 1–90 days). It contains sleep/readiness/activity scores, steps, sleep duration by stage (minutes), sleep efficiency, nighttime HR/HRV, temperature deviation, SpO₂ (if present), rolling 7-day means, differences from the previous 28-day baseline, and missing-source indicators. Means require at least 3 observations (7 days) or 7 observations (28 days), respectively. Missing values remain blank, never zero. The main overnight sleep takes precedence over naps.

**This is upsert/snapshot logic, not naive append.** Each run rewrites a single current CSV and manifest so corrected Oura records do not generate duplicate rows. No AI/LLM processing is performed.

## 3. Publish only the enriched files to Google Drive

Use **Google Drive for desktop** on your Mac. This reuses Google's desktop app for login and upload; the Python scripts need no Google OAuth credentials.

1. Install/sign in to [Google Drive for desktop](https://www.google.com/drive/download/).
2. In Finder, open Google Drive → My Drive and create a **private folder** named Oura Self Analysis.
3. Replace the example path below with the actual local path. You can drag the selected folder from Finder into Terminal to get it. Localized My Drive names can vary.

First, publish the current locally enriched export without another API call:

~~~bash
uv run --no-project --with keyring python local_enrichment.py publish --days 30 \
  --drive-dir "$HOME/Library/CloudStorage/GoogleDrive-YOUR_ACCOUNT/My Drive/Oura Self Analysis"
~~~

Or do **Oura sync → local enrichment → Drive folder copy** together:

~~~bash
uv run --no-project --with keyring python local_enrichment.py run --days 30 \
  --drive-dir "$HOME/Library/CloudStorage/GoogleDrive-YOUR_ACCOUNT/My Drive/Oura Self Analysis"
~~~

The destination must already exist. Only daily_enriched.csv and manifest.json are copied; the raw SQLite database, detailed original records and secrets stay on the Mac. Google Drive for desktop handles the actual cloud sync, so **verify its menu bar status** and check the files online. A local copy success message does not prove upload to Google completed.

**Privacy:** the CSV contains sensitive health information in readable form. A regular Google Drive folder is not end-to-end encrypted. Never publish or share the folder. This version deliberately does not add cloud encryption; consider encryption if the files must remain opaque to Google.

**Retention:** Drive gets one rolling snapshot of at most 90 days, not unlimited monthly backups. Google Drive may preserve previous file revisions, which you should manage as needed. Oura's [API/MCP Agreement](https://cloud.ouraring.com/legal/api-agreement) imposes strict limits on retention of API-derived User Data, including derived metrics. Do not assume unlimited historical archiving is allowed.

## 4. Daily automation on the Mac

Once a **manual** run succeeds and Google Drive desktop confirms upload, install the per-user macOS LaunchAgent:

~~~bash
python3 scripts/install_launch_agent.py install \
  --drive-dir "$HOME/Library/CloudStorage/GoogleDrive-YOUR_ACCOUNT/My Drive/Oura Self Analysis" \
  --hour 9 --minute 15 --days 30
~~~

Runs at 09:15 local time when the Mac is available; uses the existing Keychain, uv and local Drive mount. If the Mac sleeps or Drive is offline, the next successful run reconciles the rolling period.

Logs:

    ~/Library/Application Support/OuraSelfAnalysis/daily-stdout.log
    ~/Library/Application Support/OuraSelfAnalysis/daily-stderr.log

Remove the schedule without deleting data:

~~~bash
python3 scripts/install_launch_agent.py uninstall
~~~

If the repository is moved, reinstall: the agent stores the absolute script path.

## 5. Tests

~~~bash
python3 -m unittest discover -s tests -v
~~~

CI uses synthetic records only. No Oura or Google secrets and no real health data are needed.

## Privacy and limitations

- [Privacy Policy](PRIVACY.md) · [Terms of Service](TERMS.md)
- The [Oura API/MCP Agreement](https://cloud.ouraring.com/legal/api-agreement) restricts API-derived data as input to AI systems. Enrichment here uses deterministic Python calculations only.
- No clinical diagnosis, causal inference or public Oura application is provided.
- This is an independent personal project, not affiliated with Oura.
