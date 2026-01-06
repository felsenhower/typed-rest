from typing import Annotated

import pytest
from rest_rpc import ApiDefinition, ApiImplementation, Query


def make_api():
    api = ApiDefinition()

    @api.get("/items/{item_id}")
    def get_item(
        item_id: int,
        q: Annotated[str | None, Query()] = None,
    ) -> dict[str, int | str | None]: ...

    return api


def test_valid_handler_registration():
    api = make_api()
    impl = ApiImplementation(api)

    @impl.handler
    def get_item(item_id, q):
        return {"item_id": item_id, "q": q}


def test_missing_handler():
    api = make_api()
    impl = ApiImplementation(api)
    with pytest.raises(ValueError):
        impl.make_fastapi()


def test_duplicate_handler():
    api = make_api()
    impl = ApiImplementation(api)

    @impl.handler
    def get_item(item_id, q):
        return {}

    with pytest.raises(ValueError):

        @impl.handler
        def get_item(item_id, q):
            return {}


def test_handler_wrong_name():
    api = make_api()
    impl = ApiImplementation(api)
    with pytest.raises(ValueError):

        @impl.handler
        def wrong(item_id, q):
            return {}


def test_handler_wrong_signature():
    api = make_api()
    impl = ApiImplementation(api)
    with pytest.raises(ValueError):

        @impl.handler
        def get_item(item_id):
            return {}


def test_handler_wrong_annotation():
    api = make_api()
    impl = ApiImplementation(api)
    with pytest.raises(ValueError):

        @impl.handler
        def get_item(item_id: float, q: str):
            return {}


def test_handler_wrong_default():
    api = make_api()
    impl = ApiImplementation(api)
    with pytest.raises(ValueError):

        @impl.handler
        def get_item(item_id, q="Incorrect"):
            return {}
