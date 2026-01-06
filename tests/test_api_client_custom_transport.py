import fastapi.testclient
from rest_rpc import ApiClient, ApiDefinition, ApiImplementation, Request


def test_custom_sync_transport():
    api = ApiDefinition()

    @api.get("/")
    def root() -> dict[str, str]: ...

    impl = ApiImplementation(api)

    @impl.handler
    def root():
        return {"ok": "yes"}

    app = impl.make_fastapi()
    testclient = fastapi.testclient.TestClient(app)

    def transport(request: Request):
        response = testclient.request(
            method=request.method,
            url=request.path,
            params=request.query_params,
            json=request.body,
            headers=request.headers,
        )
        response.raise_for_status()
        return response.json()

    client = ApiClient(api, engine="custom", transport=transport)
    assert client.root() == {"ok": "yes"}
