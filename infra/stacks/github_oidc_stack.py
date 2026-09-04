from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

# This AWS account already has a GitHub OIDC provider from a prior project
# (GitHubActionsMeatfestRole) — only one provider per URL is allowed per
# account, so this imports it rather than creating a second one.
GITHUB_OIDC_PROVIDER_ARN = (
    "arn:aws:iam::466850516129:oidc-provider/token.actions.githubusercontent.com"
)
GITHUB_REPO = "cbgunter/off-yo-ass"

# GitHub's OIDC `sub` claim embeds immutable numeric IDs alongside the
# owner/repo names — confirmed via `gh api users/cbgunter --jq .id` (user)
# and `gh api repos/cbgunter/off-yo-ass --jq .id` (repo), and matches what
# CloudTrail actually recorded for a real failed AssumeRoleWithWebIdentity
# call. AWS separately *requires* the trust policy to constrain `sub` (or
# job_workflow_ref) directly — a condition on `repository` alone is
# rejected as "not scoped to all" — so both conditions are needed together.
GITHUB_SUB_PATTERN = "repo:cbgunter@10583645/off-yo-ass@1357467340:*"


class GithubOidcStack(Stack):
    """A deploy role for GitHub Actions, trusted only by this repo.

    Mirrors the existing GitHubActionsMeatfestRole pattern already in use
    in this account: PowerUserAccess (everything except IAM) plus
    IAMFullAccess (so CDK can create and manage the Lambda execution role
    it needs). That's broader than a least-privilege CDK bootstrap-role
    hand-off would be — flagged in the plan for a later tightening pass,
    not re-decided here since it matches a working convention this
    account's owner already chose once.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self, "GithubOidcProvider", GITHUB_OIDC_PROVIDER_ARN
        )

        self.role = iam.Role(
            self,
            "DeployRole",
            role_name="GitHubActionsOffYoAssRole",
            assumed_by=iam.FederatedPrincipal(
                provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:repository": GITHUB_REPO,
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": GITHUB_SUB_PATTERN,
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("PowerUserAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("IAMFullAccess"),
            ],
        )
