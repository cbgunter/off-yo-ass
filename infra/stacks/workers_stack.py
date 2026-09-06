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

# Mirrors the *_param defaults in oya/settings.py — infra and the app are
# separate Python projects (this one never imports `oya`), so these are
# necessarily a second copy of the same literal strings, the same
# pre-existing pattern as api_stack.py's SESSION_SECRET_PARAM.
GARMIN_TOKENSTORE_PREFIX = "/oya/garmin/tokenstore"
VAPID_PRIVATE_KEY_PARAM = "/oya/vapid/private-key"
GOOGLE_CLIENT_SECRET_PARAM = "/oya/google/client-secret"
GOOGLE_REFRESH_TOKEN_PARAM = "/oya/google/refresh-token"
ANTHROPIC_API_KEY_PARAM = "/oya/anthropic/api-key"


class WorkersStack(Stack):
    """Five scheduled Lambdas, one per row in the master plan's daily
    loop table: the nightly Garmin sync, the 15:45 coach call, the 20:30
    check-in reminder, the 21:00 bedtime nudge, and the Sunday weekly
    question.

    Every schedule uses EventBridge Scheduler (aws_scheduler.CfnSchedule),
    not classic EventBridge Rules — Rules are UTC-only with no timezone
    concept, so a fixed UTC cron would silently drift by an hour every
    spring and fall. That's exactly the kind of silent failure this app
    exists to catch, so each of these needs to actually stay at its wall
    clock time year-round. Scheduler is an L1 construct only (no stable
    L2 `Schedule` in aws-cdk-lib), so each one needs a small hand-built
    IAM role instead of the L2 Rule's automatic wiring —
    `_scheduled_function` below is what keeps that from being five
    copy-pasted blocks.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.ITable,
        vapid_public_key: str,
        google_client_id: str,
        weather_office: str,
        weather_grid_x: str,
        weather_grid_y: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.table = table

        common_env = {
            "OYA_ENV": "production",
            "OYA_TABLE_NAME": table.table_name,
            "OYA_VAPID_PUBLIC_KEY": vapid_public_key,
            "OYA_VAPID_PRIVATE_KEY_PARAM": VAPID_PRIVATE_KEY_PARAM,
        }

        self._scheduled_function(
            "SyncGarmin",
            handler="oya.workers.sync_garmin.handler",
            cron="cron(0 8 * * ? *)",  # 08:00 ET
            environment={
                **common_env,
                "OYA_GARMIN_TOKENSTORE_PREFIX": GARMIN_TOKENSTORE_PREFIX,
            },
            ssm_read=[VAPID_PRIVATE_KEY_PARAM],
            ssm_read_write_path=[GARMIN_TOKENSTORE_PREFIX],
            grant_table_write=True,
            # Re-fetches a trailing week of days, each ~7 Garmin calls.
            timeout=Duration.minutes(5),
        )

        self._scheduled_function(
            "Coach",
            handler="oya.workers.coach.handler",
            cron="cron(45 15 * * ? *)",  # 15:45 ET — the daily call
            environment={
                **common_env,
                "OYA_GOOGLE_CLIENT_ID": google_client_id,
                "OYA_WEATHER_OFFICE": weather_office,
                "OYA_WEATHER_GRID_X": weather_grid_x,
                "OYA_WEATHER_GRID_Y": weather_grid_y,
            },
            ssm_read=[
                VAPID_PRIVATE_KEY_PARAM,
                GOOGLE_CLIENT_SECRET_PARAM,
                GOOGLE_REFRESH_TOKEN_PARAM,
                ANTHROPIC_API_KEY_PARAM,
            ],
            grant_table_write=True,
        )

        self._scheduled_function(
            "Checkin",
            handler="oya.workers.checkin.handler",
            cron="cron(30 20 * * ? *)",  # 20:30 ET — fixed-copy reminder, no LLM
            environment=common_env,
            ssm_read=[VAPID_PRIVATE_KEY_PARAM],
            grant_table_write=False,
        )

        self._scheduled_function(
            "Bedtime",
            handler="oya.workers.bedtime.handler",
            cron="cron(0 21 * * ? *)",  # 21:00 ET — deterministic, no LLM
            environment={**common_env, "OYA_GOOGLE_CLIENT_ID": google_client_id},
            ssm_read=[
                VAPID_PRIVATE_KEY_PARAM,
                GOOGLE_CLIENT_SECRET_PARAM,
                GOOGLE_REFRESH_TOKEN_PARAM,
            ],
            # Writes one BEDTIME row per night so the nudge persists on the
            # Call screen until the next run.
            grant_table_write=True,
        )

        self._scheduled_function(
            "WeeklyQuestion",
            handler="oya.workers.weekly_question.handler",
            cron="cron(0 19 ? * SUN *)",  # Sunday 19:00 ET
            environment=common_env,
            ssm_read=[VAPID_PRIVATE_KEY_PARAM, ANTHROPIC_API_KEY_PARAM],
            grant_table_write=True,
        )

    def _scheduled_function(
        self,
        name: str,
        *,
        handler: str,
        cron: str,
        environment: dict[str, str],
        ssm_read: list[str] | None = None,
        ssm_read_write_path: list[str] | None = None,
        grant_table_write: bool,
        timeout: Duration | None = None,
    ) -> lambda_.Function:
        fn = lambda_.Function(
            self,
            f"{name}Function",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler=handler,
            code=lambda_.Code.from_asset(str(LAMBDA_ASSET_PATH)),
            memory_size=512,
            # None of these five have a user waiting on them synchronously
            # — no reason to run at API-Gateway-timeout speed.
            timeout=timeout or Duration.minutes(2),
            environment=environment,
        )

        if grant_table_write:
            self.table.grant_read_write_data(fn)
        else:
            self.table.grant_read_data(fn)

        for param in ssm_read or []:
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["ssm:GetParameter"],
                    resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{param}"],
                )
            )

        for param in ssm_read_write_path or []:
            # Confirmed the hard way (a real AccessDeniedException on a
            # manual invoke, phase 1): GetParametersByPath authorizes
            # against the bare path ARN, not the "/*" children pattern
            # that GetParameter/PutParameter need — both forms have to be
            # granted together.
            base_arn = f"arn:aws:ssm:{self.region}:{self.account}:parameter{param}"
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:PutParameter"],
                    resources=[base_arn, f"{base_arn}/*"],
                )
            )

        scheduler_role = iam.Role(
            self,
            f"{name}SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        fn.grant_invoke(scheduler_role)

        scheduler.CfnSchedule(
            self,
            f"{name}Schedule",
            schedule_expression=cron,
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
        return fn
