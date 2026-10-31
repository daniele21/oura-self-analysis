#!/usr/bin/env python3
"""Read-only, loopback-only mobile dashboard for locally processed Oura data.

No external API calls, OAuth secrets, external AI or public listener.
A reverse proxy such as Tailscale Serve can later expose this loopback port
to authenticated tailnet devices without changing application permissions.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

import health_analytics
import local_enrichment
import oura_self_analysis as oura

ASSET_DIR = Path(__file__).resolve().parent / "dashboard"
ALLOWED_ASSETS = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
    "/sw.js": "sw.js",
    "/manifest.webmanifest": "manifest.webmanifest",
    "/icon.svg": "icon.svg",
}
SUPPORTED_DAYS = (7, 30, 90)
HEALTH_KEYS = tuple(health_analytics.FIELDS)
DAILY_KEYS = (
    "activity_score", "readiness_score", "steps",
    "deep_sleep_minutes", "rem_sleep_minutes", "temperature_deviation_c",
    "spo2_average_pct",
)
HTTP_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; manifest-src 'self'; "
        "worker-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
}
MAX_OUTPUT_BYTES = 1_000_000


def make_payload(db: Path, *, days: int = 30, today: date | None = None) -> dict:
    """Return only whitelisted summary fields and deterministic insight text."""
    if days not in SUPPORTED_DAYS:
        raise ValueError("Only 7, 30 and 90 calendar-day views are supported.")
    now = today or date.today()
    features, document = health_analytics.analyze(db, days=days, today=now)
    daily = local_enrichment.enrich_window(db, days=days, today=now)
    by_day = {r["day"]: r for r in daily}
    records: list[dict] = []
    for feature in features:
        day = feature["day"]
        existing = by_day.get(day, {})
        row = {key: feature.get(key) for key in HEALTH_KEYS}
        row.update({key: existing.get(key) for key in DAILY_KEYS})
        records.append(row)
    records.sort(key=lambda x: x["day"])
    valid_days = len({item["day"] for item in records})
    end = now.isoformat()
    most_recent = records[-1]["day"] if records else None
    latest_age = (now - date.fromisoformat(most_recent)).days if most_recent else None

    # Keep the original health analytics output's references/limitations.
    allowed_insight_keys = ("id", "title", "summary", "measurements",
                            "observation_window", "evidence_urls", "limitations",
                            "evidence_class", "medical_alert", "quality",
                            "interpretation", "alternative_explanations")
    insights = [
        {key: item.get(key) for key in allowed_insight_keys}
        for item in document.get("insights", [])
    ]
    return {
        "version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "range": {"days": days, "start": (now - timedelta(days=days - 1)).isoformat(), "end": end},
        "meta": {
            "observed_days": valid_days,
            "coverage_percent": round(valid_days / days * 100),
            "last_observed_day": most_recent,
            "age_days": latest_age,
            "workout_history_available": bool(document["metadata"].get("workout_history_available")),
        },
        "records": records,
        "insights": insights,
        "exercise_recovery": document.get("exercise_recovery"),
        "privacy": "Dati locali. Statistiche descrittive, non valutazioni cliniche.",
    }


class DashboardHandler(BaseHTTPRequestHandler):
    """Static allowlist + read-only JSON; never serves the repository or SQLite."""

    server_version = "OuraPrivateDashboard/1.0"
    sys_version = ""

    def log_message(self, format, *args):
        # Do not log URLs, response bodies, headers, or private health data.
        pass

    def _headers(self, status: int, mime: str, length: int, *, cache: str = "no-store"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        for name, value in HTTP_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()

    def _reply(self, status: int, data: bytes, mime: str):
        self._headers(status, mime, len(data))
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_OUTPUT_BYTES:
            return self._reply(500, b'{"error":"Risposta troppo grande"}',
                               "application/json; charset=utf-8")
        self._reply(status, body, "application/json; charset=utf-8")

    def _trusted_host(self):
        host = self.headers.get("Host", "").split(":")[0].lower().strip(".")
        return host in ("localhost", "127.0.0.1", "[::1]") or bool(
            re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net", host)
        )

    def do_HEAD(self):
        self._get()

    def do_GET(self):
        self._get()

    def do_POST(self):
        self._json(405, {"error": "Servizio di sola lettura"})

    def _get(self):
        if not self._trusted_host():
            self._json(403, {"error": "Host non autorizzato"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/api/dashboard":
            params = parse_qs(parsed.query, keep_blank_values=True)
            if set(params) - {"days"} or len(params.get("days", ["30"])) != 1:
                self._json(400, {"error": "Parametri non supportati"})
                return
            raw_days = params.get("days", ["30"])[0]
            if raw_days not in ("7", "30", "90"):
                self._json(400, {"error": "Intervallo non supportato"})
                return
            try:
                payload = make_payload(oura.DB_PATH, days=int(raw_days))
            except (oura.OuraError, sqlite3.Error, ValueError, OSError):
                self._json(503, {
                    "error": "Dati non ancora disponibili. Esegui il sync Oura sul Mac.",
                    "retryable": True,
                })
                return
            self._json(200, payload)
            return
        asset_name = ALLOWED_ASSETS.get(parsed.path)
        if not asset_name:
            self._json(404, {"error": "Risorsa non trovata"})
            return
        path = ASSET_DIR / asset_name
        try:
            data = path.read_bytes()
        except OSError:
            self._json(404, {"error": "Risorsa non trovata"})
            return
        mime = {
            ".js": "text/javascript",
            ".css": "text/css",
            ".webmanifest": "application/manifest+json",
            ".svg": "image/svg+xml",
            ".html": "text/html",
        }.get(path.suffix, "application/octet-stream") + "; charset=utf-8"
        self._reply(200, data, mime)


def serve(port: int = 8765):
    if not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged port (1024–65535).")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    httpd.daemon_threads = True
    print(f"Oura dashboard (solo locale): http://127.0.0.1:{port}")
    print("I dati restano sul Mac. Ctrl+C per fermare il server.")
    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\nDashboard arrestata.")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the private mobile Oura dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        serve(args.port)
    except (ValueError, OSError) as exc:
        print(f"Dashboard non avviata: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
