import pytest

from typed_rest import ApiDefinition, ApiImplementation


def test_add_simple_handlers():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, int]: ...

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, int | str | None]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    @api_impl.handler
    def route_with_arg(item_id):
        return {"item_id": item_id}

    @api_impl.handler
    def route_with_optional_arg(item_id, q):
        return {"item_id": item_id, "q": q}


def test_detect_non_matching_handler():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)
    with pytest.raises(ValueError):

        @api_impl.handler
        def simple_route_wrong_name():
            return {"Hello": "World"}


def test_add_duplicate_handler():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    with pytest.raises(ValueError):

        @api_impl.handler
        def simple_route():
            return {"Hello": "World"}


def test_add_simple_handlers_with_annotation():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, int]: ...

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, str | int | None]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route() -> dict[str, str]:
        return {"Hello": "World"}

    @api_impl.handler
    def route_with_arg(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @api_impl.handler
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, str | int | None]:
        return {"item_id": item_id, "q": q}


def test_detect_incorrect_annotation():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, int]: ...

    api_impl = ApiImplementation(api_def)
    with pytest.raises(ValueError):

        @api_impl.handler
        def simple_route() -> dict[str, int]:
            return {"Hello": "World"}

    with pytest.raises(ValueError):

        @api_impl.handler
        def route_with_arg(item_id: float) -> dict[str, float]:
            return {"item_id": item_id}


def test_detect_incorrect_default():
    api_def = ApiDefinition()

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, int | str | None]: ...

    api_impl = ApiImplementation(api_def)
    with pytest.raises(ValueError):

        @api_impl.handler
        def route_with_optional_arg(item_id, q="Foo"):
            return {"item_id": item_id, "q": q}


def test_detect_incorrect_parameter_name():
    api_def = ApiDefinition()

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, int]: ...

    api_impl = ApiImplementation(api_def)
    with pytest.raises(ValueError):

        @api_impl.handler
        def route_with_arg(foo):
            return {"item_id": foo}


def test_make_fastapi():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_optional_arg(
        item_id: int, q: str | None = None
    ) -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    @api_impl.handler
    def route_with_arg(item_id):
        return {"item_id": item_id}

    @api_impl.handler
    def route_with_optional_arg(item_id, q):
        return {"item_id": item_id, "q": q}

    _ = api_impl.make_fastapi()


def test_detect_missing_handlers():
    api_def = ApiDefinition()

    @api_def.get("/")
    def simple_route() -> dict[str, str]: ...

    @api_def.get("/items/{item_id}")
    def route_with_arg(item_id: int) -> dict[str, str]: ...

    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def simple_route():
        return {"Hello": "World"}

    with pytest.raises(ValueError):
        _ = api_impl.make_fastapi()
