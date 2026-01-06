"""API definition."""

import inspect
import re
from typing import Annotated, get_args, get_origin

import pydantic
from pydantic import TypeAdapter

from .request_params import Body, Path, RequestParam
from .route import Route


def is_valid_pydantic_type(tp) -> bool:
    try:
        TypeAdapter(tp)
    except pydantic.PydanticSchemaGenerationError:
        return False
    return True


def get_request_param(tp) -> RequestParam:
    if get_origin(tp) is not Annotated:
        return Path()
    request_param_annotations = {
        annotation
        for annotation in get_args(tp)
        if isinstance(annotation, RequestParam)
    }
    num_annotations = len(request_param_annotations)
    if num_annotations == 0:
        return Path()
    if num_annotations > 1:
        raise ValueError(
            f"Can only add one RequestParam annotation. Gave { {a.__class__.__name__ for a in request_param_annotations} }."
        )
    return next(iter(request_param_annotations))


def get_request_params(
    path: str,
    parameters: list[inspect.Parameter],
) -> dict[str, RequestParam]:
    parameter_names_from_path = set(re.findall(r"\{(.+?)\}", path))
    if not parameter_names_from_path.issubset(p.name for p in parameters):
        raise ValueError(
            f"Parameters {parameter_names_from_path.difference(p.name for p in parameters)} are in path, but not in parameters."
        )
    request_params = {p.name: get_request_param(p.annotation) for p in parameters}
    if not parameter_names_from_path.isdisjoint(
        pname for (pname, a) in request_params.items() if not isinstance(a, Path)
    ):
        raise ValueError(
            f"Parameters {parameter_names_from_path.intersection(pname for (pname, a) in request_params.items() if not isinstance(a, Path))} have incompatible annotations."
        )

    if not {
        pname for (pname, a) in request_params.items() if isinstance(a, Path)
    }.issubset(parameter_names_from_path):
        raise ValueError(
            f"Parameters {set(pname for (pname, a) in request_params.items() if isinstance(a, Path)).difference(parameter_names_from_path)} are in parameters, but not in path."
        )
    if sum(1 for a in request_params.values() if isinstance(a, Body)) > 1:
        raise ValueError(
            f"More than one Body parameter was given: {set(pname for (pname, a) in request_params.items() if isinstance(a, Body))}"
        )
    assert parameter_names_from_path == {
        pname for (pname, a) in request_params.items() if isinstance(a, Path)
    }, (
        parameter_names_from_path,
        {pname for (pname, a) in request_params.items() if isinstance(a, Path)},
    )
    return request_params


class ApiDefinition:
    """Class for API definition. Put an instance of this class into a module that you import from both the back-end and
    the front-end.

    Example:

    ```python
    api_def = ApiDefinition()


    @api_def.get("/")
    def read_root() -> dict[str, str]: ...
    ```
    """

    def __init__(self):
        self.routes: dict[str, Route] = dict()

    def route(self, method: str, path: str):
        """Decorator for route definitions.

        Example:

        ```python
        @api_def.route("GET", "/")
        def read_root() -> dict[str, str]: ...

        @api_def.route("GET", "/items/{item_id}")
        def read_item(item_id: int) -> dict[str, Any]: ...
        ```

        Args:
            method (str): The HTTP method of the route. Supports `DELETE`, `GET`, `PATCH`, `POST`, and `PUT`. Only one
                method is supported per route.

            path (str): The path of the route. May contain path parameters like `{param}`. Must start with a `/`.

        Raises:
            ValueError: When trying to add a duplicated route, a route with an unsopported HTTP method, with an invalid
                path, with missing or invalid annotations, or using more than one parameter annotated with
                [`Body()`](#rest_rpc.request_params.Body).
        """

        def route_decorator(func):
            EMPTY = inspect.Signature.empty
            name = func.__name__
            if name in self.routes:
                raise ValueError(f'Unable to add duplicate route "{name}".')
            SUPPORTED_METHODS = {"DELETE", "GET", "PATCH", "POST", "PUT"}
            if method not in SUPPORTED_METHODS:
                raise ValueError(
                    f'Unable to add route "{name}". Method "{method}" is not supported. Supported methods are {SUPPORTED_METHODS}.'
                )
            if not path.startswith("/"):
                raise ValueError(
                    f'Unable to add route "{name}". Path "{path}" does not start with "/".'
                )
            signature = inspect.signature(func)
            parameters = list(signature.parameters.values())
            if signature.return_annotation == EMPTY:
                raise ValueError(
                    f'Unable to add route "{name}" without a return annotation.'
                )
            if not is_valid_pydantic_type(signature.return_annotation):
                raise ValueError(
                    f'Unable to add route "{name}". "{signature.return_annotation}" cannot be converted to a Pydantic schema.'
                )
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters):
                raise ValueError(
                    f'Unable to add route "{name}". **kwargs is not supported.'
                )
            if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in parameters):
                raise ValueError(
                    f'Unable to add route "{name}". *args is not supported.'
                )
            if sum(1 for p in parameters if p.annotation == EMPTY) > 0:
                raise ValueError(
                    f'Unable to add route "{name}". Missing type annotations for parameters {tuple(p.name for p in parameters if p.annotation == EMPTY)}'
                )

            if (
                sum(1 for p in parameters if not is_valid_pydantic_type(p.annotation))
                > 0
            ):
                raise ValueError(
                    f'Unable to add route "{name}". Annotations of parameters {tuple(p.name for p in parameters if not is_valid_pydantic_type(p.annotation))} cannot be converted to pydantic schemas.'
                )
            request_params = get_request_params(path, parameters)

            METHODS_SUPPORTING_BODY = {"PATCH", "POST", "PUT"}
            if method not in METHODS_SUPPORTING_BODY:
                if (
                    sum(1 for (_, a) in request_params.items() if isinstance(a, Body))
                    > 0
                ):
                    raise ValueError(
                        f'Unable to add route "{name}". Request bodies are only support for methods {METHODS_SUPPORTING_BODY}.'
                    )

            raw_annotations = func.__annotations__
            raw_defaults = func.__defaults__
            self.routes[name] = Route(
                method,
                path,
                name,
                signature,
                raw_annotations,
                raw_defaults,
                request_params,
            )
            return func

        return route_decorator

    def delete(self, path: str):
        """Shorthand for `@api_def.route(method="DELETE", path)`. See #route.

        Example:

        ```python
        @api_def.delete("/foo")
        def route() -> dict[str,Any]: ...
        ```
        """
        return self.route(method="DELETE", path=path)

    def get(self, path: str):
        """Shorthand for `@api_def.route(method="GET", path)`. See #route.

        Example:

        ```python
        @api_def.get("/foo")
        def route() -> dict[str,Any]: ...
        ```
        """
        return self.route(method="GET", path=path)

    def patch(self, path: str):
        """Shorthand for `@api_def.route(method="PATCH", path)`. See #route.

        Example:

        ```python
        @api_def.patch("/foo")
        def route() -> dict[str,Any]: ...
        ```
        """
        return self.route(method="PATCH", path=path)

    def post(self, path: str):
        """Shorthand for `@api_def.route(method="POST", path)`. See #route.

        Example:

        ```python
        @api_def.post("/foo")
        def route() -> dict[str,Any]: ...
        ```
        """
        return self.route(method="POST", path=path)

    def put(self, path: str):
        """Shorthand for `@api_def.route(method="PUT", path)`. See #route.

        Example:

        ```python
        @api_def.put("/foo")
        def route() -> dict[str,Any]: ...
        ```
        """
        return self.route(method="PUT", path=path)
