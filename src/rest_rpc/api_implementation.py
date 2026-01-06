"""API implementation via FastAPI."""

import inspect
from collections.abc import Callable
from typing import Annotated, assert_never, get_args, get_origin

from .api_definition import ApiDefinition
from .request_params import Body, Header, Path, Query, RequestParam


def ensure_has_request_param_annotations(
    annotations: dict[str, type], request_params: dict[str, RequestParam]
) -> dict[str, type]:
    assert "return" in annotations
    param_annotations = {
        pname: ptype for (pname, ptype) in annotations.items() if pname != "return"
    }
    assert param_annotations.keys() == request_params.keys(), (
        "Non-matching parameter names",
        param_annotations,
        request_params,
    )
    new_annotations = annotations.copy()

    def annotated_contains_request_param(annotated, request_param) -> bool:
        assert get_origin(annotated) is Annotated
        for arg in get_args(annotated):
            if isinstance(arg, RequestParam):
                assert arg.__class__ == request_param.__class__
                return True
        return False

    for (pname, annotation), request_param in zip(
        param_annotations.items(), request_params.values()
    ):
        if get_origin(annotation) is Annotated:
            if annotated_contains_request_param(annotation, request_param):
                new_annotations[pname] = annotation
            else:
                new_args = (*get_args(annotation), request_param)
                new_annotated = Annotated[*new_args]
                new_annotations[pname] = new_annotated
        else:
            new_annotated = Annotated[annotation, request_param]
            new_annotations[pname] = new_annotated
    return new_annotations


def convert_annotations_to_fastapi(
    annotations: dict[str, type], request_params: dict[str, RequestParam]
) -> dict[str, type]:
    import fastapi
    from fastapi.openapi.models import Example as FastapiExample

    annotations = ensure_has_request_param_annotations(annotations, request_params)
    assert "return" in annotations
    param_annotations = {
        pname: ptype for (pname, ptype) in annotations.items() if pname != "return"
    }
    assert param_annotations.keys() == request_params.keys(), (
        "Non-matching parameter names",
        param_annotations,
        request_params,
    )
    new_annotations = annotations.copy()
    for pname, annotation in param_annotations.items():
        assert get_origin(annotation) is Annotated
        new_args = []
        for arg in get_args(annotation):
            if isinstance(arg, RequestParam):
                args = dict(arg.bound_args.arguments)
                if "openapi_examples" in args:
                    args["openapi_examples"] = FastapiExample(
                        dict(args["openapi_examples"])
                    )
                if isinstance(arg, Path):
                    new_args.append(fastapi.Path(**args))
                elif isinstance(arg, Query):
                    new_args.append(fastapi.Query(**args))
                elif isinstance(arg, Header):
                    new_args.append(fastapi.Header(**args, convert_underscores=True))
                elif isinstance(arg, Body):
                    new_args.append(
                        fastapi.Body(**args, embed=False, media_type="application/json")
                    )
                else:
                    assert_never()
            else:
                new_args.append(arg)
        new_annotated = Annotated[*new_args]
        new_annotations[pname] = new_annotated
    return new_annotations


class ApiImplementation:
    """Class for API implementation via FastAPI.

    Args:
        api_def (ApiDefinition): The [`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance to base the
            implementation on. The constructed `ApiImplementation` instance must add a handler to all routes that have
            been defined in `api_def`. Otherwise, it won't be possible to generate a FastAPI app.

    Example:

    ```python
    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def read_root():
        return {"Hello": "World"}
    ```
    """

    def __init__(self, api_def: ApiDefinition):
        from fastapi import FastAPI  # noqa # pylint: disable=unused-import

        self.api_def = api_def
        self.handlers: dict[str, Callable] = dict()

    def handler(self, func):
        """Decorator for route handlers. All routes defined in the
            [`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance that was passed to the constructor must
            be implemented through this decorator.

        Example:

        ```python
        @api_impl.handler
        def read_root():
            return {"Hello": "World"}
        ```

        Raises:
            ValueError: When trying to add a duplicate handler, a handler that doesn't exist in the api defintion,
                when adding a non-matching annotation or default value.
        """
        name = func.__name__
        if name in self.handlers:
            raise ValueError(f'Unable to add duplicate handler "{name}".')
        if name not in self.api_def.routes:
            raise ValueError(
                f'Unable to add handler "{name}". Does not match any defined routes.'
            )
        route = self.api_def.routes[name]
        signature = inspect.signature(func)
        EMPTY = inspect.Signature.empty
        assert route.signature.return_annotation != EMPTY
        if signature.return_annotation != EMPTY:
            if signature.return_annotation != route.signature.return_annotation:
                raise ValueError(
                    f'Unable to add handler "{name}". Return annotation doesn\'t match corresponding route. Expected "{route.signature.return_annotation}", but got "{signature.return_annotation}".'
                )
        parameters = signature.parameters.values()
        expected_parameters = route.signature.parameters.values()
        if tuple(p.name for p in parameters) != tuple(
            p.name for p in expected_parameters
        ):
            raise ValueError(
                f'Unable to add handler "{name}". Parameter names don\'t match corresponding route. Expected {tuple(p.name for p in expected_parameters)}, but got {tuple(p.name for p in parameters)}.'
            )
        for param, exp_param in zip(parameters, expected_parameters):
            assert param.name == exp_param.name
            pname = param.name
            assert (exp_annotation := exp_param.annotation) != EMPTY
            if (actual_annotation := param.annotation) != EMPTY:
                if get_origin(actual_annotation) is Annotated:
                    raise ValueError(
                        f'Unable to add handler "{name}". Type annotation of parameter "{pname}" uses Annotated[] which is not supported.'
                    )
                if get_origin(exp_annotation) is Annotated:
                    exp_annotation = get_args(exp_annotation)[0]
                if actual_annotation != exp_annotation:
                    raise ValueError(
                        f'Unable to add handler "{name}". Type annotation of parameter "{pname}" doesn\'t match corresponding route. Expected "{exp_annotation}", but got "{actual_annotation}".'
                    )
            if param.default != EMPTY:
                if param.default != exp_param.default:
                    raise ValueError(
                        f'Unable to add handler "{name}". Default value of parameter "{pname}" doesn\'t match corresponding route. Expected "{exp_param.default}", but got "{param.default}".'
                    )
        annotations = convert_annotations_to_fastapi(
            route.raw_annotations, route.request_params
        )
        func.__annotations__ = annotations
        func.__defaults__ = route.raw_defaults
        self.handlers[name] = func
        return func

    def make_fastapi(self):
        """Generate a FastAPI app.

        Raises:
            ValueError: When not all route definitions have a corresponding handler.

        Returns:
            FastAPI: a FastAPI instance.
        """
        from fastapi import FastAPI

        if set(self.api_def.routes.keys()) != set(self.handlers.keys()):
            # `pydoc-markdown` fails without the backslashes (sigh).
            # fmt: off
            raise ValueError(
                f"Unable to generate FastAPI app. ApiImplementation is missing handlers for the following routes: { \
                    tuple( \
                        set(self.api_def.routes.keys()).difference(self.handlers.keys()) \
                    ) \
                }"
            )
            # fmt: on

        app = FastAPI()
        for name, route_def in self.api_def.routes.items():
            handler = self.handlers[name]
            route_def = self.api_def.routes[name]
            path = route_def.path
            method = route_def.method
            app.add_api_route(
                path,
                endpoint=handler,
                methods=[
                    method,
                ],
            )
        return app
