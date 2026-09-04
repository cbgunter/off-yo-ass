from aws_cdk import Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_route53 as route53
from constructs import Construct

# caseyhunter.net already hosts seven other projects (dgs, golf,
# admin.golf, theturn, app.theturn, trip, electricphactory.golf's own
# zone is separate). This app follows that same one-subdomain-per-project
# convention rather than inventing a new domain.
HOSTED_ZONE_ID = "Z0040614HEUI57PWWJGI"
HOSTED_ZONE_NAME = "caseyhunter.net"
APP_DOMAIN = "oya.caseyhunter.net"


class NetworkStack(Stack):
    """Owns exactly one corner of the shared caseyhunter.net zone: the
    oya.* certificate and its DNS validation record.

    The zone is imported by ID (from_hosted_zone_attributes), never
    created — CDK must never believe it owns a zone with seven live
    projects in it. Every other stack that needs the zone or this
    certificate takes them as constructor arguments from here, so this
    is the only file with the zone ID in it.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "Zone",
            hosted_zone_id=HOSTED_ZONE_ID,
            zone_name=HOSTED_ZONE_NAME,
        )

        self.certificate = acm.Certificate(
            self,
            "Certificate",
            domain_name=APP_DOMAIN,
            validation=acm.CertificateValidation.from_dns(self.hosted_zone),
        )
