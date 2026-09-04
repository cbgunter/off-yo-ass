import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_route53 as route53
from aws_cdk.assertions import Template

from stacks.frontend_stack import FrontendStack


def _synth_frontend_template() -> Template:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    support = cdk.Stack(app, "TestSupport", env=env)

    hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
        support, "Zone", hosted_zone_id="Z0000000000000ZONE", zone_name="example.com"
    )
    certificate = acm.Certificate.from_certificate_arn(
        support, "Cert", "arn:aws:acm:us-east-1:123456789012:certificate/test-cert"
    )
    http_api = apigwv2.HttpApi(support, "TestHttpApi")

    frontend = FrontendStack(
        app,
        "TestFrontend",
        hosted_zone=hosted_zone,
        certificate=certificate,
        http_api=http_api,
        env=env,
    )
    return Template.from_stack(frontend)


def test_api_behavior_path_pattern_has_no_leading_slash():
    """A leading slash on a CloudFront additional-behavior path pattern
    makes it silently never match — CloudFront strips the leading slash
    from the incoming URI before comparing, so "/api/*" matches nothing
    and every request falls through to the default (S3) behavior.

    Caught this the hard way on the first live deploy: it looked like a
    success (200 OK) because the SPA's 404-to-index.html fallback quietly
    served the app shell instead of the actual API response. This test
    exists so that regression can't happen silently again.
    """
    template = _synth_frontend_template()

    resources = template.find_resources("AWS::CloudFront::Distribution")
    assert len(resources) == 1
    (distribution,) = resources.values()

    cache_behaviors = distribution["Properties"]["DistributionConfig"]["CacheBehaviors"]
    assert len(cache_behaviors) == 1
    path_pattern = cache_behaviors[0]["PathPattern"]

    assert not path_pattern.startswith("/"), (
        f"CloudFront path pattern {path_pattern!r} starts with '/' and will never match"
    )
    assert path_pattern == "api/*"


def test_api_behavior_does_not_forward_the_viewer_host_header():
    """ALL_VIEWER forwards the viewer's original Host header
    (oya.caseyhunter.net) straight through to the API Gateway origin,
    which rejects any Host that doesn't match its own execute-api domain
    with a bare 403 — which the SPA's 403-to-index.html fallback then
    silently turned into a fake 200. Reproduced directly: curl -H "Host:
    oya.caseyhunter.net" against the raw execute-api endpoint returns 403
    ForbiddenException. ALL_VIEWER_EXCEPT_HOST_HEADER is AWS's managed
    policy for exactly this: forward everything else, let CloudFront set
    Host to the origin's own domain.
    """
    template = _synth_frontend_template()

    resources = template.find_resources("AWS::CloudFront::Distribution")
    (distribution,) = resources.values()
    cache_behaviors = distribution["Properties"]["DistributionConfig"]["CacheBehaviors"]

    all_viewer = "216adef6-5c7f-47e4-b989-5492eafa07d3"
    all_viewer_except_host = "b689b0a8-53d0-40ab-baf2-68738e2966ac"

    policy_id = cache_behaviors[0]["OriginRequestPolicyId"]
    assert policy_id != all_viewer, "ALL_VIEWER forwards Host and breaks API Gateway routing"
    assert policy_id == all_viewer_except_host
