#!/usr/bin/env python3
"""Generates the VAPID keypair Web Push needs, once. Uploads the private
key to SSM as a SecureString (never touches disk) and prints the public
key, which isn't secret — set it as the VITE_VAPID_PUBLIC_KEY GitHub
Actions repo variable.

Safe to re-run, but doing so invalidates every existing push subscription
(the browser's applicationServerKey would no longer match) — everyone
who enabled notifications would need to do it again.

Usage (from the repo root, using the project's own venv):
    uv run python scripts/bootstrap_vapid.py
"""

from __future__ import annotations

import boto3
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urlencode, num_to_bytes

PRIVATE_KEY_PARAM = "/oya/vapid/private-key"


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()

    # Raw 32-byte private scalar, base64url-encoded — the one string
    # format pywebpush's Vapid.from_string() actually round-trips (it
    # tries a file path first, then assumes base64url RAW-or-DER; a PEM
    # string with headers and newlines doesn't parse as either).
    private_raw = num_to_bytes(vapid.private_key.private_numbers().private_value, 32)
    private_b64 = b64urlencode(private_raw)

    # Uncompressed EC point, base64url-encoded — the exact
    # applicationServerKey shape PushManager.subscribe() expects in the
    # browser.
    public_raw = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_b64 = b64urlencode(public_raw)

    ssm = boto3.client("ssm")
    ssm.put_parameter(
        Name=PRIVATE_KEY_PARAM, Value=private_b64, Type="SecureString", Overwrite=True
    )

    print(f"Private key stored in SSM at {PRIVATE_KEY_PARAM}.")
    print()
    print("Public key (not secret) — set this as the VITE_VAPID_PUBLIC_KEY GitHub repo variable:")
    print()
    print(f"  {public_b64}")


if __name__ == "__main__":
    main()
