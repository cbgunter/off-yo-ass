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
from datetime import UTC, date, datetime

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


@dataclass
class GarminActivity:
    """One discrete workout/session, as opposed to DayMetrics' daily
    wellness aggregate. `type_key` is Garmin's own raw activity-type
    string (e.g. "cycling", "resistance_training") -- there's no offline
    mapping of Garmin's full type vocabulary available (confirmed: not
    bundled in the garminconnect package, only fetchable live via
    get_activity_types()), so it's stored as-is rather than coerced into
    this app's own fixed activity-type set. `activity_id` and
    `start_gmt` both come straight from Garmin; `start_gmt` doubles as
    the natural idempotency key when this gets written to the store,
    since re-running the same day should overwrite the same rows, not
    duplicate them.
    """

    activity_id: int
    type_key: str
    start_gmt: datetime
    duration_min: float
    distance_m: float | None = None
    calories: float | None = None
    name: str | None = None
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
        # Each entry is [timestamp_ms, level, ...]. Garmin has no single
        # "at wake" field, so the first *real* reading of the day stands
        # in for it — a documented approximation, not a bug. Confirmed
        # against a real account that the array's leading entries are
        # often [timestamp, null] placeholders before the watch takes its
        # first actual measurement, so this has to skip nulls rather than
        # blindly take index 0 — that was the actual bug.
        for entry in levels:
            if len(entry) > 1 and entry[1] is not None:
                metrics.body_battery_at_wake = entry[1]
                break

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


def fetch_activities(day: date) -> list[GarminActivity]:
    """Discrete workouts for one calendar day -- unlike fetch_day's daily
    aggregates, this is new and unverified against a real account (see
    oya/workers/sync_garmin.py's isolated try/except around it). Confirmed
    from the installed garminconnect/garth source, not from memory:
    get_activities_by_date takes "YYYY-MM-DD" strings (a date object
    raises), duration comes back in seconds, distance in meters, and
    startTimeGMT is a naive "YYYY-MM-DD HH:MM:SS" string that is already
    UTC despite carrying no offset.
    """
    client = _client()
    iso = day.isoformat()
    raw_activities = client.get_activities_by_date(iso, iso) or []

    activities: list[GarminActivity] = []
    for item in raw_activities:
        activity_id = item.get("activityId")
        start_gmt_raw = item.get("startTimeGMT")
        if activity_id is None or not start_gmt_raw:
            continue  # no stable idempotency key without both -- skip it

        start_gmt = datetime.strptime(start_gmt_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        duration_seconds = item.get("duration")
        type_key = (item.get("activityType") or {}).get("typeKey") or "other"

        activities.append(
            GarminActivity(
                activity_id=activity_id,
                type_key=type_key,
                start_gmt=start_gmt,
                duration_min=duration_seconds / 60 if duration_seconds is not None else 0.0,
                distance_m=item.get("distance"),
                calories=item.get("calories"),
                name=item.get("activityName"),
                raw=item,
            )
        )
    return activities
