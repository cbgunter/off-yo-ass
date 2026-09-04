from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_scheduler as scheduler
from constructs import Construct

# Same asset scripts/build_lambda.sh stages for OyaApi — it already
# includes all of oya/, workers included.
LAMBDA_ASSET_PATH = Path(__file__).resolve().parent.parent / "build" / "lambda"

GARMIN_TOKENSTORE_PREFIX = "/oya/garmin/tokenstore"
VAPID_PRIVATE_KEY_PARAM = "/oya/vapid/private-key"


class WorkersStack(Stack):
    """The nightly sync_garmin Lambda and the schedule that fires it.

    The schedule uses EventBridge Scheduler (aws_scheduler.CfnSchedule),
    not classic EventBridge Rules — Rules are UTC-only with no timezone
    concept, so a fixed UTC cron would silently drift by an hour every
    spring and fall. That's exactly the kind of silent failure this
    phase exists to catch, so 04:30 America/New_York needs to actually
    stay 04:30 year-round. Scheduler is an L1 construct only (no stable
    L2 `Schedule` in aws-cdk-lib), so it needs a small hand-built IAM
    role instead of the L2 Rule's automatic wiring — worth the dozen
    extra lines for correctness that matters here.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.ITable,
        vapid_public_key: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = lambda_.Function(
            self,
            "SyncGarminFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler="oya.workers.sync_garmin.handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ASSET_PATH)),
            memory_size=512,
            # Garmin's API is occasionally slow; a nightly job has no
            # user waiting on it, so there's no reason to run this at
            # API-Gateway-timeout speed.
            timeout=Duration.minutes(2),
            environment={
                "OYA_ENV": "production",
                "OYA_TABLE_NAME": table.table_name,
                "OYA_GARMIN_TOKENSTORE_PREFIX": GARMIN_TOKENSTORE_PREFIX,
                "OYA_VAPID_PUBLIC_KEY": vapid_public_key,
                "OYA_VAPID_PRIVATE_KEY_PARAM": VAPID_PRIVATE_KEY_PARAM,
            },
        )

        table.grant_read_write_data(fn)

        garmin_tokenstore_base_arn = (
            f"arn:aws:ssm:{self.region}:{self.account}:parameter{GARMIN_TOKENSTORE_PREFIX}"
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:PutParameter"],
                # Confirmed the hard way (real AccessDeniedException on a
                # manual invoke): GetParametersByPath authorizes against
                # the bare path ARN, not the "/*" children pattern that
                # GetParameter/PutParameter need — both forms are
                # required together, one alone isn't enough for either.
                resources=[garmin_tokenstore_base_arn, f"{garmin_tokenstore_base_arn}/*"],
            )
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter{VAPID_PRIVATE_KEY_PARAM}"
                ],
            )
        )

        scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        fn.grant_invoke(scheduler_role)

        scheduler.CfnSchedule(
            self,
            "NightlySchedule",
            schedule_expression="cron(30 4 * * ? *)",
            schedule_expression_timezone="America/New_York",
            flexible_time_window={"mode": "OFF"},
            state="ENABLED",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=fn.function_arn,
                role_arn=scheduler_role.role_arn,
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(
                    maximum_retry_attempts=2,
                    maximum_event_age_in_seconds=3600,
                ),
            ),
        )
