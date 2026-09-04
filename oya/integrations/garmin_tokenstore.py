"""Garmin token persistence. `garth` (via `garminconnect`) reads and
writes a small directory of session-token files on login. A Lambda's
`/tmp` doesn't reliably survive between invocations of an infrequent
nightly job, so the real copy lives in SSM — this module is the only
thing that moves files between the two.

Deliberately generic about which files exist: garth's on-disk tokenstore
format is an implementation detail this doesn't need to know. Whatever
scripts/bootstrap_garmin.py uploaded is whatever gets downloaded here.
"""

from __future__ import annotations

import os

import boto3

from oya.settings import get_settings


def download_tokenstore(local_dir: str) -> int:
    """Fetch every SSM parameter under the tokenstore prefix into
    `local_dir`. Returns the file count — zero means no tokens exist yet,
    which the caller should treat as "not bootstrapped"."""
    settings = get_settings()
    ssm = boto3.client("ssm")
    os.makedirs(local_dir, exist_ok=True)

    count = 0
    paginator = ssm.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(
        Path=settings.garmin_tokenstore_prefix, WithDecryption=True, Recursive=True
    ):
        for param in page["Parameters"]:
            filename = param["Name"].rsplit("/", 1)[-1]
            with open(os.path.join(local_dir, filename), "w", encoding="utf-8") as f:
                f.write(param["Value"])
            count += 1
    return count


def upload_tokenstore(local_dir: str) -> None:
    """Push every file in `local_dir` back to SSM. Called after every
    sync so a token `garth` refreshed carries forward to the next
    invocation instead of silently going stale."""
    settings = get_settings()
    ssm = boto3.client("ssm")

    for filename in os.listdir(local_dir):
        path = os.path.join(local_dir, filename)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            value = f.read()
        ssm.put_parameter(
            Name=f"{settings.garmin_tokenstore_prefix}/{filename}",
            Value=value,
            Type="SecureString",
            Overwrite=True,
        )
