#!/usr/bin/env python3

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never
from pydantic import TypeAdapter, ValidationError
import inspect


@dataclass
class Route:
    method: str
    path: str
    name: str
    signature: inspect.Signature
    raw_annotations: dict[str, type]
    raw_defaults: tuple | None


class ApiDefinition:
    def __init__(self):
        self.routes: dict[str, Route] = dict()

    def route(self, method: str, path: str):
        def route_decorator(func):
            EMPTY = inspect.Signature.empty
            name = func.__name__
            if name in self.routes:
                raise ValueError(f'Unable to add duplicate route "{name}".')
            signature = inspect.signature(func)
            parameters = signature.parameters.values()
            if signature.return_annotation == EMPTY:
                raise ValueError(
                    f'Unable to add route "{name}" without a return annotation.'
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
            raw_annotations = func.__annotations__
            raw_defaults = func.__defaults__
            self.routes[name] = Route(
                method, path, name, signature, raw_annotations, raw_defaults
            )
            return func

        return route_decorator

    def get(self, path: str):
        return self.route(method="GET", path=path)


class ApiImplementation:
    def __init__(self, api_def: ApiDefinition):
        from fastapi import FastAPI  # noqa # pylint: disable=unused-import

        self.api_def = api_def
        self.handlers = dict()

    def handler(self, func):
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
            assert exp_param.annotation != EMPTY
            if param.annotation != EMPTY:
                if param.annotation != exp_param.annotation:
                    raise ValueError(
                        f'Unable to add handler "{name}". Type annotation of parameter "{pname}" doesn\'t match corresponding route. Expected "{exp_param.annotation}", but got "{param.annotation}".'
                    )
            if param.default != EMPTY:
                if param.default != exp_param.default:
                    raise ValueError(
                        f'Unable to add handler "{name}". Default value of parameter "{pname}" doesn\'t match corresponding route. Expected "{exp_param.default}", but got "{param.default}".'
                    )
        func.__annotations__ = route.raw_annotations
        func.__defaults__ = route.raw_defaults
        self.handlers[name] = func
        return func

    def make_fastapi(self):
        from fastapi import FastAPI

        if set(self.api_def.routes.keys()) != set(self.handlers.keys()):
            raise ValueError(
                f"Unable to generate FastAPI app. ApiImplementation is missing handlers for the following routes: {
                    tuple(
                        set(self.api_def.routes.keys()).difference(self.handlers.keys())
                    )
                }"
            )

        app = FastAPI()
        for name, route_def in self.api_def.routes.items():
            handler = self.handlers[name]
            route_def = self.api_def.routes[name]
            path = route_def.path
            method = route_def.method
            app.add_api_route(path, endpoint=handler, methods=(method,))
        return app


class ApiClientEngine(StrEnum):
    REQUESTS = "requests"


class ApiClient:
    def make_request_with_requests(self, route: Route, *args, **kwargs):
        import requests

        name = route.name
        path = route.path
        EMPTY = inspect.Signature.empty
        assert route.raw_annotations != EMPTY
        expected_parameters = route.signature.parameters.values()
        if len(args) + len(kwargs) > len(expected_parameters):
            raise ValueError(
                f'Unable to use accessor for route "{name}". Received too many parameters. Expected {len(expected_parameters)}, but received {len(args) + len(kwargs)}'
            )
        for pname, value in zip((p.name for p in expected_parameters), args):
            kwargs.setdefault(pname, value)

        for (pname, ptype), value in zip(
            ((p.name, p.annotation) for p in expected_parameters), kwargs.values()
        ):
            type_adapter = TypeAdapter(ptype)
            try:
                _ = type_adapter.validate_python(value)
            except ValidationError as e:
                raise ValueError(
                    f'Unable to use accessor for route "{name}". Detected illegal type for parameter "{pname}". Expected "{ptype}", but received "{value.__class__}"'
                ) from e
        for pname, value in list(kwargs.items()):
            placeholder = "{" + pname + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))
                kwargs.pop(pname)
        url = self.base_url.rstrip("/") + path
        method = route.method
        response = requests.request(
            method=method,
            url=url,
            params=kwargs if kwargs else None,
        )
        response.raise_for_status()
        json = response.json()
        return_type = route.signature.return_annotation
        type_adapter = TypeAdapter(return_type)
        return type_adapter.validate_python(json)

    def __init__(self, api_def: ApiDefinition, engine: str, base_url: str):
        if engine not in ApiClientEngine:
            raise ValueError(
                f'Unsupported engine "{engine}". Supported engines are '
                f"{ {str(e) for e in ApiClientEngine} }."
            )
        self.api_def = api_def
        self.engine = ApiClientEngine(engine)
        self.base_url = base_url
        for name, route_def in self.api_def.routes.items():
            if hasattr(self, name):
                raise ValueError(
                    f'Unable to add accessor for route "{name}". '
                    "This should only happen when a route name is already used internally."
                )
            match self.engine:
                case ApiClientEngine.REQUESTS:

                    def make_accessor(route):
                        def accessor(*args, **kwargs):
                            return self.make_request_with_requests(
                                route, *args, **kwargs
                            )

                        return accessor

                    setattr(self, name, make_accessor(route_def))
                case _:
                    assert_never(f'Encountered unexpected engine "{engine}".')
