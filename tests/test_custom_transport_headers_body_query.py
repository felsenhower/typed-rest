from typing import Annotated

from rest_rpc import (
    ApiClient,
    ApiClientEngine,
    ApiDefinition,
    Body,
    Header,
    Query,
    Request,
)


def test_custom_transport_mapping():
    api = ApiDefinition()

    @api.post("/custom")
    def custom(
        q: Annotated[str, Query()],
        h: Annotated[str, Header()],
        body: Annotated[dict, Body()],
    ) -> dict:
        return {}

    def transport(request: Request):
        assert request.method == "POST"
        assert request.path == "/custom"
        assert request.query_params == {"q": "query"}
        assert request.body == {"x": 1}
        assert request.headers == {"h": "head"}
        return {"ok": True}

    client = ApiClient(
        api,
        ApiClientEngine.CUSTOM,
        transport=transport,
    )

    assert client.custom(q="query", h="head", body={"x": 1}) == {"ok": True}
