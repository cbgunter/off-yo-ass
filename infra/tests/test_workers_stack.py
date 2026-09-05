import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk.assertions import Template

from stacks.workers_stack import WorkersStack


def _synth_workers_template() -> Template:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    support = cdk.Stack(app, "TestSupport", env=env)

    table = dynamodb.Table(
        support,
        "TestTable",
        partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
    )

    workers = WorkersStack(
        app,
        "TestWorkers",
        table=table,
        vapid_public_key="test-public-key",
        google_client_id="test-client-id",
        weather_office="PHI",
        weather_grid_x="50",
        weather_grid_y="75",
        env=env,
    )
    return Template.from_stack(workers)


# One entry per _scheduled_function call in WorkersStack.__init__, in the
# same order — a mismatch here is itself a sign one of the two drifted.
EXPECTED_SCHEDULES = {
    "SyncGarmin": "cron(30 4 * * ? *)",
    "Coach": "cron(45 15 * * ? *)",
    "Checkin": "cron(30 20 * * ? *)",
    "Bedtime": "cron(0 21 * * ? *)",
    "WeeklyQuestion": "cron(0 19 ? * SUN *)",
}


def test_every_worker_runs_on_a_real_wall_clock_time_not_bare_utc():
    """Classic EventBridge Rules have no timezone concept -- a fixed UTC
    cron silently drifts by an hour every DST transition, which is
    exactly the kind of silent failure this app exists to catch. This
    locks in that all five schedules are EventBridge *Scheduler* (which
    supports IANA timezones) with the timezone actually set and the
    expected cron expression, not a bare UTC cron -- parameterized across
    all five now that _scheduled_function makes that the same code path
    for each.
    """
    template = _synth_workers_template()

    schedules = template.find_resources("AWS::Scheduler::Schedule")
    assert len(schedules) == len(EXPECTED_SCHEDULES)

    by_expression = {s["Properties"]["ScheduleExpression"]: s for s in schedules.values()}
    for name, expression in EXPECTED_SCHEDULES.items():
        schedule = by_expression.get(expression)
        assert schedule is not None, f"no schedule found for {name} ({expression})"
        props = schedule["Properties"]
        assert props["ScheduleExpressionTimezone"] == "America/New_York", name
        assert props["State"] == "ENABLED", name


def test_five_lambda_functions_are_created_one_per_worker():
    template = _synth_workers_template()
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == len(EXPECTED_SCHEDULES)


def test_garmin_tokenstore_policy_grants_both_the_bare_path_and_its_children():
    """Confirmed the hard way against the real deployed stack:
    ssm:GetParametersByPath authorizes against the bare path ARN
    ("/oya/garmin/tokenstore"), while GetParameter/PutParameter need the
    "/*" children pattern -- a policy granting only one of the two fails
    with AccessDeniedException on whichever action needs the other. This
    locks in that both are present together.
    """
    template = _synth_workers_template()

    statements = [
        stmt
        for policy in template.find_resources("AWS::IAM::Policy").values()
        for stmt in policy["Properties"]["PolicyDocument"]["Statement"]
        if "ssm:GetParametersByPath" in _as_list(stmt["Action"])
    ]
    assert len(statements) == 1

    resources = _as_list(statements[0]["Resource"])
    base = "arn:aws:ssm:us-east-1:123456789012:parameter/oya/garmin/tokenstore"
    assert base in resources
    assert f"{base}/*" in resources


def _as_list(value):
    return value if isinstance(value, list) else [value]
