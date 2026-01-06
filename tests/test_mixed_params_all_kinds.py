from typing import Annotated

from rest_rpc import (
    ApiClient,
    ApiClientEngine,
    ApiDefinition,
    Body,
    Header,
    Path,
    Query,
)


def test_all_param_kinds_together():
    api = ApiDefinition()

    @api.put("/items/{item_id}")
    def update(
        item_id: Annotated[int, Path()],
        q: Annotated[str, Query()],
        h: Annotated[str, Header()],
        body: Annotated[dict, Body()],
    ) -> dict:
        return {"item_id": item_id, "q": q, "h": h, **body}

    from rest_rpc import ApiImplementation

    impl = ApiImplementation(api)

    @impl.handler
    def update(item_id: int, q: str, h: str, body: dict) -> dict:
        return {"item_id": item_id, "q": q, "h": h, **body}

    app = impl.make_fastapi()
    client = ApiClient(api, ApiClientEngine.TESTCLIENT, app=app)

    result = client.update(
        item_id=1,
        q="query",
        h="header",
        body={"name": "apple"},
    )

    assert result == {
        "item_id": 1,
        "q": "query",
        "h": "header",
        "name": "apple",
    }
