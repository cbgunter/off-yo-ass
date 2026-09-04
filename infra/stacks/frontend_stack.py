from pathlib import Path

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from constructs import Construct

APP_DOMAIN = "oya.caseyhunter.net"

# Built by `npm run build` in web/ — CI (or you, locally) must build the web
# app before `cdk deploy`; this stack only ships what's already in dist/.
WEB_DIST_PATH = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


class FrontendStack(Stack):
    """The one CloudFront distribution the whole app lives behind: S3 for
    the PWA shell as the default behavior, the API Gateway HTTP API for
    /api/* as a second behavior. Same origin end to end, so the browser
    never makes a cross-origin request and the session cookie just works.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        hosted_zone: route53.IHostedZone,
        certificate: acm.ICertificate,
        http_api: apigwv2.HttpApi,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        api_origin = origins.HttpOrigin(
            f"{http_api.http_api_id}.execute-api.{self.region}.amazonaws.com",
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=[APP_DOMAIN],
            certificate=certificate,
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                # No leading slash — CloudFront strips it from the incoming
                # URI before matching path patterns, so "/api/*" silently
                # never matches anything and every request falls through to
                # the default (S3) behavior. Confirmed the hard way: S3 404s
                # on the nonexistent "api/health" key, and the SPA fallback
                # below quietly turned that into a 200 index.html response,
                # masking a completely unrouted API.
                "api/*": cloudfront.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    # The session cookie and any request body must reach
                    # Lambda unmodified, and responses are never cached —
                    # they carry per-user, per-moment state.
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    # NOT ALL_VIEWER: that policy forwards the viewer's
                    # original Host header (oya.caseyhunter.net) straight
                    # through to API Gateway, which rejects any Host that
                    # doesn't match its own execute-api domain with a bare
                    # 403 — silently turned into a fake 200 index.html by
                    # the SPA fallback below. Confirmed by reproducing it
                    # directly: curl -H "Host: oya.caseyhunter.net" against
                    # the execute-api domain returns 403 ForbiddenException.
                    # This managed policy forwards everything else (cookies,
                    # headers, query strings) but lets CloudFront set Host
                    # to the origin's own domain, as a custom origin needs.
                    origin_request_policy=(
                        cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
                    ),
                ),
            },
            # React Router owns client-side routing — a direct load of
            # /sources has to fall through to index.html, not a CloudFront
            # 403/404 page.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403, response_http_status=200, response_page_path="/index.html"
                ),
                cloudfront.ErrorResponse(
                    http_status=404, response_http_status=200, response_page_path="/index.html"
                ),
            ],
        )

        s3_deployment.BucketDeployment(
            self,
            "DeploySite",
            sources=[s3_deployment.Source.asset(str(WEB_DIST_PATH))],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            cache_control=[
                s3_deployment.CacheControl.from_string("public, max-age=0, must-revalidate")
            ],
        )

        route53.ARecord(
            self,
            "AliasRecordV4",
            zone=hosted_zone,
            record_name="oya",
            target=route53.RecordTarget.from_alias(route53_targets.CloudFrontTarget(distribution)),
        )
        route53.AaaaRecord(
            self,
            "AliasRecordV6",
            zone=hosted_zone,
            record_name="oya",
            target=route53.RecordTarget.from_alias(route53_targets.CloudFrontTarget(distribution)),
        )

        self.distribution = distribution
