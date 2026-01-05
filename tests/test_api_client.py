from typing import Annotated, Any

import fastapi
import pytest
from pydantic import BaseModel
from typed_rest import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    Body,
    DecodeError,
    HttpError,
    Query,
    ValidationError,
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
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.simple_route()
    assert result == {"Hello": "World"}


def test_client_with_arg():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/items/{item_id}")
        def route_with_arg(item_id: int) -> dict[str, int]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def route_with_arg(item_id):
            return {"item_id": item_id}

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_arg(item_id=42)
    assert result == {"item_id": 42}


def test_client_with_optional_arg():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/items/{item_id}")
        def route_with_optional_arg(
            item_id: int, q: Annotated[str | None, Query()] = None
        ) -> dict[str, Any]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def route_with_optional_arg(item_id, q):
            return {"item_id": item_id, "q": q}

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_optional_arg(item_id=42, q="Foo")
    assert result == {"item_id": 42, "q": "Foo"}


class ExampleResult(BaseModel):
    item_id: int
    q: str | None


def test_client_with_optional_arg_basemodel():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/items/{item_id}")
        def route_with_optional_arg(
            item_id: int, q: Annotated[str | None, Query()] = None
        ) -> ExampleResult: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def route_with_optional_arg(item_id, q):
            return ExampleResult(item_id=item_id, q=q)

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_optional_arg(item_id=42, q="Foo")
    assert result == ExampleResult(item_id=42, q="Foo")


class Item(BaseModel):
    name: str
    price: float


def test_client_with_post():
    def make_def():
        api_def = ApiDefinition()

        @api_def.post("/items/{item_id}")
        def update_item(
            item_id: int, item: Annotated[Item, Body()]
        ) -> ExampleResult: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def update_item(item_id, item):
            return ExampleResult(
                item_id=item_id, q=f'Item "{item.name}" costs {item.price:0.2f} EUR.'
            )

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.update_item(item_id=42, item=Item(name="Apple", price=3.14))
    assert result == ExampleResult(item_id=42, q='Item "Apple" costs 3.14 EUR.')


def test_client_simple_http_methods():
    def make_def():
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

        return api_def

    api_def = make_def()

    def make_impl(api_def):
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

        return api_impl

    api_impl = make_impl(api_def)

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


def test_client_http_error():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    app = fastapi.FastAPI()

    @app.get("/")
    def simple_route():
        return fastapi.responses.JSONResponse(
            content={"Hello": "World"}, status_code=400
        )

    api_client = ApiClient(api_def, engine="testclient", app=app)
    with pytest.raises(HttpError):
        _ = api_client.simple_route()


def test_client_decode_error():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    app = fastapi.FastAPI()

    @app.get("/")
    def simple_route():
        return fastapi.Response(content="this is not json", media_type="text/plain")

    api_client = ApiClient(api_def, engine="testclient", app=app)
    with pytest.raises(DecodeError):
        _ = api_client.simple_route()


def test_client_validation_error():
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    app = fastapi.FastAPI()

    @app.get("/")
    def simple_route():
        return fastapi.responses.JSONResponse(content={"Hello": 42})

    api_client = ApiClient(api_def, engine="testclient", app=app)
    with pytest.raises(ValidationError):
        _ = api_client.simple_route()
