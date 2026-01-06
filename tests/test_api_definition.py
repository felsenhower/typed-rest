from typing import Annotated

import pytest
from pydantic import BaseModel
from rest_rpc import ApiDefinition, Body, Query


class Item(BaseModel):
    name: str
    price: float


class Result(BaseModel):
    ok: bool


def test_valid_minimal_route():
    api = ApiDefinition()

    @api.get("/")
    def root() -> dict[str, str]: ...


def test_multiple_routes_same_path_different_methods():
    api = ApiDefinition()

    @api.get("/")
    def get_root() -> dict[str, str]: ...

    @api.post("/")
    def post_root() -> dict[str, str]: ...


def test_missing_return_annotation():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/")
        def root(): ...


def test_missing_parameter_annotation():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/")
        def root(x) -> dict[str, str]: ...


def test_varargs_rejected():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/")
        def root(*args) -> dict[str, str]: ...


def test_kwargs_rejected():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/")
        def root(**kwargs) -> dict[str, str]: ...


def test_invalid_annotation_type():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/")
        def root(x: any) -> dict[str, str]: ...


def test_path_parameter_inference():
    api = ApiDefinition()

    @api.get("/items/{item_id}")
    def get_item(item_id: int) -> dict[str, int]: ...


def test_path_parameter_mismatch():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/items/{item_id}")
        def get_item(x: int) -> dict[str, int]: ...


def test_body_requires_annotation():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.post("/items")
        def create_item(item: Item) -> Result: ...


def test_valid_body_annotation():
    api = ApiDefinition()

    @api.post("/items")
    def create_item(item: Annotated[Item, Body()]) -> Result: ...


def test_query_requires_annotation():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.get("/items")
        def get_items(q: str) -> dict[str, str]: ...


def test_valid_query_annotation():
    api = ApiDefinition()

    @api.get("/items")
    def get_items(q: Annotated[str, Query()]) -> dict[str, str]: ...


def test_multiple_body_parameters_rejected():
    api = ApiDefinition()
    with pytest.raises(ValueError):

        @api.post("/items")
        def create_item(
            a: Annotated[Item, Body()],
            b: Annotated[Item, Body()],
        ) -> Result: ...
