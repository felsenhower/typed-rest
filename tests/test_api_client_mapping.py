from typing import Annotated

from pydantic import BaseModel
from rest_rpc import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    Body,
    Header,
    Query,
)


class Item(BaseModel):
    name: str
    price: float


class Result(BaseModel):
    item_id: int
    source: str


def test_full_request_mapping():
    api = ApiDefinition()

    @api.post("/items/{item_id}")
    def update_item(
        item_id: int,
        item: Annotated[Item, Body()],
        q: Annotated[str, Query()],
        h: Annotated[str, Header()],
    ) -> Result: ...

    impl = ApiImplementation(api)

    @impl.handler
    def update_item(item_id, item, q, h):
        return Result(item_id=item_id, source=f"{item.name}:{q}:{h}")

    app = impl.make_fastapi()
    client = ApiClient(api, engine="testclient", app=app)

    result = client.update_item(
        item_id=5,
        item=Item(name="apple", price=1.5),
        q="query",
        h="header",
    )

    assert result == Result(item_id=5, source="apple:query:header")
