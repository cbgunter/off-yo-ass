import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Template

from stacks.api_stack import ApiStack


def _synth_api_template() -> Template:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    support = cdk.Stack(app, "TestSupport", env=env)

    table = dynamodb.Table(
        support,
        "TestTable",
        partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
    )
    bucket = s3.Bucket(support, "TestBucket")

    api = ApiStack(
        app,
        "TestApi",
        table=table,
        meal_photos_bucket=bucket,
        google_client_id="test-client-id",
        allowed_email="cbgunter@gmail.com",
        env=env,
    )
    return Template.from_stack(api)


def test_api_function_has_the_meal_photos_bucket_name_in_its_environment():
    template = _synth_api_template()
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == 1

    env_vars = next(iter(functions.values()))["Properties"]["Environment"]["Variables"]
    assert "OYA_MEAL_PHOTOS_BUCKET" in env_vars


def test_api_function_can_read_and_write_the_meal_photos_bucket():
    """oya/api/meals.py both writes photos (POST /api/meals/analyze) and
    reads them back (GET /api/meals/photo/{id}) -- granting only one
    direction would 403 on whichever route needs the other, the same
    class of bug the workers' SSM policy split already caught once.
    """
    template = _synth_api_template()

    s3_statements = [
        stmt
        for policy in template.find_resources("AWS::IAM::Policy").values()
        for stmt in policy["Properties"]["PolicyDocument"]["Statement"]
        if any(a.startswith("s3:") for a in _as_list(stmt["Action"]))
    ]
    assert s3_statements, "expected an S3 IAM policy statement for the meal photos bucket"

    actions = {a for stmt in s3_statements for a in _as_list(stmt["Action"])}
    assert any(a.startswith("s3:GetObject") for a in actions)
    assert any(a.startswith("s3:PutObject") for a in actions)


def _as_list(value):
    return value if isinstance(value, list) else [value]
