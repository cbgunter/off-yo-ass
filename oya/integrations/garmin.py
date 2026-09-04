"""Garmin Connect sync. Pulls one calendar day of recovery data and
normalizes it into the shape the domain layer and store expect. Talks to
`garminconnect` directly rather than through the `garmin_mcp` server,
because a nightly ETL should be deterministic and shouldn't spend tokens.

Field paths below (sleepScores.overall.value, hrvSummary.lastNightAvg,
bodyBatteryValuesArray, dateWeightList, ...) are best-effort from
garminconnect's public method names and known community-documented
response shapes — not yet verified against a real account, since that
needs scripts/bootstrap_garmin.py to have run first. Every lookup uses
`.get()` chains on purpose: a wrong path degrades to a missing value for
that one metric, not a crashed sync. Expect to correct a few of these
once real data is flowing (see the plan's verification step).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import date

from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError

from oya.integrations.garmin_tokenstore import download_tokenstore, upload_tokenstore

GRAMS_PER_LB = 453.592


class GarminNotBootstrapped(Exception):
    """No usable tokens in SSM — scripts/bootstrap_garmin.py needs to run
    (again, if this followed a real expiry) from your machine."""


@dataclass
class DayMetrics:
    day: date
    sleep_minutes: float | None = None
    sleep_score: float | None = None
    resting_heart_rate: float | None = None
    hrv_overnight_avg: float | None = None
    stress_avg: float | None = None
    body_battery_at_wake: float | None = None
    steps: float | None = None
    weight_lbs: float | None = None
    raw: dict = field(default_factory=dict, repr=False)


def _client() -> Garmin:
    tokendir = tempfile.mkdtemp(prefix="garmin-tokens-")
    if download_tokenstore(tokendir) == 0:
        raise GarminNotBootstrapped(
            "No Garmin tokens in SSM. Run scripts/bootstrap_garmin.py once from your machine."
        )

    client = Garmin()
    try:
        client.login(tokendir)
    except (GarminConnectAuthenticationError, GarminConnectConnectionError) as exc:
        raise GarminNotBootstrapped(
            "Garmin tokens expired. Re-run scripts/bootstrap_garmin.py."
        ) from exc

    upload_tokenstore(tokendir)  # carry forward any refresh garth just did
    return client


def fetch_day(day: date) -> DayMetrics:
    client = _client()
    iso = day.isoformat()
    metrics = DayMetrics(day=day)

    sleep = client.get_sleep_data(iso) or {}
    daily_sleep = sleep.get("dailySleepDTO") or {}
    seconds = daily_sleep.get("sleepTimeSeconds")
    if seconds is not None:
        metrics.sleep_minutes = seconds / 60
    metrics.sleep_score = ((daily_sleep.get("sleepScores") or {}).get("overall") or {}).get(
        "value"
    )

    heart_rates = client.get_heart_rates(iso) or {}
    metrics.resting_heart_rate = heart_rates.get("restingHeartRate")

    hrv = client.get_hrv_data(iso) or {}
    metrics.hrv_overnight_avg = (hrv.get("hrvSummary") or {}).get("lastNightAvg")

    stress = client.get_stress_data(iso) or {}
    metrics.stress_avg = stress.get("avgStressLevel")

    battery_days = client.get_body_battery(iso) or []
    if battery_days:
        levels = battery_days[0].get("bodyBatteryValuesArray") or []
        if levels:
            # Each entry is [timestamp_ms, level, ...]. Garmin has no
            # single "at wake" field, so the first reading of the day
            # stands in for it — a documented approximation, not a bug.
            metrics.body_battery_at_wake = levels[0][1]

    stats = client.get_stats(iso) or {}
    metrics.steps = stats.get("totalSteps")

    weight = client.get_body_composition(iso, iso) or {}
    entries = weight.get("dateWeightList") or []
    if entries:
        grams = entries[-1].get("weight")
        if grams is not None:
            metrics.weight_lbs = grams / GRAMS_PER_LB

    metrics.raw = {
        "sleep": sleep,
        "heart_rates": heart_rates,
        "hrv": hrv,
        "stress": stress,
        "body_battery": battery_days,
        "stats": stats,
        "weight": weight,
    }
    return metrics
