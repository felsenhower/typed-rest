import pytest

from typed_rest import ApiDefinition, ApiImplementation, ApiClient

from pydantic import BaseModel


def test_client_simple():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]:
        pass

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
    def route_with_arg(item_id: int) -> dict[str, int]:
        pass

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
    ) -> dict[str, int | str | None]:
        pass

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
    def route_with_optional_arg(item_id: int, q: str | None = None) -> ExampleResult:
        pass

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def route_with_optional_arg(item_id, q):
        return ExampleResult(item_id=item_id, q=q)

    app = api_impl.make_fastapi()
    api_client = ApiClient(api_def, engine="testclient", app=app)
    result = api_client.route_with_optional_arg(item_id=42, q="Foo")
    assert ExampleResult(item_id=42, q="Foo")
