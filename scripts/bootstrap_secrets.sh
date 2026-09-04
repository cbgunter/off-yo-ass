#!/usr/bin/env bash
# Creates the session-signing secret in SSM Parameter Store.
#
# CloudFormation's AWS::SSM::Parameter resource does not support
# SecureString — that's an AWS limitation, not a choice made here — so this
# has to exist before the first `cdk deploy` of OyaApi, created once by
# hand rather than by CDK. Safe to re-run: it overwrites in place, which
# invalidates every existing session (everyone has to sign in again).
set -euo pipefail

PARAM_NAME="/oya/session-secret"
VALUE="$(openssl rand -base64 48)"

aws ssm put-parameter \
  --name "$PARAM_NAME" \
  --type SecureString \
  --value "$VALUE" \
  --overwrite

echo "Wrote $PARAM_NAME (SecureString) to SSM Parameter Store in the default AWS CLI region."
