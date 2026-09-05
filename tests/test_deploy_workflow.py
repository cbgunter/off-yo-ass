"""Guards a real regression: infra/app.py reads WEATHER_OFFICE/GRID_X/
GRID_Y from the environment at synth time, but .github/workflows/deploy.yml
didn't pass them to the `cdk deploy` step -- so two unrelated deploys
(the privacy-policy pages, then the VAPID env var fix) silently reset the
already-configured weather grid back to empty in production. Nothing
about that was visible locally; only a real `aws lambda
get-function-configuration` against the deployed Coach function caught
it. This test would have failed the moment the omission was introduced.
"""

from pathlib import Path

import yaml

DEPLOY_WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy.yml"

REQUIRED_CDK_DEPLOY_ENV = {
    "GOOGLE_CLIENT_ID",
    "ALLOWED_EMAIL",
    "VAPID_PUBLIC_KEY",
    "WEATHER_OFFICE",
    "WEATHER_GRID_X",
    "WEATHER_GRID_Y",
}


def _cdk_deploy_step() -> dict:
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    (step,) = [s for s in steps if s.get("name") == "cdk deploy"]
    return step


def test_cdk_deploy_step_passes_every_env_var_infra_app_reads_from_the_environment():
    step = _cdk_deploy_step()
    assert REQUIRED_CDK_DEPLOY_ENV <= step["env"].keys()


def test_cdk_deploy_step_deploys_every_stack():
    step = _cdk_deploy_step()
    for stack in ("OyaNetwork", "OyaData", "OyaApi", "OyaFrontend", "OyaWorkers"):
        assert stack in step["run"]
