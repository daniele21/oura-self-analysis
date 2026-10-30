#!/usr/bin/env python3
"""Private, local-only Oura API V2 collector. Python 3.10+; requires keyring."""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import fcntl
import getpass
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import webbrowser

AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
API_URL = "https://api.ouraring.com/v2/usercollection"
REDIRECT_URI = "http://localhost:8989/callback"
SERVICE = "oura-self-analysis"
SCOPES = ("daily", "heartrate", "workout", "tag", "spo2")
COLLECTIONS = {
    "daily_sleep": "daily",
    "sleep": "daily",
    "daily_readiness": "daily",
    "daily_activity": "daily",
    "heartrate": "heartrate",
    "workout": "workout",
    "enhanced_tag": "tag",
    "daily_spo2": "spo2",
}
DEFAULT_COLLECTIONS = ("daily_sleep", "sleep", "daily_readiness", "daily_activity")
APP_HOME = Path.home() / "Library" / "Application Support" / "OuraSelfAnalysis"
DB_PATH = APP_HOME / "oura.sqlite3"


class OuraError(Exception):
    pass


class APIError(OuraError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Oura returned HTTP {status}")


def private_home() -> Path:
    APP_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    APP_HOME.chmod(0o700)
    return APP_HOME


def keychain():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
        from keyring.backends.null import Keyring as NullKeyring
    except ImportError as exc:
        raise OuraError("Install the 'keyring' package (see README).") from exc
    backend = keyring.get_keyring()
    if isinstance(backend, (FailKeyring, NullKeyring)) or getattr(backend, "priority", 0) <= 0:
        raise OuraError("No secure Keychain backend available; refusing plaintext token storage.")
    return keyring


def secret_read(name: str) -> str | None:
    return keychain().get_password(SERVICE, name)


def secret_write(name: str, value: str) -> None:
    keychain().set_password(SERVICE, name, value)


def credentials(prompt: bool = False) -> tuple[str, str]:
    client_id = secret_read("client_id")
    client_secret = secret_read("client_secret")
    if prompt or not (client_id and client_secret):
        client_id = input("Oura Client ID: ").strip()
        client_secret = getpass.getpass("Oura Client Secret (hidden): ").strip()
        if not client_id or not client_secret:
            raise OuraError("Client ID and secret must both be nonempty.")
        secret_write("client_id", client_id)
        secret_write("client_secret", client_secret)
    return client_id, client_secret


def token_load() -> dict | None:
    raw = secret_read("oauth_tokens")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OuraError("Invalid OAuth token in Keychain: log in again.") from exc


def token_save(response: dict, requested_scopes: str | None = None) -> dict:
    if not response.get("access_token") or not response.get("refresh_token"):
        raise OuraError("Token response missing access/refresh token; credentials not replaced.")
    if response.get("token_type", "bearer").lower() != "bearer":
        raise OuraError("Unexpected token type; credentials not replaced.")
    result = {
        "access_token": response["access_token"],
        "refresh_token": response["refresh_token"],
        "expires_at": time.time() + max(0, int(response.get("expires_in", 0))),
        "scope": response.get("scope", requested_scopes),
    }
    # Oura refresh tokens rotate and are single-use. Save BEFORE using the new access token.
    secret_write("oauth_tokens", json.dumps(result))
    return result


def request_json(url: str, *, form: dict | None = None, bearer: str | None = None) -> dict:
    data = urlencode(form).encode("utf-8") if form is not None else None
    headers = {"User-Agent": "OuraSelfAnalysis/0.1", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    for attempt in range(4):
        req = Request(url, data=data, headers=headers, method="POST" if data else "GET")
        try:
            with urlopen(req, timeout=30) as res:
                result = json.load(res)
            if not isinstance(result, dict):
                raise OuraError("Unexpected JSON response from Oura.")
            return result
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise APIError(exc.code) from None
            retry_after = exc.headers.get("Retry-After", "")
            delay = min(30, int(retry_after)) if retry_after.isdigit() else min(30, 2 ** attempt)
            time.sleep(delay)
        except (URLError, TimeoutError) as exc:
            if attempt == 3:
                raise OuraError("Network request failed after retries.") from exc
            time.sleep(2 ** attempt)
        except (ValueError, json.JSONDecodeError) as exc:
            raise OuraError("Oura returned invalid JSON.") from exc
    raise OuraError("Unexpected request failure.")


def exchange(form: dict) -> dict:
    client_id, client_secret = credentials()
    return request_json(TOKEN_URL, form={
        **form, "client_id": client_id, "client_secret": client_secret
    })


def authorized_access_token(*, rejected: str | None = None) -> str:
    private_home()
    lock_path = APP_HOME / ".refresh.lock"
    with open(lock_path, "a+", encoding="utf-8") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        saved = token_load()
        if not saved:
            raise OuraError("Not authenticated. Run: python oura_self_analysis.py login")
        if (saved.get("expires_at", 0) > time.time() + 120
                and (rejected is None or saved["access_token"] != rejected)):
            return saved["access_token"]
        if not saved.get("refresh_token"):
            raise OuraError("No refresh token: log in again.")
        try:
            refreshed = exchange({
                "grant_type": "refresh_token",
                "refresh_token": saved["refresh_token"],
            })
        except APIError as exc:
            if exc.status in (400, 401):
                raise OuraError("Refresh rejected by Oura; run 'login' again.") from exc
            raise
        return token_save(refreshed, saved.get("scope"))["access_token"]


def login(args: argparse.Namespace) -> None:
    client_id, _ = credentials(prompt=args.reset_client)
    scopes = " ".join(args.scopes) if args.scopes else " ".join(SCOPES)
    for scope in scopes.split():
        if scope not in ("daily", "heartrate", "workout", "tag", "spo2", "personal", "email", "session"):
            raise OuraError(f"Unknown Oura scope: {scope}")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    outcome: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Never log the one-time authorization code.
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            if not secrets.compare_digest(query.get("state", [""])[0], state):
                outcome["error"] = "Invalid OAuth state; refusing callback."
            elif "error" in query:
                outcome["error"] = "Authorization denied by Oura."
            elif query.get("code"):
                outcome["code"] = query["code"][0]
            else:
                outcome["error"] = "Missing authorization code."
            success = "code" in outcome
            html = ("Authorization received. Return to Terminal." if success
                    else "Authorization failed. Check the Terminal.")
            body = f"<html><body><h3>{html}</h3></body></html>".encode()
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    # Bind to loopback only. localhost in the registered URI must match exactly.
    try:
        server = HTTPServer(("127.0.0.1", 8989), CallbackHandler)
    except OSError as exc:
        raise OuraError("Local port 8989 unavailable. Close the other process or change Oura registration.") from exc
    query = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    url = f"{AUTH_URL}?{query}"
    print("Opening browser to authorize Oura. Complete authorization within 3 minutes.")
    if not webbrowser.open(url):
        print("Open this URL in your browser:\n" + url)
    server.timeout = 180
    try:
        server.handle_request()
    finally:
        server.server_close()
    if "code" not in outcome:
        raise OuraError(outcome.get("error", "No OAuth callback received (timeout)."))
    response = exchange({
        "grant_type": "authorization_code",
        "code": outcome["code"],
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    })
    saved = token_save(response, scopes)
    print("Authenticated. Tokens saved in macOS Keychain (not in GitHub).")
    print("Scopes reported by Oura:", saved.get("scope") or "not provided")


def status(_args: argparse.Namespace) -> None:
    saved = token_load()
    if not saved:
        print("Not authenticated. Run 'login'.")
        return
    expiration = datetime.fromtimestamp(saved["expires_at"], timezone.utc).isoformat()
    print("OAuth token stored in Keychain.")
    print("Expires (UTC):", expiration)
    print("Scopes:", saved.get("scope") or "not provided by Oura")


def open_database() -> sqlite3.Connection:
    private_home()
    con = sqlite3.connect(DB_PATH)
    os.chmod(DB_PATH, 0o600)
    con.execute("""CREATE TABLE IF NOT EXISTS records (
        collection TEXT NOT NULL,
        record_id TEXT NOT NULL,
        day TEXT,
        payload TEXT NOT NULL,
        synced_at TEXT NOT NULL,
        PRIMARY KEY (collection, record_id)
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS records_day ON records(collection, day)")
    con.commit()
    return con


def record_identity(collection: str, item: dict) -> str:
    if item.get("id") is not None:
        return str(item["id"])
    if collection == "heartrate" and item.get("timestamp"):
        return f'{item["timestamp"]}:{item.get("source", "")}'
    # Stable fallback for unexpected API shapes; no unique id assumed.
    return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()


def save_page(con: sqlite3.Connection, collection: str, items: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in items:
        if not isinstance(item, dict):
            raise OuraError("Unexpected collection record shape.")
        day = item.get("day") or item.get("timestamp", "")[:10]
        rows.append((collection, record_identity(collection, item), day or None,
                     json.dumps(item, ensure_ascii=False, sort_keys=True), now))
    with con:
        con.executemany("""INSERT INTO records
            (collection, record_id, day, payload, synced_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(collection, record_id) DO UPDATE SET
              day=excluded.day, payload=excluded.payload, synced_at=excluded.synced_at
            WHERE records.payload != excluded.payload""", rows)
    return len(rows)


def fetch_pages(con: sqlite3.Connection, name: str, start: date, end: date) -> int:
    params = ({"start_datetime": f"{start.isoformat()}T00:00:00Z",
               "end_datetime": f"{end.isoformat()}T00:00:00Z"}
              if name == "heartrate" else
              {"start_date": start.isoformat(), "end_date": end.isoformat()})
    next_tokens: set[str] = set()
    total = 0
    while True:
        url = f"{API_URL}/{name}?{urlencode(params)}"
        bearer = authorized_access_token()
        try:
            response = request_json(url, bearer=bearer)
        except APIError as exc:
            if exc.status != 401:
                raise
            bearer = authorized_access_token(rejected=bearer)
            response = request_json(url, bearer=bearer)
        items = response.get("data")
        if not isinstance(items, list):
            raise OuraError(f"{name}: API response missing 'data' array.")
        total += save_page(con, name, items)
        next_token = response.get("next_token")
        if not next_token:
            return total
        if not isinstance(next_token, str) or next_token in next_tokens:
            raise OuraError(f"{name}: invalid/repeated pagination token.")
        next_tokens.add(next_token)
        params["next_token"] = next_token


def sync(args: argparse.Namespace) -> None:
    today = date.today()
    if args.days < 1:
        raise OuraError("--days must be positive.")
    try:
        start = date.fromisoformat(args.start) if args.start else today - timedelta(days=args.days - 1)
        end = date.fromisoformat(args.end) if args.end else today + timedelta(days=1)
    except ValueError as exc:
        raise OuraError("Use YYYY-MM-DD for dates.") from exc
    if end <= start:
        raise OuraError("--end must be later than --start.")
    names = [s.strip() for s in args.collections.split(",")]
    if not names or any(s not in COLLECTIONS for s in names):
        raise OuraError("Unknown collection. Valid: " + ", ".join(COLLECTIONS))
    saved = token_load()
    if not saved:
        raise OuraError("Run 'login' before 'sync'.")
    granted = set(saved.get("scope", "").split())
    failures = []
    with open_database() as con:
        for name in dict.fromkeys(names):
            needed = COLLECTIONS[name]
            if granted and needed not in granted:
                print(f"{name}: skipped (scope '{needed}' was not granted)")
                continue
            try:
                count = fetch_pages(con, name, start, end)
                print(f"{name}: processed {count} records")
            except OuraError as exc:
                failures.append(name)
                print(f"{name}: ERROR: {exc}", file=sys.stderr)
    print(f"Local SQLite: {DB_PATH}")
    if failures:
        raise OuraError("Partial sync; collections needing retry: " + ", ".join(failures))


def report(args: argparse.Namespace) -> None:
    if not DB_PATH.exists():
        raise OuraError("No local data yet. Run 'sync' first.")
    with open_database() as con:
        print("Stored rows by collection:")
        for name, n in con.execute(
            "SELECT collection, COUNT(*) FROM records GROUP BY collection ORDER BY collection"
        ):
            print(f"  {name}: {n}")
        print("\nDay         Sleep  Readiness  Activity  Steps")
        print("-----------------------------------------------")
        rows: dict[str, dict] = {}
        cutoff = (date.today() - timedelta(days=args.days - 1)).isoformat()
        for name, day, raw in con.execute(
            """SELECT collection, day, payload FROM records
               WHERE collection IN ('daily_sleep','daily_readiness','daily_activity')
               AND day >= ? ORDER BY day DESC""", (cutoff,)
        ):
            if day:
                rows.setdefault(day, {})[name] = json.loads(raw)
        for day in sorted(rows, reverse=True):
            sample = rows[day]
            sleep = sample.get("daily_sleep", {})
            readiness = sample.get("daily_readiness", {})
            activity = sample.get("daily_activity", {})
            def fmt(value):
                return str(value) if value is not None else "—"
            print(f"{day}  {fmt(sleep.get('score')):>5}  "
                  f"{fmt(readiness.get('score')):>9}  "
                  f"{fmt(activity.get('score')):>8}  {fmt(activity.get('steps')):>5}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private Oura API V2 extraction to local SQLite")
    sub = parser.add_subparsers(dest="command", required=True)
    login_p = sub.add_parser("login", help="Complete local browser OAuth login")
    login_p.add_argument("--reset-client", action="store_true", help="Replace Keychain client credentials")
    login_p.add_argument("--scopes", nargs="+", default=None, help="Override default Oura OAuth scopes")
    sub.add_parser("status", help="Show token status without printing secrets")
    sync_p = sub.add_parser("sync", help="Sync recent data, or a specified date interval")
    sync_p.add_argument("--days", type=int, default=30)
    sync_p.add_argument("--start", help="Inclusive start, YYYY-MM-DD")
    sync_p.add_argument("--end", help="Exclusive UTC end, YYYY-MM-DD")
    sync_p.add_argument("--collections", default=",".join(DEFAULT_COLLECTIONS))
    report_p = sub.add_parser("report", help="Show local summary (no external AI)")
    report_p.add_argument("--days", type=int, default=14)
    args = parser.parse_args(argv)
    try:
        {"login": login, "status": status, "sync": sync, "report": report}[args.command](args)
        return 0
    except (OuraError, sqlite3.Error, KeyboardInterrupt) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
