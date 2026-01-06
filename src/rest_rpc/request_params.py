"""Helper classes for `Annotated` and API definition."""

import inspect
from typing import Any, Optional, Union

from pydantic import AliasChoices, AliasPath, AnyUrl
from pydantic_core import PydanticUndefined
from typing_extensions import TypedDict, deprecated


class ParamExample(TypedDict, total=False):
    summary: Optional[str]
    description: Optional[str]
    value: Optional[Any]
    externalValue: Optional[AnyUrl]
    __pydantic_config__ = {"extra": "allow"}  # type: ignore[misc]


class RequestParam:
    """Base class for the #Path, #Query, #Body and #Header classes which mirror the corresponding Request Parameter
    classes from FastAPI which are documented in the [FastAPI reference](https://fastapi.tiangolo.com/reference/parameters/).

    The REST-RPC versions intentionally support less parameters than the FastAPI versions in order to not support
    deprecated, superseded or non-applicable concepts.

    In the back-end, the classes are mapped to FastAPI's versions. Please refer to the FastAPI documentation to find out
    what the parameters do. The following parameters are supported:
    - `alias`
    - `alias_priority`
    - `validation_alias`
    - `serialization_alias`
    - `title`
    - `description`
    - `examples`
    - `openapi_examples`
    - `deprecated`
    - `include_in_schema`
    - `json_schema_extra`
    """

    def __init__(self, *args, **kwargs):
        def f(
            *,
            alias: Optional[str] = None,
            alias_priority: Union[int, None] = PydanticUndefined,
            validation_alias: Union[str, AliasPath, AliasChoices, None] = None,
            serialization_alias: Union[str, None] = None,
            title: Optional[str] = None,
            description: Optional[str] = None,
            discriminator: Union[str, None] = None,
            examples: Optional[list[Any]] = None,
            openapi_examples: Optional[dict[str, ParamExample]] = None,
            deprecated: Union[deprecated, str, bool, None] = None,
            include_in_schema: bool = True,
            json_schema_extra: Union[dict[str, Any], None] = None,
        ): ...

        signature = inspect.signature(f)
        self.bound_args = signature.bind(*args, **kwargs)


class Path(RequestParam):
    """REST-RPC analogue to FastAPI's `Path()`. Refer to #RequestParam for more information.

    Note: It's optional to annotate path parameters in REST-RPC.

    Example:

    ```python
    @api_def.get("/foo")
    def foo(bar: Annotated[int, Path()]) -> dict[str, Any]: ...
    ```
    """

    pass


class Query(RequestParam):
    """REST-RPC analogue to FastAPI's `Query()`. Refer to #RequestParam for more information.

    Note: Query parameters must be annotated in REST-RPC.

    Example:

    ```python
    @api_def.get("/foo")
    def foo(bar: Annotated[int, Query()]) -> dict[str, Any]: ...
    ```
    """

    pass


class Body(RequestParam):
    """REST-RPC analogue to FastAPI's `Body()`. Refer to #RequestParam for more information.

    Note: Body parameters must be annotated in REST-RPC. Body parameters are only allowed on `PATCH`, `POST`, and `PUT`.
    Only one Body parameter is allowed per route. FastAPI's `Body(embed=True)` is not supported.

    Example:

    ```python
    @api_def.get("/foo")
    def foo(bar: Annotated[SomeModel, Body()]) -> dict[str, Any]: ...
    ```
    """

    pass


class Header(RequestParam):
    """REST-RPC analogue to FastAPI's `Header()`. Refer to #RequestParam for more information.

    Note: Header parameters must be annotated in REST-RPC.

    Example:

    ```python
    @api_def.get("/foo")
    def foo(bar: Annotated[str, Header()]) -> dict[str, Any]: ...
    ```
    """

    pass
