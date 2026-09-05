from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from oya.api.app import app
from oya.settings import get_settings

TEST_TABLE_NAME = "test-oya-table"

# Settings is env-driven (pydantic-settings) and get_settings() is
# lru_cache'd, so code that calls get_settings() directly — like
# oya/store/table.py, outside of any route's Depends() — never sees
# app.dependency_overrides. Driving config through real env vars plus a
# cache clear makes every call path, DI or direct, see the same config.
TEST_ENV = {
    "OYA_ENV": "development",
    "OYA_GOOGLE_CLIENT_ID": "test-client-id",
    "OYA_ALLOWED_EMAIL": "cbgunter@gmail.com",
    "OYA_SESSION_SECRET": "test-secret",
    "OYA_TABLE_NAME": TEST_TABLE_NAME,
    "OYA_ANTHROPIC_API_KEY": "sk-ant-test-fake",
    "OYA_GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "OYA_GOOGLE_REFRESH_TOKEN": "test-google-refresh-token",
    "AWS_DEFAULT_REGION": "us-east-1",
}


@pytest.fixture
def dynamodb_table(monkeypatch):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.create_table(
            TableName=TEST_TABLE_NAME,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table

    get_settings.cache_clear()


@pytest.fixture
def client(dynamodb_table):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed_client(client):
    """A client that's already signed in — most protected-route tests
    don't care about the auth flow itself, just that something's behind
    it."""
    with patch("oya.api.auth.google_id_token.verify_oauth2_token") as verify:
        verify.return_value = {
            "email": "cbgunter@gmail.com",
            "email_verified": True,
            "name": "Casey",
        }
        client.post("/api/auth/google", json={"id_token": "fake"})
    return client
