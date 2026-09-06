#!/usr/bin/env python3
"""One-time history backfill for Garmin recovery metrics.

The nightly sync (oya/workers/sync_garmin.py) re-fetches a trailing week,
which catches late-arriving sleep/HRV going forward. This pulls a longer
stretch of history in one shot so the 30-day baselines in
oya/domain/recovery.py establish now instead of a month from now.

Run it yourself: it needs your AWS credentials -- to read the Garmin
tokens from SSM and to write the DynamoDB table. Nothing is typed into a
terminal. It re-fetches one day at a time (a Garmin login per day), so a
35-day run takes a couple of minutes; put_item overwrites by key, so
re-running is safe.

Usage:
    OYA_TABLE_NAME=<table> uv run python scripts/backfill_garmin.py [--days 35]
    uv run python scripts/backfill_garmin.py --table <table> --days 35
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=35, help="how many days back to fetch")
    parser.add_argument("--table", default=os.environ.get("OYA_TABLE_NAME", ""))
    args = parser.parse_args()

    if not args.table:
        parser.error("set OYA_TABLE_NAME or pass --table")
    os.environ["OYA_TABLE_NAME"] = args.table

    # Imported after OYA_TABLE_NAME is set so get_settings() picks it up.
    from oya.integrations.garmin import fetch_day
    from oya.workers.sync_garmin import _write_metrics

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    total = 0

    for i in range(args.days):
        day = yesterday - timedelta(days=i)
        try:
            metrics = fetch_day(day)
        except Exception as exc:  # noqa: BLE001
            print(f"{day}  skipped: {exc}")
            continue

        rows = _write_metrics(metrics)
        total += rows
        present = [
            name
            for name, value in (
                ("sleep", metrics.sleep_minutes),
                ("rhr", metrics.resting_heart_rate),
                ("hrv", metrics.hrv_overnight_avg),
                ("stress", metrics.stress_avg),
                ("bodybatt", metrics.body_battery_at_wake),
                ("steps", metrics.steps),
                ("weight", metrics.weight_lbs),
            )
            if value is not None
        ]
        print(f"{day}  {rows} rows: {', '.join(present) or 'nothing'}")

    print(f"\n{total} rows written across {args.days} days.")


if __name__ == "__main__":
    main()
