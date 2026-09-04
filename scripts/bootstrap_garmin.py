#!/usr/bin/env python3
"""One-time Garmin login. Run this on your own machine — it needs your
real Garmin email, password, and MFA code, none of which should ever
touch a Lambda or CI environment. Logs in via `garminconnect`, then
uploads the resulting session tokens to SSM, where
oya/integrations/garmin.py expects to find them.

Safe to re-run any time tokens expire or this needs to move to a new
Garmin account — it always overwrites in place.

Usage (from the repo root, using the project's own venv):
    uv run python scripts/bootstrap_garmin.py
"""

from __future__ import annotations

import getpass
import os
import sys
import tempfile

import boto3
from garminconnect import Garmin

from oya.settings import get_settings


def main() -> None:
    prefix = get_settings().garmin_tokenstore_prefix

    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")

    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA code (check your phone): ").strip(),
    )

    with tempfile.TemporaryDirectory(prefix="garmin-bootstrap-") as tokendir:
        # login(path) unconditionally tries to *load* tokens from that
        # path first (garth.load), and raises a bare FileNotFoundError —
        # not caught internally — when the directory is empty, instead of
        # falling through to credential login. Confirmed against a real
        # account: calling login(tokendir) on a fresh empty dir crashes
        # every time. The fix is to log in with no path (credential-only
        # flow) and save the resulting tokens explicitly afterward.
        client.login()
        print("Logged in. Uploading session tokens to SSM...")
        client.garth.dump(tokendir)

        ssm = boto3.client("ssm")
        count = 0
        for filename in os.listdir(tokendir):
            path = os.path.join(tokendir, filename)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                value = f.read()
            ssm.put_parameter(
                Name=f"{prefix}/{filename}",
                Value=value,
                Type="SecureString",
                Overwrite=True,
            )
            count += 1
            print(f"  uploaded {filename}")

    print(f"Done. {count} token file(s) in SSM under {prefix}.")
    print("The nightly sync picks these up automatically from here.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled — no tokens were uploaded.")
        sys.exit(1)
