from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


@lru_cache
def _fetch_ssm_secret(param_name: str) -> str:
    # boto3 ships in the Lambda runtime image itself, so it's deliberately
    # not a project dependency — importing it here, only when this path is
    # actually used, keeps it out of local dev and out of the deploy
    # package that scripts/build_lambda.sh stages.
    import boto3

    ssm = boto3.client("ssm")
    return ssm.get_parameter(Name=param_name, WithDecryption=True)["Parameter"]["Value"]


class Settings(BaseSettings):
    """Runtime config. Values come from OYA_*-prefixed env vars in local
    dev, or from Lambda environment variables plus SSM Parameter Store in
    deployed environments — never a checked-in secret."""

    model_config = SettingsConfigDict(env_prefix="OYA_", env_file=".env", extra="ignore")

    env: str = "development"

    # This app is single-tenant on purpose: one Google account, checked by
    # exact email match on every sign-in.
    google_client_id: str = ""
    allowed_email: str = "cbgunter@gmail.com"

    # Set directly for local dev. In production this is left blank and
    # session_secret_param names an SSM SecureString instead — the CDK
    # stack never sees the plaintext value.
    session_secret: str = ""
    session_secret_param: str = ""
    session_cookie_name: str = "oya_session"
    session_ttl_days: int = 30

    table_name: str = ""

    # VAPID keypair for Web Push. The private key is fetched from SSM by
    # name, same pattern as the session secret; the public key isn't
    # secret and is passed through as a plain env var.
    vapid_public_key: str = ""
    vapid_private_key_param: str = ""
    vapid_subject: str = "mailto:cbgunter@gmail.com"

    garmin_tokenstore_prefix: str = "/oya/garmin/tokenstore"

    @property
    def cookie_secure(self) -> bool:
        # Secure cookies aren't sent back over plain http, which is what
        # local dev talks. Only require it outside development.
        return self.env != "development"

    def resolved_session_secret(self) -> str:
        if self.session_secret:
            return self.session_secret
        if self.session_secret_param:
            return _fetch_ssm_secret(self.session_secret_param)
        return "dev-insecure-secret-change-me"

    def resolved_vapid_private_key(self) -> str:
        if not self.vapid_private_key_param:
            raise RuntimeError("OYA_VAPID_PRIVATE_KEY_PARAM is not configured")
        return _fetch_ssm_secret(self.vapid_private_key_param)


@lru_cache
def get_settings() -> Settings:
    return Settings()
