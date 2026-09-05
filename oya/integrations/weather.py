"""National Weather Service forecast for the evening workout window. Free,
no API key, one required header. The ZIP-to-grid-point resolution (office
+ X/Y) happens once via scripts/resolve_weather_grid.py and is stored as
plain config -- a home address's grid point never changes, so there's no
reason to re-resolve it on every run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

from oya.settings import get_settings

USER_AGENT = "off-yo-ass (cbgunter@gmail.com)"

EVENING_START_HOUR = 17
EVENING_END_HOUR = 20


@dataclass(frozen=True)
class WeatherWindow:
    short_forecast: str | None
    temperature_f: float | None
    precipitation_chance: int | None


def get_evening_window() -> WeatherWindow | None:
    settings = get_settings()
    if not (settings.weather_office and settings.weather_grid_x and settings.weather_grid_y):
        return None

    url = (
        f"https://api.weather.gov/gridpoints/{settings.weather_office}/"
        f"{settings.weather_grid_x},{settings.weather_grid_y}/forecast/hourly"
    )
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()
    periods = response.json()["properties"]["periods"]

    evening = [
        p
        for p in periods
        if EVENING_START_HOUR <= datetime.fromisoformat(p["startTime"]).hour < EVENING_END_HOUR
    ]
    if not evening:
        return None

    representative = evening[len(evening) // 2]
    precipitation = representative.get("probabilityOfPrecipitation") or {}
    return WeatherWindow(
        short_forecast=representative.get("shortForecast"),
        temperature_f=representative.get("temperature"),
        precipitation_chance=precipitation.get("value"),
    )
