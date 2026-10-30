# Oura Self-Analysis

Private, local-first integration for extracting **your own** Oura Ring data via the official API V2. This is not a hosted service and is not affiliated with Oura.

## 1. First login on macOS

Requirements: Oura OAuth application, active Oura API access, Python 3.10+, [uv](https://docs.astral.sh/uv/).

Ensure the Oura app has **exactly** this registered redirect URI:

    http://localhost:8989/callback

Run in macOS Terminal:

    git clone https://github.com/daniele21/oura-self-analysis.git
    cd oura-self-analysis
    uv run --no-project --with keyring python oura_self_analysis.py login

When prompted, enter the **Client ID** and **Client Secret** from Oura Developer Portal. The secret is hidden while you type. Do not put it in a chat message or GitHub. Your browser opens the Oura authorization page; approve the requested scopes.

Credentials and rotating OAuth tokens are saved to **macOS Keychain**, not to this repository.

## 2. Extract data and see a summary

    uv run --no-project --with keyring python oura_self_analysis.py status
    uv run --no-project --with keyring python oura_self_analysis.py sync --days 30
    uv run --no-project --with keyring python oura_self_analysis.py report

The sync requests recent **sleep scores, detailed sleep, readiness and activity** data, following every API page. Data is saved in a SQLite database here:

    ~/Library/Application Support/OuraSelfAnalysis/oura.sqlite3

The database is private and never uploaded. Sync can be repeated: existing records are updated without duplication.

To backfill older records:

    uv run --no-project --with keyring python oura_self_analysis.py sync --start 2025-01-01

To include other authorized data sources:

    uv run --no-project --with keyring python oura_self_analysis.py sync --days 7 --collections daily_sleep,sleep,daily_readiness,daily_activity,heartrate,workout,enhanced_tag,daily_spo2

Dates use YYYY-MM-DD; the optional \`--end\` is exclusive. Heart-rate boundaries use UTC. If some scopes were not granted by the user, those collections are skipped; other API errors are shown explicitly. Data may lag until Oura has synced to its cloud.

## Technical safeguards

- OAuth2 authorization-code flow with PKCE S256 and random CSRF state.
- Local callback bound to \`127.0.0.1:8989\`; registered URI must match exactly.
- Credentials and tokens saved only through macOS Keychain via Python's \`keyring\`; no plaintext fallback.
- Rotating single-use refresh tokens persisted *before* use, with cross-process file lock.
- Rate-limit retries, pagination, and idempotent SQLite upserts. The application specifies its User-Agent.

## Troubleshooting

- **Redirect mismatch:** update the Oura app's registered redirect URI to exactly \`http://localhost:8989/callback\`.
- **Port 8989 in use:** close the application occupying the port before logging in.
- **401 or refresh failure:** rerun \`login\`.
- **403 or empty data:** check Oura membership (Gen3+), permissions and sync history.
- **Keychain errors:** run from a standard interactive macOS session.

## Privacy and limitations

- [Privacy Policy](PRIVACY.md) · [Terms of Service](TERMS.md)
- Do not share client secrets, access tokens, OAuth authorization codes, the local database, or medical records.
- No cloud deployment, daily automation, or external AI integration is enabled yet.
- Oura's [API and MCP Agreement](https://cloud.ouraring.com/legal/api-agreement), effective June 2026, **restricts using Oura API data as input to AI models**. This tool currently does local, non-AI reporting only.

## Tests

    python3 -m unittest discover -s tests -v

All tests run without real health data or Oura credentials.

## Next steps

1. Confirm the local OAuth login and a successful real sync.
2. Schedule daily incremental sync on macOS (launchd).
3. Build local dashboards and statistical analysis.
