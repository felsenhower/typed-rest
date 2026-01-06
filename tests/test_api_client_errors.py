import fastapi
import pytest
from rest_rpc import (
    ApiClient,
    ApiDefinition,
    DecodeError,
    HttpError,
    ValidationError,
)


def make_api():
    api = ApiDefinition()

    @api.get("/")
    def root() -> dict[str, str]: ...

    return api


def test_http_error():
    api = make_api()

    app = fastapi.FastAPI()

    @app.get("/")
    def root():
        return fastapi.responses.JSONResponse({"x": 1}, status_code=400)

    client = ApiClient(api, engine="testclient", app=app)
    with pytest.raises(HttpError):
        client.root()


def test_decode_error():
    api = make_api()

    app = fastapi.FastAPI()

    @app.get("/")
    def root():
        return fastapi.Response("not json", media_type="text/plain")

    client = ApiClient(api, engine="testclient", app=app)
    with pytest.raises(DecodeError):
        client.root()


def test_validation_error():
    api = make_api()

    app = fastapi.FastAPI()

    @app.get("/")
    def root():
        return {"x": 1}

    client = ApiClient(api, engine="testclient", app=app)
    with pytest.raises(ValidationError):
        client.root()
