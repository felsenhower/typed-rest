import pytest

from typed_rest import ApiDefinition, ApiImplementation, ApiClient, HttpError

from pydantic import BaseModel


def test_client_simple_requests(fastapi_server):
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

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
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    app = api_impl.make_fastapi()

    api_client = ApiClient(
        api_def,
        engine="requests",
        base_url="http://example.org/hopefully/there/is/no/api/here",
    )
    with pytest.raises(HttpError):
        _ = api_client.simple_route()
