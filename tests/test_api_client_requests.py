import fastapi
import pytest
from rest_rpc import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    DecodeError,
    HttpError,
    NetworkError,
    ValidationError,
)


def test_client_simple_requests(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return {"Hello": "World"}

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        api_client = ApiClient(
            api_def,
            engine="requests",
            base_url=base_url,
        )
        result = api_client.simple_route()
    assert result == {"Hello": "World"}


def test_network_error():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    api_client = ApiClient(
        api_def,
        engine="requests",
        base_url="http://i-made-up-this-url-4e40ac92-3df4-4aa9-9a6a-d6da534a67cf.org/api",
    )
    with pytest.raises(NetworkError):
        _ = api_client.simple_route()


def test_http_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return fastapi.responses.JSONResponse(
                content={"Hello": "World"}, status_code=400
            )

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        api_client = ApiClient(
            api_def,
            engine="requests",
            base_url=base_url,
        )
        with pytest.raises(HttpError):
            _ = api_client.simple_route()


def test_decode_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return fastapi.Response(content="this is not json", media_type="text/plain")

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        api_client = ApiClient(
            api_def,
            engine="requests",
            base_url=base_url,
        )
        with pytest.raises(DecodeError):
            _ = api_client.simple_route()


def test_validation_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return fastapi.responses.JSONResponse(content={"Hello": 42})

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        api_client = ApiClient(
            api_def,
            engine="requests",
            base_url=base_url,
        )
        with pytest.raises(ValidationError):
            _ = api_client.simple_route()
