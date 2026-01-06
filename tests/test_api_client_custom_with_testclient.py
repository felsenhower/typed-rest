import fastapi
import fastapi.testclient
from rest_rpc import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    Request,
)


def test_client_simple():
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

    testclient = fastapi.testclient.TestClient(app)

    def transport(
        request: Request,
    ):
        response = testclient.request(
            method=request.method,
            url=request.path,
            params=request.query_params,
            json=request.body,
            headers=request.headers,
        )
        response.raise_for_status()
        return response.json()

    api_client = ApiClient(api_def, engine="custom", transport=transport)
    result = api_client.simple_route()
    assert result == {"Hello": "World"}
