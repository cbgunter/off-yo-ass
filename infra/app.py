import os

import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.data_stack import DataStack
from stacks.frontend_stack import FrontendStack
from stacks.github_oidc_stack import GithubOidcStack
from stacks.network_stack import NetworkStack
from stacks.workers_stack import WorkersStack

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
    weather_office=os.environ.get("WEATHER_OFFICE", ""),
    weather_grid_x=os.environ.get("WEATHER_GRID_X", ""),
    weather_grid_y=os.environ.get("WEATHER_GRID_Y", ""),
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

WorkersStack(
    app,
    "OyaWorkers",
    table=data.table,
    # Not secret — the applicationServerKey a browser needs to subscribe
    # to push is public by design. Generated once by
    # scripts/bootstrap_vapid.py, set as a plain GitHub Actions repo
    # variable the same way GOOGLE_CLIENT_ID is.
    vapid_public_key=os.environ.get("VAPID_PUBLIC_KEY", ""),
    google_client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    # NWS grid coordinates for the home ZIP — not secret, just config,
    # resolved once by scripts/resolve_weather_grid.py. Empty is a valid
    # placeholder: the coach just reports weather as unavailable.
    weather_office=os.environ.get("WEATHER_OFFICE", ""),
    weather_grid_x=os.environ.get("WEATHER_GRID_X", ""),
    weather_grid_y=os.environ.get("WEATHER_GRID_Y", ""),
    env=env,
)

app.synth()
