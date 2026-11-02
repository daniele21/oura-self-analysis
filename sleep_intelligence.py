"""Sleep Intelligence 2.0: weekly, daily comparison and single-night detail.

Oura sleep.day is the waking date. Only long_sleep qualifies as a main night.
All values are wearable estimates and cannot establish a diagnosis.
"""
from __future__ import annotations
from datetime import date, timedelta, datetime
from pathlib import Path
from statistics import mean, pstdev
import math
from local_enrichment import daily_records

STUDIES = ["https://doi.org/10.1016/j.sleep.2024.01.020",
           "https://doi.org/10.1093/sleep/zsad253"]
FIELDS = ("sleep_minutes", "sleep_efficiency_pct", "sleep_latency_minutes",
          "awake_minutes", "sleep_score", "deep_sleep_minutes",
          "rem_sleep_minutes", "light_sleep_minutes", "time_in_bed_minutes")
COMPARE_FIELDS = ("sleep_minutes","sleep_efficiency_pct","sleep_latency_minutes",
                  "awake_minutes","sleep_score","deep_sleep_minutes","rem_sleep_minutes")
MIN_WEEK = 4


def number(value, low=0, high=100000):
    if (isinstance(value,(float,int)) and not isinstance(value,bool)
            and math.isfinite(value) and low<=value<=high):
        return float(value)
    return None


def minutes(value, max_seconds=86400):
    valid=number(value,0,max_seconds)
    return round(valid/60,2) if valid is not None else None


def aware_date(value):
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return dt if dt.utcoffset() is not None else None


def local_time(value):
    dt=aware_date(value)
    return dt.strftime("%H:%M") if dt is not None else None


def circular_clock_sd(times):
    """Midnight-aware standard deviation of local times; NOT validated SRI."""
    clean=[]
    for t in times:
        if not isinstance(t,str): continue
        p=t.split(":")
        if len(p)!=2: continue
        try: h,m=map(int,p)
        except ValueError: continue
        if 0<=h<24 and 0<=m<60: clean.append(h*60+m)
    if len(clean)<MIN_WEEK: return None
    angles=[t*2*math.pi/1440 for t in clean]
    length=math.hypot(mean(math.cos(a) for a in angles),
                      mean(math.sin(a) for a in angles))
    if length<1e-8: return None
    return round(math.sqrt(max(0,-2*math.log(min(1.,length))))*1440/(2*math.pi),1)


def choose_main(sessions):
    longs=[s for s in sessions if isinstance(s,dict) and s.get("type")=="long_sleep"]
    return max(longs,key=lambda x:number(x.get("total_sleep_duration"),0,86400) or 0) if longs else None


def extract(day,groups):
    main=choose_main(groups.get("sleep",[]))
    scores=groups.get("daily_sleep",[])
    daily=scores[0] if scores and isinstance(scores[0],dict) else {}
    item={"day":day,"main_sleep_available":main is not None,
          "sleep_score":number(daily.get("score"),0,100)}
    item.update({key:None for key in FIELDS if key!="sleep_score"})
    item.update({"bedtime_local":None,"wake_local":None,"sleep_midpoint_local":None,
                 "hrv_ms":None,"heart_rate_min_bpm":None,"heart_rate_average_bpm":None,
                 "respiratory_rate":None,"restless_periods":None,"phase_coverage":None,
                 "data_quality":[]})
    if main is None:
        item["data_quality"].append("main_sleep_unavailable")
        return item
    lookup={"sleep_minutes":"total_sleep_duration",
            "deep_sleep_minutes":"deep_sleep_duration","rem_sleep_minutes":"rem_sleep_duration",
            "light_sleep_minutes":"light_sleep_duration","awake_minutes":"awake_time",
            "time_in_bed_minutes":"time_in_bed"}
    for key,source in lookup.items():
        item[key]=minutes(main.get(source))
    item["sleep_efficiency_pct"]=number(main.get("efficiency"),0,100)
    item["sleep_latency_minutes"]=minutes(main.get("latency"),7200)
    item["bedtime_local"]=local_time(main.get("bedtime_start"))
    item["wake_local"]=local_time(main.get("bedtime_end"))
    start,end=aware_date(main.get("bedtime_start")),aware_date(main.get("bedtime_end"))
    if start is not None and end is not None and 0<(end-start).total_seconds()<=86400:
        item["sleep_midpoint_local"]=(start+(end-start)/2).strftime("%H:%M")
    item["hrv_ms"]=number(main.get("average_hrv"),1,250)
    item["heart_rate_min_bpm"]=number(main.get("lowest_heart_rate"),25,150)
    item["heart_rate_average_bpm"]=number(main.get("average_heart_rate"),25,150)
    item["respiratory_rate"]=number(main.get("average_breath"),5,40)
    item["restless_periods"]=number(main.get("restless_periods"),0,2000)
    stages=[item[k] for k in ("deep_sleep_minutes","rem_sleep_minutes","light_sleep_minutes")]
    total=item["sleep_minutes"]
    if all(v is not None for v in stages) and total is not None and total>0:
        if abs(sum(stages)-total)<=max(5,total*.02):
            item["phase_coverage"]="consistent"
        else:
            item["phase_coverage"]="inconsistent"
            item["data_quality"].append("phase_totals_do_not_match_sleep")
    else: item["phase_coverage"]="incomplete"
    if item["sleep_minutes"] is None: item["data_quality"].append("sleep_duration_missing")
    if item["bedtime_local"] is None or item["wake_local"] is None:
        item["data_quality"].append("bedtime_or_wake_offset_missing")
    if item["sleep_efficiency_pct"] is None: item["data_quality"].append("efficiency_missing")
    return item


def field_mean(rows,field,minimum=MIN_WEEK):
    values=[number(x.get(field)) for x in rows]
    valid=[x for x in values if x is not None]
    return (round(mean(valid),2) if len(valid)>=minimum else None),len(valid)


def week(rows,end):
    days=[end-timedelta(days=i) for i in range(6,-1,-1)]
    samples=[rows.get(d.isoformat(),{}) for d in days]
    valid=[x for x in samples if x.get("main_sleep_available") and
           number(x.get("sleep_minutes"),1,1440) is not None]
    avg,counts={},{}
    for field in FIELDS:
        avg[field],counts[field]=field_mean(valid,field)
    durations=[x["sleep_minutes"] for x in valid]
    return {"start":days[0].isoformat(),"end":end.isoformat(),
            "available_nights":len(valid),"calendar_days":7,
            "coverage_pct":round(len(valid)/7*100),
            "sufficient":len(valid)>=MIN_WEEK,"averages":avg,"metric_counts":counts,
            "duration_sd_minutes":round(pstdev(durations),1) if len(durations)>=MIN_WEEK else None,
            "bedtime_clock_sd_minutes":circular_clock_sd([x.get("bedtime_local") for x in valid]),
            "wake_clock_sd_minutes":circular_clock_sd([x.get("wake_local") for x in valid])}


def delta(current,previous):
    return round(current-previous,2) if current is not None and previous is not None else None


def compare_day(rows,day):
    current=rows.get(day.isoformat(),{})
    yesterday=rows.get((day-timedelta(days=1)).isoformat(),{})
    prior=[rows.get((day-timedelta(days=i)).isoformat(),{}) for i in range(1,8)]
    avg,count,day_delta,week_delta={}, {}, {}, {}
    for key in COMPARE_FIELDS:
        avg[key],count[key]=field_mean(prior,key)
        day_delta[key]=delta(number(current.get(key)),number(yesterday.get(key)))
        week_delta[key]=delta(number(current.get(key)),avg[key])
    return {"day":day.isoformat(),"previous_day":(day-timedelta(days=1)).isoformat(),
            "previous_day_exists":yesterday.get("main_sleep_available") is True,
            "previous_day_values":{k:number(yesterday.get(k)) for k in COMPARE_FIELDS},
            "prior7_start":(day-timedelta(days=7)).isoformat(),
            "prior7_end":(day-timedelta(days=1)).isoformat(),
            "previous7_averages":avg,"previous7_counts":count,
            "delta_vs_previous_day":day_delta,"delta_vs_previous7":week_delta}



def explain(report:dict)->list[dict]:
    """Narrative observations with measurements and quality, never medical claims."""
    w=report["weekly"]
    current,previous=w["recent"],w["previous"]
    results=[]
    diff=w["delta_recent_vs_previous"]["sleep_minutes"]
    if diff is not None:
        eff=w["delta_recent_vs_previous"]["sleep_efficiency_pct"]
        latency=w["delta_recent_vs_previous"]["sleep_latency_minutes"]
        summary=(
            f"Durata media negli ultimi 7 giorni: {current['averages']['sleep_minutes']:.0f} minuti "
            f"({diff:+.0f} minuti rispetto ai 7 precedenti). "
        )
        if eff is not None:
            summary+=f"Efficienza media: {eff:+.1f} punti percentuali. "
        if latency is not None:
            summary+=f"Latenza media: {latency:+.1f} minuti. "
        summary+="Le differenze non dimostrano un miglioramento o un peggioramento clinico."
        results.append({
            "id":"sleep-weekly-comparison",
            "title":"Sonno: andamento degli ultimi sette giorni",
            "summary":summary,
            "observation_window":{"start":previous["start"],"end":current["end"]},
            "measurements":{
                "current_nights":current["available_nights"],
                "previous_nights":previous["available_nights"],
                "current_sleep_minutes_avg":current["averages"]["sleep_minutes"],
                "previous_sleep_minutes_avg":previous["averages"]["sleep_minutes"],
                "sleep_minutes_avg_delta":diff,
                "sleep_efficiency_delta_pp":eff,
                "sleep_latency_delta_minutes":latency,
                "bedtime_sd_minutes":current["bedtime_clock_sd_minutes"],
            },
            "quality":{"level":"adequate" if min(current["available_nights"],previous["available_nights"])>=6 else "limited",
                       "method":"two non-overlapping seven-calendar-day groups, 4+ nights each",
                       "recent_n":current["available_nights"],
                       "baseline_n":previous["available_nights"]},
            "interpretation":"Confronto descrittivo di durata, efficienza e latenza; i segni delle differenze non sono giudizi di salute.",
            "alternative_explanations":["Orari, lavoro e viaggi","Allenamenti","Eventuali notti non registrate"],
            "limitations":["Campioni ridotti e possibili condizioni diverse fra settimane.",
                           "Durata ed efficienza sono stime del wearable.",
                           "La variabilità oraria non è uno Sleep Regularity Index validato."],
            "evidence_urls":STUDIES,"evidence_class":"exploratory","medical_alert":False,
        })
    latest=report.get("latest_main_sleep_day")
    if latest:
        nights={n["day"]:n for n in report["nights"]}
        comp=next((c for c in report["daily_comparisons"] if c["day"]==latest),None)
        night=nights.get(latest)
        if night and comp and night.get("sleep_minutes") is not None:
            day_delta=comp["delta_vs_previous_day"]["sleep_minutes"]
            week_delta=comp["delta_vs_previous7"]["sleep_minutes"]
            statements=[f"Nell'ultima notte registrata ({latest}) sono stati stimati "
                        f"{night['sleep_minutes']:.0f} minuti di sonno."]
            if day_delta is not None:
                statements.append(f"Rispetto alla notte precedente: {day_delta:+.0f} minuti.")
            else:
                statements.append("Il confronto con la notte precedente non è disponibile.")
            if week_delta is not None:
                statements.append(f"Rispetto alla media delle sette notti precedenti: {week_delta:+.0f} minuti.")
            else:
                statements.append("Il confronto con la settimana precedente ha dati insufficienti.")
            results.append({
                "id":"sleep-night-context",
                "title":"Ultima notte: confronto giornaliero e settimanale",
                "summary":" ".join(statements),
                "observation_window":{"start":comp["prior7_start"],"end":latest},
                "measurements":{
                    "night_sleep_minutes":night["sleep_minutes"],
                    "delta_vs_previous_day_minutes":day_delta,
                    "delta_vs_previous7_minutes":week_delta,
                    "previous7_n":comp["previous7_counts"]["sleep_minutes"],
                    "efficiency_pct":night.get("sleep_efficiency_pct"),
                    "latency_minutes":night.get("sleep_latency_minutes"),
                },
                "quality":{"level":"limited" if day_delta is None or week_delta is None else "adequate",
                           "recent_n":1,
                           "baseline_n":comp["previous7_counts"]["sleep_minutes"],
                           "method":"same-calendar-night vs exact prior night and average of prior seven calendar days"},
                "interpretation":"La notte precedente è un confronto singolo, sensibile alla variabilità naturale; serve leggere il trend su più notti.",
                "alternative_explanations":["Orari della giornata","Stato di recupero e allenamento","Notti mancanti"],
                "limitations":["La variabilità giornaliera può essere normale.",
                               "I riferimenti non sono soglie cliniche né causalità.",
                               "Fasi REM e profondo sono stime meno stabili."],
                "evidence_urls":STUDIES,"evidence_class":"exploratory","medical_alert":False,
            })
    return results

def build(db:Path,*,days:int=30,today:date|None=None)->dict:
    if not 7<=days<=90: raise ValueError("Sleep window must be 7-90 days.")
    today=today or date.today()
    first=today-timedelta(days=days-1)
    # Read enough private history for 28v28 even when only seven nights are visible.
    # Older per-night records never leave this module via the comparison report.
    initial_start=first-timedelta(days=max(14,56-days))
    grouped=daily_records(db,initial_start,today)
    rows={key:extract(key,groups) for key,groups in grouped.items()}
    # The comparison is anchored to the last measured main night, not to
    # today's calendar date. When syncing lags, the oldest 28v28 baseline
    # must be extended by the same lag; otherwise the 7/30/90 API ranges
    # would report contradictory sample counts for the same comparison.
    comparison_day=max((key for key,row in rows.items()
                        if key<=today.isoformat() and row.get("main_sleep_available")),
                       default=today.isoformat())
    comparison_start=date.fromisoformat(comparison_day)-timedelta(days=55)
    if comparison_start<initial_start:
        backfill=daily_records(db,comparison_start,initial_start-timedelta(days=1))
        rows.update({key:extract(key,groups) for key,groups in backfill.items()})
    recent=week(rows,today)
    previous=week(rows,today-timedelta(days=7))
    deltas={}
    for field in COMPARE_FIELDS:
        r,p=recent["averages"][field],previous["averages"][field]
        deltas[field]=delta(r,p) if recent["sufficient"] and previous["sufficient"] else None
    history=[]
    for offset in range(0,days,7):
        w=week(rows,today-timedelta(days=offset))
        if w["end"]<first.isoformat(): break
        history.append(w)
    nights,comparisons=[],[]
    for i in range(days):
        day=first+timedelta(days=i)
        row=rows.get(day.isoformat())
        if row is None or (not row["main_sleep_available"] and row["sleep_score"] is None):
            continue
        nights.append(row)
        comparisons.append(compare_day(rows,day))
    latest=next((r["day"] for r in reversed(nights) if r["main_sleep_available"]),None)
    from sleep_stage_trends import build as build_stages
    stage_trends = build_stages(rows, days=days, today=today)
    from period_comparisons import build as build_comparisons
    # Use the most recent qualified overnight session, even if a lagging sync
    # has left today's calendar window partially empty. Preserve report dates
    # separately so a stale data feed is never presented as today's sleep.
    period_comparisons = build_comparisons(
        rows, today=date.fromisoformat(comparison_day), group="sleep")
    return {"schema_version":"2.0","method":"Deterministic local descriptive sleep analysis",
            "window":{"start":first.isoformat(),"end":today.isoformat(),"days":days},
            "weekly":{"recent":recent,"previous":previous,
                      "delta_recent_vs_previous":deltas,"history":history},
            "nights":nights,"daily_comparisons":comparisons,"latest_main_sleep_day":latest,
            "stage_trends":stage_trends,"comparisons":period_comparisons,
            "sources":STUDIES,
            "limitations":[
                "Finestre di sette giorni di calendario ancorate alla data del report, non settimane ISO.",
                "Confronto settimanale solo con almeno 4 notti in ciascun blocco.",
                "Confronto con il giorno precedente solo se esiste il dato della notte precedente esatta.",
                "Sonno profondo, REM, tempo sveglio e risvegli sono stime non diagnostiche.",
                "Giorno senza misurazione non significa sonno assente o insonnia.",
                "La variabilità dell'orario locale non equivale a uno Sleep Regularity Index validato."]}
