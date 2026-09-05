import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.data_stack import DataStack


def _synth() -> Template:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    stack = DataStack(app, "TestData", env=env)
    return Template.from_stack(stack)


def test_meal_photos_bucket_blocks_all_public_access():
    """Meal photos are served only through the API Lambda
    (oya/api/meals.py), never directly -- a public bucket would be the
    first way anyone but the app's one user could read them.
    """
    template = _synth()
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 1

    props = next(iter(buckets.values()))["Properties"]
    assert props["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }


def test_meal_photos_bucket_is_retained_not_deleted_on_stack_removal():
    template = _synth()
    bucket = next(iter(template.find_resources("AWS::S3::Bucket").values()))
    assert bucket["DeletionPolicy"] == "Retain"
