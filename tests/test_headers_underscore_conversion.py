from typing import Annotated

from rest_rpc import ApiClient, ApiClientEngine, ApiDefinition, Header


def test_header_underscore_conversion():
    api = ApiDefinition()

    @api.get("/headers")
    def read_headers(x_token: Annotated[str, Header()]) -> str:
        return x_token

    from rest_rpc import ApiImplementation

    impl = ApiImplementation(api)

    @impl.handler
    def read_headers(x_token: str) -> str:
        return x_token

    app = impl.make_fastapi()
    client = ApiClient(api, ApiClientEngine.TESTCLIENT, app=app)

    # FastAPI converts x_token <-> X-Token
    assert client.read_headers(x_token="secret") == "secret"
