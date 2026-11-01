# Oura Self-Analysis

Personal Oura Ring data pipeline: **Oura API → local SQLite → local deterministic enrichment → optional Google Drive Desktop sync**. No cloud runtime, external AI, or credentials stored in this public repository.

## Mobile dashboard — Oura Insights

New: **responsive read-only web dashboard** with four sections (Oggi, Trend, Insight, Allenamenti), 7/30/90-day line charts, evidence-linked explanations, and missing-data visibility. It reads the *real local SQLite data* through a tightly limited Python HTTP API; it contains **no sample patient data**.

### View on the Mac

~~~bash
cd ~/Projects/oura-self-analysis
git pull --ff-only
uv run --no-project python dashboard_server.py --port 8765
~~~

Open **http://127.0.0.1:8765** in the Mac browser. No extra Python packages or Google Drive mount are needed. The server listens **only on 127.0.0.1**, never on your LAN, and exposes just a small set of static assets and a read-only \`/api/dashboard?days=30\` JSON endpoint.

The dashboard uses the Mac's existing \`~/Library/Application Support/OuraSelfAnalysis/oura.sqlite3\`. If there is no data it shows a helpful empty state instead of invented values. On each refresh, calculations are done locally from SQLite. This is independent of Google Drive synchronization and does **not** trigger the Oura API or write to SQLite.

Data coverage is honest: a 90-day view does not fabricate earlier data when fewer days have been synchronized. An outdated Oura last-observation date is shown explicitly.

### Keep it running without Terminal

Once manual startup works, stop it with Ctrl+C, then:

~~~bash
uv run --no-project python scripts/dashboard_service.py install --port 8765
~~~

This installs a per-user macOS LaunchAgent to start the local web server at login and keep it running. Remove the service (without touching Oura data) with:

~~~bash
uv run --no-project python scripts/dashboard_service.py uninstall
~~~

Local service logs are private at \`~/Library/Application Support/OuraSelfAnalysis/dashboard-stdout.log\` and \`dashboard-stderr.log\`. If you move the repository, reinstall the agent.

### Access from the phone (optional, not enabled by this change)

For private access remotely, install [Tailscale](https://tailscale.com/) on your Mac and phone, and use [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) to securely publish the localhost port **within your authorized tailnet**. Keep the application bound to localhost, and use Serve **not Funnel**; Funnel makes services publicly reachable. Tailnet access depends on your Tailscale account and ACLs. Do not expose the dashboard via open router ports or a public GitHub Pages site.

The app includes a manifest, installable mobile icon, and a service worker that caches **only HTML/CSS/JS/icon**, never health API responses. When visited from a secure Tailscale HTTPS address, you can add it to your phone's Home screen.

**Security & limitations:** There is no built-in login screen; Tailscale identity/permissions form the access boundary when viewing remotely. HTTP on localhost is for your trusted Mac user only. Dashboard API responses use \`Cache-Control: no-store\`, strict security headers and restricted paths. The browser app does not send analytics to third parties. Insights are descriptive and not clinical guidance. The mobile page is not an offline health-data viewer.

## 1. Connect and sync Oura

Requires macOS, Python 3.10+, [uv](https://docs.astral.sh/uv/) and Oura API access. Configure the OAuth callback in the Oura portal as http://localhost:8989/callback.

~~~bash
git clone https://github.com/daniele21/oura-self-analysis.git
cd oura-self-analysis
uv run --no-project --with keyring python oura_self_analysis.py login
uv run --no-project --with keyring python oura_self_analysis.py sync --days 65
uv run --no-project --with keyring python oura_self_analysis.py report
~~~

Enter your Oura Client ID and Secret only in the **local Terminal prompt**. OAuth tokens and credentials are stored in macOS Keychain, never committed. The database is:

    ~/Library/Application Support/OuraSelfAnalysis/oura.sqlite3

The original collector handles scopes with Oura's extapi: prefix, pagination, token refresh, and idempotent upserts. The recommended **first import is 65 days**: this covers a 30-day reporting window, with a separate 7-day recent median and non-overlapping previous 28-day baseline, even near the beginning of the report.

## 2. Enrich your data locally

~~~bash
uv run --no-project --with keyring python local_enrichment.py enrich --days 30
~~~

Two files are generated **outside the repository**:

    ~/Library/Application Support/OuraSelfAnalysis/enriched/daily_enriched.csv
    ~/Library/Application Support/OuraSelfAnalysis/enriched/manifest.json

The CSV has one row for each available day in the rolling 30-day window (configurable 1–90 days). It contains sleep/readiness/activity scores, steps, sleep duration by stage (minutes), sleep efficiency, nighttime HR/HRV, temperature deviation, SpO₂ (if present), rolling 7-day means, differences from the previous 28-day baseline, and missing-source indicators. Means require at least 3 observations (7 days) or 7 observations (28 days), respectively. Missing values remain blank, never zero. The main overnight sleep takes precedence over naps.

**This is upsert/snapshot logic, not naive append.** Each run rewrites a single current CSV and manifest so corrected Oura records do not generate duplicate rows. No AI/LLM processing is performed.

## 2b. Evidence-informed health insights (local only by default)

Three deterministic analytics modules are now available:

- **Sleep Intelligence:** main overnight sleep duration, latency, local bedtime regularity (14-day SD; *not* the validated Sleep Regularity Index) and 7-day sleep duration.
- **Autonomic Recovery:** night-time HRV and minimum nightly heart rate; 7-day median compared with a **non-overlapping previous 28-day** baseline (minimum 5 and 14 observations respectively).
- **Exercise Recovery:** counts of imported workouts and observational next-day HRV comparison after workout days, emitted only when there are at least 4 observations per group.

Run locally without uploading extra files to Drive:

~~~bash
uv run --no-project --with keyring python health_analytics.py --days 30
~~~

This creates two additional **private local** artifacts:

- `~/Library/Application Support/OuraSelfAnalysis/enriched/health_features.csv`
- `~/Library/Application Support/OuraSelfAnalysis/enriched/health_insights.json`

Every insight contains measurements, limitations and links to research. There are **no medical alerts, causal claims, AI models, predictions or disease classifications**. A missing workout history is marked unknown, not interpreted as no activity. See [scientific methodology](docs/scientific-methods.md) for exact definitions and study citations.

To include these files with the usual enrichment and optionally upload them through Drive Desktop or rclone, add **`--include-health`**:

~~~bash
# Manually, from the Mac, after your first 65-day backfill:
uv run --no-project --with keyring python local_enrichment.py run --days 30 \
  --include-health --drive-dir "$DRIVE_DIR"
~~~

The script will upload `daily_enriched.csv`, `health_features.csv`, `health_insights.json`, then `manifest.json` after successful verification. The manifest contains file SHA-256 checksums. The normal two-file export remains unchanged unless you explicitly opt in.

**Backfill:** for 30 days of health features and a complete earlier non-overlapping 28-day baseline even for the earliest reported day, import **65 days** once with `oura_self_analysis.py sync --days 65 --collections daily_sleep,sleep,daily_readiness,daily_activity,workout`. Existing OAuth authorization and Keychain tokens can be reused.

### Cardiovascular Intelligence — cross-domain context (v1.4)

Recupero now adds **four prespecified** within-person, same-waking-night associations: sleep duration and efficiency against nightly HRV and minimum nighttime HR. Each comparison requires at least 21 valid paired nights spanning four calendar weeks (up to 90 days). Results include Spearman rho, distinct night/week counts, one-week-out sign sensitivity and optional within-week-centered correlation. These tests help flag fragile relationships; they are **not statistical significance or causal inference**. The browser receives only aggregated results, even when opened in 7-day mode. At most two stable exploratory associations are offered as explainable insight cards.

The within-night HR/HRV detail now also describes the **lowest qualified 30-minute heart-rate bin** and its elapsed position from bedtime, plus a P90−P10 spread of the 30-minute medians where at least eight bins are present. This is **not** the absolute heart-rate minimum or a medical biomarker.

The Attività section can expand recorded workout categories and Oura intensity groups to inspect HRV/HR deltas at waking days D+1/D+2/D+3, where sample thresholds are met. Workouts within the window may overlap and be unrecorded. The app does not convert Oura intensity to RPE, infer recovery time or issue training prescriptions.

See [scientific methods](docs/scientific-methods.md) for formulae, selection rules and reliability limits.

### Cardiovascular Intelligence — night profiles (M1)

The **Recupero** section now has aligned HR and HRV night curves for the chosen main sleep night. A new read-only local endpoint `/api/v2/recovery/night?day=YYYY-MM-DD` reads **only one overnight long_sleep session** and returns privacy-minimized 30-minute median bins for both channels, with missing bins blank. The browser can explore both values with a synchronized keyboard-friendly slider or a tabular alternative.

Bins are shown only if they contain at least 4 valid nominal five-minute samples, using an actual UTC timeline derived from the Oura PublicSample timestamps, with timezone/DST awareness and independent channel alignment. Per-channel full-night coverage is reported and a partial night never pretends to be 100% complete. Interpretation remains descriptive; no clinical predictions or invented recovery scores.

The feature is **local only** and uses already authorized `sleep` data: no new OAuth scopes, remote models, record-level identifiers, additional raw-data disk storage or GitHub health logs. The browser can request at most one of the latest 90 nights per query. Technical details and limitations are in [M1 methodology](docs/m1-night-cardiovascular-profile.md). The existing summary API remains backward compatible.

### Sleep stage trends — light, deep and REM

In **Sonno → Fasi del sonno nel tempo**, a new dedicated chart shows the three estimated sleep phases as color-coded **stacked nightly bars** for 7/30 days or **per-night weekly averages** for the 90-day view. Switch to **Trend 7 giorni** to see three independently drawn rolling 7-calendar-day averages, or between **minutes and percentage of total sleep**. The chart includes a keyboard-accessible date scrubber and a tabular equivalent.

Each night must have a valid main \`long_sleep\` session and three internally consistent phase durations. Missing and inconsistent nights are *missing*, not zero; trend points and weekly comparisons require at least 4 valid nights. Percentages are based on the total observed sleep duration of valid nights, rather than an unweighted percentage average. This is a wearable-derived, descriptive analysis and does not infer a diagnosis or a "better REM score". [Method and limitations](docs/scientific-methods.md).

### Sleep Intelligence 2.0 (v1.3)

The **Sonno** tab offers three linked views, driven by real, local Oura API V2 sleep data:

1. **Weekly overview:** trailing seven calendar nights vs the preceding seven, including means for duration, efficiency, awake time, latency and proprietary Sleep Score, plus dispersion of duration and circular clock-time regularity. Each period displays its actual coverage. A week needs 4 valid nights for means and two such weeks for comparisons.
2. **Daily navigation:** choose any main sleep night in the selected 7/30/90-day window. Compare each metric to the **exact previous calendar day's** sleep and to the **average of the seven previous days**, excluding the selected night. Missing previous-day data are unknown, not replaced by an earlier observation.
3. **Night detail:** overnight duration, bedtime/wake time and midpoint, time in bed, efficiency, latency, awake minutes, restless periods, estimated REM/deep/light sleep proportions, HRV, minimum/average heart rate and respiration when reported by Oura.

The dashboard includes new explainable **weekly** and **latest-night** insight cards with evidence, sample sizes and limitations. The enrichment opt-in also adds stage durations, awake minutes and other measured daily features to health_features.csv, and the new reports to health_insights.json. These stay local unless explicitly published with --include-health.

Only sessions with **type=long_sleep** count as main overnight sleep: naps are not passed off as nights. Stage estimates are not diagnostic, and score changes are not medical judgments. Sleep phase sums are checked instead of artificially normalized. See [scientific methods](docs/scientific-methods.md) for definitions, study references and caveats.

### Exercise Recovery 2.0 (v1.2)

Workout analysis now includes **recorded duration**, conservative activity groups, and Oura's reported `easy/moderate/hard` intensity. Unknown duration is **not** assumed to be zero, and Oura intensity is not session-RPE or a calibrated training-load score.

The Training view adds observational differences in **nightly HRV, minimum nighttime heart rate, and sleep duration** at the **next three wake-days D+1/D+2/D+3** compared with wake-day D. These are calendar-day lags, **not precisely 24/48/72 hours after exercise**.

The engine reports both **isolated recorded sessions** (no other registered workout within ±3 days) and **all workout days** with overlap warnings, so frequent workouts can still be reviewed without pretending a clean causal experiment. A median at each lag requires at least 4 valid pairs. The dashboard never exposes Oura workout IDs, free-form workout labels or exact workout times.

For more details and limitations, see [scientific-methods.md](docs/scientific-methods.md). No medical alerts, diagnosis, performance optimization guarantees or training prescriptions are generated.

### Deeper longitudinal insights (v1.1)

The deterministic **`longitudinal_insights.py`** engine now adds:

- **Personal robust baselines:** 7-day median versus the non-overlapping 28-day median, dispersion with scaled median absolute deviation (MAD), personal statistical reference bands, number of days outside a band and longest consecutive run.
- **Stability and uncertainty:** HRV 7-day coefficient of variation (CV), leave-one-out directional sensitivity, and a reproducible exploratory 80% moving-block-bootstrap interval *only when all 35 days are present*.
- **Joint physiology:** paired days when nighttime HRV is below and minimum nighttime heart rate is above their respective individual statistical reference bands; this is not a disease or overtraining detection tool.
- **Reliability metadata:** actual sample sizes, coverage and explanatory limitations on each insight. Missing data suppresses unsupported estimates. If historical dispersion is zero, no anomaly score is calculated.

The enhanced interpretation, data quality and alternative explanations are visible under **"Come è stato calcolato"** in the mobile dashboard. These exploratory statistical conventions **are not validated clinical thresholds**; see [detailed methods](docs/scientific-methods.md).

Check the availability of Oura API fields without exposing physiological values or identifiers:

~~~bash
uv run --no-project --with keyring python scripts/audit_oura_coverage.py --days 65
~~~

It writes `~/Library/Application Support/OuraSelfAnalysis/enriched/coverage_audit.json` **locally with restrictive permissions**. This file contains only collection and field coverage counts; it is never automatically sent to Drive or GitHub.

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

For the daily pipeline, **--days 30** controls the export window, while **--sync-days 7** (the default) controls how many recent API days are refreshed. Run an initial 65-day import before enabling automation; occasionally repeat a 65-day sync if you want to reconcile older Oura corrections.

The destination must already exist. Only daily_enriched.csv and manifest.json are copied; the raw SQLite database, detailed original records and secrets stay on the Mac. Google Drive for desktop handles the actual cloud sync, so **verify its menu bar status** and check the files online. A local copy success message does not prove upload to Google completed.

**Privacy:** the CSV contains sensitive health information in readable form. A regular Google Drive folder is not end-to-end encrypted. Never publish or share the folder. This version deliberately does not add cloud encryption; consider encryption if the files must remain opaque to Google.

**Retention:** Drive gets one rolling snapshot of at most 90 days, not unlimited monthly backups. Google Drive may preserve previous file revisions, which you should manage as needed. Oura's [API/MCP Agreement](https://cloud.ouraring.com/legal/api-agreement) imposes strict limits on retention of API-derived User Data, including derived metrics. Do not assume unlimited historical archiving is allowed.

## Alternative: mount Google Drive virtually (without Drive for desktop)

You **can mount Drive as a virtual folder** with rclone. This does **not** download a full local copy. Writes can use a small local cache until rclone uploads them, so copying into the mounted folder is **not** proof that upload is complete.

1. Install rclone: `brew install rclone`, and run `rclone config` to authorize a remote named `gdrive`. In 2026, rclone's shared Google OAuth client is being retired: [configure your own Google client ID](https://rclone.org/drive/#making-your-own-client-id). This is separate from Oura OAuth.
2. For **rclone mount**, macOS needs [macFUSE or FUSE-T](https://rclone.org/commands/rclone_mount/#mounting-on-macos). Alternatively, [rclone nfsmount](https://rclone.org/commands/rclone_nfsmount/) uses the built-in NFS stack but is marked **experimental** by rclone.
3. You can mount **just the existing private Oura Drive folder** by its Drive folder ID:

~~~bash
mkdir -p "$HOME/mnt/oura-drive"

rclone mount gdrive: "$HOME/mnt/oura-drive" \
  --drive-root-folder-id 1lwlNWLxiRuFJvYJ4NzuLvCJJWkTfSdq3 \
  --vfs-cache-mode writes --daemon
~~~

If you prefer the built-in macOS NFS path, substitute `rclone nfsmount` for `rclone mount`. Check the official compatibility requirements for your rclone/macOS versions.

**Verify the mount is active** (important: the empty mountpoint directory can exist even when Drive is not mounted):

~~~bash
mount | grep -F "$HOME/mnt/oura-drive"
~~~

Only after the check succeeds, publish using the **existing local-folder option**:

~~~bash
uv run --no-project --with keyring python local_enrichment.py publish \
  --days 30 --drive-dir "$HOME/mnt/oura-drive"
~~~

The same `--drive-dir` works with `local_enrichment.py run` and the macOS scheduler. But scheduling a mounted folder requires **mounting it before each job** or keeping rclone running, and verifying that the mount is active; the scheduler does not manage mount lifecycle. If the mount is missing, a bare directory still exists, so **do not enable unattended --drive-dir publishing to a mountpoint without an explicit mount verification**. Instead, use the direct `--drive-remote` option for robust unattended daily uploads, which also performs checksum verification.

To unmount: `umount "$HOME/mnt/oura-drive"` (may require closing Finder/other processes using the volume). The cache is local; do not assume unmounting while an upload is pending is safe.

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

For daily scientific enrichment, reinstall the LaunchAgent with the same existing destination and the extra opt-in flag:

~~~bash
python3 scripts/install_launch_agent.py install --drive-dir "$DRIVE_DIR" \
  --hour 9 --minute 15 --days 30 --include-health
~~~

Only the local analytical outputs are exported; the raw SQLite database stays on the Mac. On Drive Desktop, confirmation of remote upload still depends on Google Drive's synchronization status.

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
