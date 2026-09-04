#!/usr/bin/env bash
# Stages the FastAPI app as a Lambda deployment package, without Docker.
#
# CDK's usual PythonFunction bundling shells out to Docker to match the
# Lambda execution environment. This machine (and the GitHub Actions
# runner) doesn't need that here: every backend dependency ships
# manylinux wheels, so `uv pip install --target` with an explicit
# platform/version pulls the right prebuilt wheels directly from PyPI.
# Run this before `cdk synth` or `cdk deploy` — infra/stacks/api_stack.py
# points straight at its output directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/infra/build/lambda"

rm -rf "$OUT"
mkdir -p "$OUT"

uv pip install \
  --target "$OUT" \
  --python-platform x86_64-manylinux2014 \
  --python-version 3.13 \
  "$ROOT"

# boto3/botocore ship in the Lambda runtime image itself — stripping them
# here keeps the package small and avoids shipping a version that could
# drift from the runtime's.
rm -rf "$OUT"/boto3* "$OUT"/botocore* "$OUT"/s3transfer* "$OUT"/dateutil* "$OUT"/jmespath*

echo "Lambda package staged at $OUT"
du -sh "$OUT" 2>/dev/null || true
