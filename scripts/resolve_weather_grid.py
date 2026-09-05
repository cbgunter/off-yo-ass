#!/usr/bin/env python3
"""Resolves a US ZIP code to the NWS grid office and X/Y coordinates --
run once (I run this myself; it's just public geocoding and NWS lookups,
no credentials involved). The result goes into WEATHER_OFFICE,
WEATHER_GRID_X, and WEATHER_GRID_Y as GitHub Actions repo variables --
not secret, just config, the same build-time pattern as GOOGLE_CLIENT_ID
and VAPID_PUBLIC_KEY.

Usage:
    uv run python scripts/resolve_weather_grid.py <zip>
"""

from __future__ import annotations

import sys

import requests

USER_AGENT = "off-yo-ass (cbgunter@gmail.com)"


def main(zip_code: str) -> None:
    geo = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=10)
    geo.raise_for_status()
    place = geo.json()["places"][0]
    lat, lon = place["latitude"], place["longitude"]
    print(f"{zip_code} -> {place['place name']}, {place['state abbreviation']} ({lat}, {lon})")

    points = requests.get(
        f"https://api.weather.gov/points/{lat},{lon}",
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    points.raise_for_status()
    props = points.json()["properties"]

    print()
    print("Set these as GitHub Actions repo variables:")
    print(f"  WEATHER_OFFICE={props['gridId']}")
    print(f"  WEATHER_GRID_X={props['gridX']}")
    print(f"  WEATHER_GRID_Y={props['gridY']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/resolve_weather_grid.py <zip>")
        sys.exit(1)
    main(sys.argv[1])
