from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

# Produced by scripts/build_lambda.sh — plain pip wheels, no Docker. Run
# that script before `cdk synth` / `cdk deploy`.
LAMBDA_ASSET_PATH = Path(__file__).resolve().parent.parent / "build" / "lambda"

# A SecureString, created out of band (CloudFormation's AWS::SSM::Parameter
# does not support SecureString — this has to exist before first deploy).
# See scripts/bootstrap_secrets.sh.
SESSION_SECRET_PARAM = "/oya/session-secret"


class ApiStack(Stack):
    """The FastAPI app on Lambda, fronted by an HTTP API with no custom
    domain of its own — FrontendStack's CloudFront distribution proxies
    /api/* straight to this API Gateway's default execute-api endpoint,
    which is what keeps the whole app same-origin with no CORS handling
    anywhere in the codebase."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.ITable,
        google_client_id: str,
        allowed_email: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler="oya.api.handler.handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ASSET_PATH)),
            memory_size=512,
            timeout=Duration.seconds(15),
            environment={
                "OYA_ENV": "production",
                "OYA_GOOGLE_CLIENT_ID": google_client_id,
                "OYA_ALLOWED_EMAIL": allowed_email,
                "OYA_TABLE_NAME": table.table_name,
                "OYA_SESSION_SECRET_PARAM": SESSION_SECRET_PARAM,
            },
        )

        table.grant_read_write_data(fn)

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{SESSION_SECRET_PARAM}"],
            )
        )

        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            default_integration=apigwv2_integrations.HttpLambdaIntegration("Integration", fn),
        )
