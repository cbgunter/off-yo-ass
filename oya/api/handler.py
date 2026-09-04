"""Lambda entry point. API Gateway (HTTP API) invokes this; Mangum adapts the
ASGI app to the Lambda event/response shape."""

from mangum import Mangum

from oya.api.app import app

handler = Mangum(app)
