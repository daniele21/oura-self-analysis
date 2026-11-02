"""Privacy-scoped, deterministic sleep-stage A/B period overlays.

Daily data are exposed ONLY if both date ranges fit entirely within the
user-selected 7/30/90-day dashboard window. No additional raw Oura reads.
Both periods must be equal length; missing days remain explicit nulls.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import isfinite
from statistics import mean

STAGES = ("light", "deep", "rem")
PRESETS = (("7v7", 7, 4, 30), ("30v30", 30, 21, 90))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _dates(first: date, days: int):
    return [(first + timedelta(days=i)).isoformat() for i in range(days)]


def _period(rows: dict, first: date, length: int, minimum: int) -> dict:
    dates = _dates(first, length)
    nights = []
    values = []
    for day in dates:
        existing = rows.get(day)
        valid = bool(existing and existing.get("valid") is True
                     and _finite(existing.get("total_minutes"))
                     and existing["total_minutes"] > 0
                     and all(_finite(existing.get(s + "_minutes")) for s in STAGES))
        item = {"day":day,"valid":valid}
        for stage in STAGES:
            item[stage + "_minutes"] = existing[stage + "_minutes"] if valid else None
            item[stage + "_percent"] = existing[stage + "_percent"] if valid else None
        nights.append(item)
        if valid:
            values.append(existing)
    enough = len(values) >= minimum
    total = sum(v["total_minutes"] for v in values)
    averages = {
        stage: {
            "minutes": round(mean(v[stage + "_minutes"] for v in values), 2) if enough else None,
            "percent": round(sum(v[stage + "_minutes"] for v in values) / total * 100, 2)
                       if enough and total > 0 else None,
        } for stage in STAGES
    }
    return {
        "start":dates[0], "end":dates[-1], "calendar_days":length,
        "valid_nights":len(values), "sufficient":enough,
        "averages":averages, "daily":nights,
    }


def build(stage_trends: dict) -> dict:
    visible=stage_trends["window"]
    days=stage_trends["daily"]
    # Anchor to the latest *phase-qualified* main night, never to calendar today.
    valid_days=[row["day"] for row in days if row.get("valid") is True]
    anchor=max(valid_days, default=None)
    out={"schema_version":"1.0", "as_of_day":anchor,
         "alignment":"index_of_calendar_day_in_each_nonoverlapping_period",
         "presets":{}, "privacy":"No individual nights outside selected API window."}
    for key,length,minimum,required_days in PRESETS:
        result={"code":key, "days_per_period":length, "minimum_nights":minimum,
                "required_view_days":required_days,
                "status":"no_data", "recent":None,"reference":None,
                "delta":{stage:{"minutes":None, "percentage_points":None}
                         for stage in STAGES}}
        if anchor is None:
            out["presets"][key]=result
            continue
        end=date.fromisoformat(anchor)
        recent_first=end-timedelta(days=length-1)
        reference_first=recent_first-timedelta(days=length)
        if reference_first.isoformat()<visible["start"]:
            result["status"]="range_too_short"
            out["presets"][key]=result
            continue
        by_day={row["day"]:row for row in days}
        reference=_period(by_day,reference_first,length,minimum)
        recent=_period(by_day,recent_first,length,minimum)
        result["reference"],result["recent"]=reference,recent
        result["status"]="available" if recent["sufficient"] and reference["sufficient"] else "insufficient"
        if result["status"]=="available":
            for stage in STAGES:
                a,b=recent["averages"][stage],reference["averages"][stage]
                result["delta"][stage]={
                    "minutes":round(a["minutes"]-b["minutes"],2),
                    "percentage_points":round(a["percent"]-b["percent"],2),
                }
        out["presets"][key]=result
    out["limitations"]=[
        "Allineamento per giorno relativo G1…GN, non per data assoluta; per 30 giorni i weekdays possono differire.",
        "L'ancora è l'ultima notte con tutte e tre le fasi coerenti; non necessariamente oggi.",
        "Soglie ingegneristiche: almeno 4/7 o 21/30 notti valide per i confronti aggregati.",
        "Notti mancanti o incoerenti rimangono null; nessuna interpolazione.",
        "Minuti = media per notte valida; percentuali = somma fasi / somma durata totale valida.",
        "Le fasi del sonno sono stime del dispositivo e non implicano qualità clinica.",
    ]
    return out
