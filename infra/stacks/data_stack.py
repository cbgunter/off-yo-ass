from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct


class DataStack(Stack):
    """One DynamoDB table for one user.

    Partition key groups by entity (SLEEP, HRV, RHR, CALL, OUTCOME, NOTE,
    ...), sort key is an ISO timestamp, so "this entity, this date range"
    — every read pattern in this app — is a native query. The by-date GSI
    answers "everything for this one day" for the dashboard in a single
    query instead of six.

    RemovalPolicy.RETAIN on purpose: `cdk destroy` must never be able to
    take sleep and heart-rate history with it.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = dynamodb.Table(
            self,
            "Table",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.table.add_global_secondary_index(
            index_name="by-date",
            partition_key=dynamodb.Attribute(name="date", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
        )

        # CDK auto-generates the actual table name (e.g.
        # OyaData-TableCD117FA1-...) — an explicit, named output is what
        # lets scripts/weekly_health_check.py look it up from outside the
        # CDK app, via `aws cloudformation describe-stacks`, without
        # hardcoding that generated name anywhere.
        CfnOutput(self, "TableName", value=self.table.table_name, export_name="OyaDataTableName")

        # Meal photos -- the first non-website bucket in the app. Private:
        # photos are only ever served back through the API Lambda
        # (oya/api/meals.py), never directly, so there's no CORS rule and
        # no CloudFront behavior for it, keeping the app's one deliberate
        # same-origin invariant intact.
        self.meal_photos_bucket = s3.Bucket(
            self,
            "MealPhotosBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )
