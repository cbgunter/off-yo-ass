import os

import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.data_stack import DataStack
from stacks.frontend_stack import FrontendStack
from stacks.github_oidc_stack import GithubOidcStack
from stacks.network_stack import NetworkStack

app = cdk.App()

# Everything lives in one region: CloudFront needs its certificate in
# us-east-1 anyway, and there's no reason to spread a single-user app
# across regions.
env = cdk.Environment(account="466850516129", region="us-east-1")

# Deployed once, manually, from an already-authenticated AWS CLI session —
# never by the GitHub Actions workflow this role itself authorizes. See
# stacks/github_oidc_stack.py.
GithubOidcStack(app, "OyaGithubOidc", env=env)

network = NetworkStack(app, "OyaNetwork", env=env)
data = DataStack(app, "OyaData", env=env)

api = ApiStack(
    app,
    "OyaApi",
    table=data.table,
    # Client IDs aren't secret — set as a plain GitHub Actions repo
    # variable once the phase-2 Google Cloud project exists. Empty is a
    # valid placeholder: sign-in just refuses everyone until it's set.
    google_client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    allowed_email=os.environ.get("ALLOWED_EMAIL", "cbgunter@gmail.com"),
    env=env,
)

FrontendStack(
    app,
    "OyaFrontend",
    hosted_zone=network.hosted_zone,
    certificate=network.certificate,
    http_api=api.http_api,
    env=env,
)

app.synth()
