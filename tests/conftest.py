import pytest
from fastapi.testclient import TestClient

from oya.api.app import app
from oya.settings import Settings, get_settings


def _test_settings() -> Settings:
    return Settings(
        env="development",
        google_client_id="test-client-id",
        allowed_email="cbgunter@gmail.com",
        session_secret="test-secret",
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = _test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
