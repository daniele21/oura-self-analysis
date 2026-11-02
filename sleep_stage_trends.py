"""Private, deterministic long-term Oura sleep-stage trends.

Only one long_sleep per waking date (already selected in sleep_intelligence).
Missing, partial or contradictory stage durations stay missing, never 0.
The daily chart shows real observed nights; rolling 7d uses prior 6 calendar
days + selected day (>=4 qualified nights); percentages are weighted by
recorded total-sleep minutes, not averaged percentages.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from math import isfinite

STAGES = ("light", "deep", "rem")
MIN_VALID_NIGHTS = 4
ROLLING_DAYS = 7
MAX_WINDOW_DAYS = 90


def _valid(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def qualified(night: dict | None) -> dict | None:
    """Only complete and internally consistent main-sleep stage estimates."""
    if not isinstance(night, dict) or night.get("main_sleep_available") is not True:
        return None
    if night.get("phase_coverage") != "consistent":
        return None
    duration = night.get("sleep_minutes")
    if not _valid(duration) or not 0 < duration <= 1440:
        return None
    values = {s:night.get(s+"_sleep_minutes") for s in STAGES}
    if any(not _valid(v) or not 0 <= v <= duration for v in values.values()):
        return None
    if abs(sum(values.values())-duration) > max(5.,duration*.02):
        return None
    return {**{s:float(v) for s,v in values.items()},"total":float(duration)}


def aggregate(values: list[dict], minimum: int = MIN_VALID_NIGHTS) -> dict:
    """Mean phase minutes per qualified night; time-weighted phase fraction."""
    count = len(values)
    out = {"valid_nights":count,"sufficient":count >= minimum}
    total = sum(v["total"] for v in values)
    for s in STAGES:
        avg = mean(v[s] for v in values) if count >= minimum else None
        percent = sum(v[s] for v in values)/total*100 if count >= minimum and total else None
        out[s+"_minutes"] = round(avg,2) if avg is not None else None
        out[s+"_percent"] = round(percent,2) if percent is not None else None
    return out


def build(rows: dict[str,dict], *, days: int, today: date) -> dict:
    if not 7 <= days <= MAX_WINDOW_DAYS:
        raise ValueError("Stage chart window must be 7–90 days")
    start = today-timedelta(days=days-1)
    indexed = {d:qualified(r) for d,r in rows.items()}
    daily = []
    rolling = []
    for idx in range(days):
        d = start+timedelta(days=idx)
        key = d.isoformat()
        vals = indexed.get(key)
        day = {"day":key,"valid":vals is not None,
               "total_minutes":round(vals["total"],2) if vals else None}
        for stage in STAGES:
            day[stage+"_minutes"] = round(vals[stage],2) if vals else None
            day[stage+"_percent"] = round(vals[stage]/vals["total"]*100,2) if vals else None
        daily.append(day)
        past = [indexed.get((d-timedelta(days=i)).isoformat()) for i in range(ROLLING_DAYS)]
        aggregate7 = aggregate([v for v in past if v is not None])
        rolling.append({"day":key,**aggregate7})
    periods = []
    for offset in range(0,days,7):
        a = start+timedelta(days=offset)
        b = min(today,a+timedelta(days=6))
        found = [indexed.get((a+timedelta(days=i)).isoformat())
                 for i in range((b-a).days+1)]
        agg = aggregate([x for x in found if x is not None])
        periods.append({"start":a.isoformat(),"end":b.isoformat(),
                        "calendar_days":(b-a).days+1,**agg})
    recent = aggregate([indexed.get((today-timedelta(days=i)).isoformat())
                        for i in range(7) if indexed.get((today-timedelta(days=i)).isoformat())])
    preceding = aggregate([indexed.get((today-timedelta(days=i)).isoformat())
                           for i in range(7,14) if indexed.get((today-timedelta(days=i)).isoformat())])
    delta = {s:{"minutes":round(recent[s+"_minutes"]-preceding[s+"_minutes"],2)
                      if recent["sufficient"] and preceding["sufficient"] else None,
                 "percentage_points":round(recent[s+"_percent"]-preceding[s+"_percent"],2)
                      if recent["sufficient"] and preceding["sufficient"] else None}
             for s in STAGES}
    return {
        "schema_version":"1.0",
        "window":{"start":start.isoformat(),"end":today.isoformat(),"days":days},
        "daily":daily,"rolling7":rolling,"weekly_buckets":periods,
        "recent7":recent,"previous7":preceding,"delta7":delta,
        "method":"Main long_sleep stage estimates only; 7-calendar-day mean minutes and total-sleep-weighted percentages",
        "minimum_nights_per_7_days":MIN_VALID_NIGHTS,
        "limitations":[
            "Fasi sonno stimate da Oura: non equivalgono a misure cliniche polisonnografiche.",
            "Notti senza sessione principale, fasi incomplete o incongruenti non entrano nelle medie.",
            "Un punto di trend 7 giorni richiede almeno quattro notti valide nei sette giorni di calendario, inclusa la data del punto.",
            "Le percentuali settimanali dividono la somma delle durate delle singole fasi per la somma del sonno totale nelle notti valide.",
            "Le settimane del grafico a 90 giorni sono blocchi consecutivi non sovrapposti, l'ultimo può contenere meno di sette giorni.",
            "Un aumento della quota REM o profondo non significa automaticamente migliore qualità del sonno.",
        ],
    }
