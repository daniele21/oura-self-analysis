"""Prespecified, non-clinical within-person sleep ↔ cardiovascular associations.

Only four same-waking-night comparisons are tested. Spearman ranks handle
outliers/ties; leave-one-calendar-week-out checks fragility; within-week
centering explores temporal trends. There are NO p-values, causal estimates,
risk predictions, or disease/recovery scores. Results require enough distinct
calendar days rather than a number of database records.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import math
from statistics import mean

WINDOW_DAYS = 90
MIN_PAIRED_DAYS = 21
MIN_JACKKNIFE_DAYS = 18
MIN_WEEKS = 4
SOURCES = (
    "https://doi.org/10.1152/ajpheart.00041.2026",
    "https://www.ausport.gov.au/ais/position_statements/heart-rate-variability",
)
PRESPECIFIED = (
    ("sleep_minutes", "hrv_ms", "Durata del sonno", "HRV"),
    ("sleep_minutes", "rhr_bpm", "Durata del sonno", "FC minima"),
    ("sleep_efficiency_pct", "hrv_ms", "Efficienza del sonno", "HRV"),
    ("sleep_efficiency_pct", "rhr_bpm", "Efficienza del sonno", "FC minima"),
)


def finite(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def rank(values: list[float]) -> list[float]:
    """Average ranks for ties, no external scipy dependency."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    out = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        midrank = ((i + 1) + j) / 2
        for k in range(i, j):
            out[indexed[k][0]] = midrank
        i = j
    return out


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    mx, my = mean(x), mean(y)
    sx = sum((a-mx)**2 for a in x)
    sy = sum((b-my)**2 for b in y)
    if sx <= 1e-12 or sy <= 1e-12:
        return None
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(sx*sy)


def spearman(pairs: list[tuple[date,float,float]]) -> float | None:
    if len(pairs) < 3:
        return None
    return pearson(rank([p[1] for p in pairs]), rank([p[2] for p in pairs]))


def week_id(day: date) -> tuple[int,int]:
    cal = day.isocalendar()
    return cal.year, cal.week


def within_week_spearman(pairs: list[tuple[date,float,float]]) -> tuple[float|None,int]:
    """Rank association after subtracting observed week means: sensitivity only."""
    grouped: dict[tuple[int,int], list[tuple[date,float,float]]] = defaultdict(list)
    for pair in pairs:
        grouped[week_id(pair[0])].append(pair)
    qualified = [v for v in grouped.values() if len(v) >= 3]
    if len(qualified) < MIN_WEEKS:
        return None,len(qualified)
    detrended = []
    for group in qualified:
        avg_x=mean(x for _,x,_ in group)
        avg_y=mean(y for _,_,y in group)
        detrended.extend((d,x-avg_x,y-avg_y) for d,x,y in group)
    return spearman(detrended),len(qualified)


def analyze_pair(rows: list[dict], end: date, exposure: str, outcome: str,
                 exposure_label: str, outcome_label: str) -> dict:
    start = end - timedelta(days=WINDOW_DAYS - 1)
    observed = {}
    for row in rows:
        raw_day = row.get("day")
        try:
            day = date.fromisoformat(raw_day)
        except (ValueError, TypeError):
            continue
        if not start <= day <= end:
            continue
        x,y = row.get(exposure),row.get(outcome)
        if finite(x) and finite(y):
            # Require physiologically meaningful, finite and positive measurements.
            bounds={"sleep_minutes":(1,1440),
                    "sleep_efficiency_pct":(1,100),
                    "hrv_ms":(1,250),"rhr_bpm":(25,150)}
            a,b=bounds[exposure],bounds[outcome]
            if a[0] <= x <= a[1] and b[0] <= y <= b[1]:
                observed[day]=(float(x),float(y))
    paired = [(d,*v) for d,v in sorted(observed.items())]
    counts = {"paired_nights":len(paired),"minimum_paired_nights":MIN_PAIRED_DAYS,
              "calendar_days":WINDOW_DAYS,"distinct_weeks":len(set(week_id(p[0]) for p in paired))}
    base = {
        "id":"sleep-"+exposure+"-"+outcome,
        "exposure":exposure, "outcome":outcome,
        "exposure_label":exposure_label,"outcome_label":outcome_label,
        "method":"prespecified same-wake-day Spearman, leave-one-week-out and within-week sensitivity",
        "window":{"start":start.isoformat(),"end":end.isoformat()},
        "quality":counts,
        "spearman_rho":None,"within_week_rho":None,
        "leave_one_week_sign_consistency_pct":None,
        "leave_one_week_replicates":0,
        "status":"insufficient",
        "limitations":[
            "Stessa notte di risveglio: relazione osservazionale simultanea, non direzione causale.",
            "La settimana e gli allenamenti possono influenzare entrambi i segnali.",
            "Le notti successive non sono indipendenti; correlazione non significa causalità.",
            "Sono esplorate solo quattro coppie predefinite, senza p-value o selezione opportunistica.",
            "I campi sono stime Oura derivate dalla stessa sessione, con possibili errori condivisi.",
        ],
    }
    if len(paired) < MIN_PAIRED_DAYS or counts["distinct_weeks"] < MIN_WEEKS:
        return base
    rho=spearman(paired)
    if rho is None:
        base["status"]="uninformative"
        base["limitations"].append("Valori costanti: la correlazione non è definita.")
        return base
    base["spearman_rho"]=round(rho,3)
    within,nweeks=within_week_spearman(paired)
    base["within_week_rho"]=round(within,3) if within is not None else None
    base["quality"]["within_week_groups"]=nweeks
    results=[]
    for week in sorted(set(week_id(p[0]) for p in paired)):
        subset=[p for p in paired if week_id(p[0]) != week]
        if len(subset) >= MIN_JACKKNIFE_DAYS:
            value=spearman(subset)
            if value is not None:
                results.append(value)
    base["leave_one_week_replicates"]=len(results)
    if not results:
        base["status"]="limited"
        return base
    # Sign consistency is NOT a confidence interval or significance test.
    consistency=sum(v*rho > 0 for v in results)/len(results)*100
    base["leave_one_week_sign_consistency_pct"]=round(consistency,1)
    if abs(rho) < .2:
        base["status"]="weak_observed"
    elif consistency < 75 or (within is not None and within*rho <= 0):
        base["status"]="unstable"
    else:
        base["status"]="consistent_exploratory"
    return base


def evaluate(rows: list[dict], end_day: str) -> dict:
    end=date.fromisoformat(end_day)
    associations=[analyze_pair(rows,end,*spec) for spec in PRESPECIFIED]
    return {
        "schema_version":"1.0",
        "window":{"start":(end-timedelta(days=WINDOW_DAYS-1)).isoformat(),
                  "end":end.isoformat()},
        "associations":associations,
        "method":"four preregistered descriptive same-night pairs, no diagnostic or causal claims",
        "sources":list(SOURCES),
        "privacy":"Aggregate evidence only; no daily health readings or record identifiers.",
    }


def explain(report: dict) -> list[dict]:
    """At most two interpretable cross-domain cards; never turn absence into evidence."""
    candidates=[a for a in report["associations"]
                if a["status"]=="consistent_exploratory"]
    candidates.sort(key=lambda a:abs(a["spearman_rho"]),reverse=True)
    cards=[]
    for a in candidates[:2]:
        rho=a["spearman_rho"]
        direction="positiva" if rho>0 else "negativa"
        cards.append({
            "id":"cardio-context-"+a["exposure"]+"-"+a["outcome"],
            "title":a["exposure_label"]+" e "+a["outcome_label"]+": associazione osservata",
            "summary":(
                f"Nelle {a['quality']['paired_nights']} notti confrontabili, "
                f"l'associazione fra {a['exposure_label'].lower()} e "
                f"{a['outcome_label']} è {direction} (Spearman {rho:+.2f}). "
                "Il risultato resta descrittivo, non dimostra una causa."
            ),
            "observation_window":a["window"],
            "measurements":{
                "rho_spearman":rho,"paired_nights":a["quality"]["paired_nights"],
                "within_week_rho":a["within_week_rho"],
                "leave_one_week_sign_consistency_pct":a["leave_one_week_sign_consistency_pct"],
            },
            "quality":{"level":"limited","recent_n":a["quality"]["paired_nights"],
                       "method":a["method"]},
            "interpretation":"Un'associazione personale richiede verifica su altri periodi e con fattori confondenti osservati.",
            "alternative_explanations":["Allenamenti o stress","Routine e giorno della settimana",
                                        "Errore condiviso fra misure del wearable"],
            "limitations":a["limitations"],
            "evidence_urls":list(SOURCES),"evidence_class":"exploratory",
            "medical_alert":False,
        })
    return cards
