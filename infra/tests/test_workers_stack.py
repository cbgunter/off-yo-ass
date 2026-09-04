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
        app, "TestWorkers", table=table, vapid_public_key="test-public-key", env=env
    )
    return Template.from_stack(workers)


def test_nightly_sync_runs_on_a_real_wall_clock_time_not_bare_utc():
    """Classic EventBridge Rules have no timezone concept — a fixed UTC
    cron silently drifts by an hour every DST transition, which is
    exactly the kind of silent failure this phase exists to catch. This
    locks in that the schedule is EventBridge *Scheduler* (which supports
    IANA timezones) with the timezone actually set, not a bare cron.
    """
    template = _synth_workers_template()

    schedules = template.find_resources("AWS::Scheduler::Schedule")
    assert len(schedules) == 1
    (schedule,) = schedules.values()
    props = schedule["Properties"]

    assert props["ScheduleExpressionTimezone"] == "America/New_York"
    assert props["ScheduleExpression"] == "cron(30 4 * * ? *)"
    assert props["State"] == "ENABLED"
