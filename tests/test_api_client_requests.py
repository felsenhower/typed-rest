import pytest
from typed_rest import ApiClient, ApiDefinition, ApiImplementation, HttpError


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

    def make_impl():
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return {"Hello": "World"}

        return api_impl

    api_impl = make_impl(api_def)

    _ = api_impl.make_fastapi()

    api_client = ApiClient(
        api_def,
        engine="requests",
        base_url="http://example.org/hopefully/there/is/no/api/here",
    )
    with pytest.raises(HttpError):
        _ = api_client.simple_route()
