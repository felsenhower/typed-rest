from typing import Any

import pytest

from typed_rest import (
    ApiDefinition,
    ApiImplementation,
    ApiClient,
    HttpError,
    DecodeError,
)

from pydantic import BaseModel

import fastapi


def test_client_simple():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.simple_route()
    assert result == {"Hello": "World"}


def test_client_with_arg():
    api_def = ApiDefinition()

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, int]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def route_with_arg(item_id):
        return {"item_id": item_id}

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_arg(item_id=42)
    assert result == {"item_id": 42}


def test_client_with_arg():
    api_def = ApiDefinition()

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, Any]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def route_with_optional_arg(item_id, q):
        return {"item_id": item_id, "q": q}

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_optional_arg(item_id=42, q="Foo")
    assert result == {"item_id": 42, "q": "Foo"}


class ExampleResult(BaseModel):
    item_id: int
    q: str | None


def test_client_with_optional_arg():
    api_def = ApiDefinition()

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> ExampleResult: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def route_with_optional_arg(item_id, q):
        return ExampleResult(item_id=item_id, q=q)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_optional_arg(item_id=42, q="Foo")
    assert ExampleResult(item_id=42, q="Foo")


def test_client_simple_http_methods():
    api_def = ApiDefinition()

    @api_def.delete("/")
    def delete_route() -> dict[str, str]: ...

    @api_def.get("/")
    def get_route() -> dict[str, str]: ...

    @api_def.patch("/")
    def patch_route() -> dict[str, str]: ...

    @api_def.post("/")
    def post_route() -> dict[str, str]: ...

    @api_def.put("/")
    def put_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def delete_route():
        return {"Hello": "World"}

    @api_impl.handler
    def get_route():
        return {"Hello": "World"}

    @api_impl.handler
    def patch_route():
        return {"Hello": "World"}

    @api_impl.handler
    def post_route():
        return {"Hello": "World"}

    @api_impl.handler
    def put_route():
        return {"Hello": "World"}

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.delete_route()
    assert result == {"Hello": "World"}
    result = api_client.get_route()
    assert result == {"Hello": "World"}
    result = api_client.patch_route()
    assert result == {"Hello": "World"}
    result = api_client.post_route()
    assert result == {"Hello": "World"}
    result = api_client.put_route()
    assert result == {"Hello": "World"}


def test_client_network_error():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    app = fastapi.FastAPI()

    api_client = ApiClient(api_def, engine="testclient", app=app)
    with pytest.raises(HttpError):
        _ = api_client.simple_route()


def test_client_decode_error():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    app = fastapi.FastAPI()

    @app.get("/")
    def simple_route():
        return fastapi.Response(content="this is not json", media_type="text/plain")

    api_client = ApiClient(api_def, engine="testclient", app=app)
    with pytest.raises(DecodeError):
        _ = api_client.simple_route()
