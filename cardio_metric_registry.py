"""Canonical definitions for the Oura overnight cardiovascular UI.

Precisely separate Oura-reported whole-night values from sampled timeseries.
No inferred clinical meaning, no API calls, no access to personal data.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class MetricDefinition:
    label_it: str
    unit: str
    source_collection: str
    source_field: str
    granularity: str
    statistic: str
    description_it: str
    caveat_it: str


METRICS = {
    "hrv_ms": MetricDefinition(
        "HRV media notturna", "ms", "sleep", "average_hrv",
        "sleep_session", "Oura-provided average",
        "Media HRV riportata da Oura per la sessione principale del sonno.",
        "Non è una misura clinica autonoma del recupero o del sistema nervoso.",
    ),
    "rhr_bpm": MetricDefinition(
        "FC minima notturna", "bpm", "sleep", "lowest_heart_rate",
        "sleep_session", "Oura-provided minimum",
        "Frequenza cardiaca minima stimata da Oura nella sessione di sonno.",
        "Non chiamarla frequenza cardiaca media a riposo; differisce dalla HR media.",
    ),
    "average_heart_rate_bpm": MetricDefinition(
        "FC media notturna", "bpm", "sleep", "average_heart_rate",
        "sleep_session", "Oura-provided average",
        "Frequenza cardiaca media della sessione principale di sonno.",
        "Il metodo di aggregazione Oura può differire dalle serie a intervalli.",
    ),
    "heart_rate_series_bpm": MetricDefinition(
        "FC durante la notte", "bpm", "sleep", "heart_rate",
        "sample_series", "PublicSample(timestamp, interval, items)",
        "Campioni temporali di frequenza cardiaca riportati da Oura.",
        "Disponibilità e intervallo effettivo devono essere verificati sul dispositivo.",
    ),
    "hrv_series_ms": MetricDefinition(
        "HRV durante la notte", "ms", "sleep", "hrv",
        "sample_series", "PublicSample(timestamp, interval, items)",
        "Campioni temporali di HRV riportati da Oura.",
        "Non interpretare variazioni di un singolo campione come risposta clinica.",
    ),
}


def public_definitions() -> dict[str, dict]:
    """Immutable reference metadata, safe for a read-only dashboard response."""
    return {name: asdict(value) for name, value in METRICS.items()}
