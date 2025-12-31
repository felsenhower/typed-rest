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
    annotations: dict[str, type]
    defaults: tuple | None


def uses_kwargs(func):
    sig = inspect.signature(func)
    return any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()
    )


def uses_args(func):
    sig = inspect.signature(func)
    return any(
        param.kind == inspect.Parameter.VAR_POSITIONAL
        for param in sig.parameters.values()
    )


class ApiDefinition:
    def __init__(self):
        self.routes: dict[str, Route] = dict()

    def route(self, method: str, path: str):
        def route_decorator(func):
            name = func.__name__
            annotations = func.__annotations__
            defaults = func.__defaults__
            assert "return" in annotations, f"Unable to add route without return type!"
            parameter_names = func.__code__.co_varnames
            assert not uses_kwargs(func), (
                f"Unable to add route. kwargs is not supported!"
            )
            assert not uses_args(func), f"Unable to add route. args is not supported!"
            parameter_annotations = {
                name: ptype for (name, ptype) in annotations.items() if name != "return"
            }
            assert list(parameter_annotations.keys()) == list(parameter_names), (
                f"Missing type annotations for parameters {set(parameter_names).difference(parameter_annotations.keys())}."
            )
            assert name not in self.routes, f'Duplicate route "{name}"'
            self.routes[name] = Route(method, path, name, annotations, defaults)
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
        annotations = func.__annotations__
        assert name not in self.handlers, f'Duplicate handler "{name}"'
        assert name in self.api_def.routes, (
            f'Handler "{name}" does not match any defined routes.'
        )
        route_def = self.api_def.routes[name]
        if "return" in annotations:
            if annotations["return"] != route_def.annotations["return"]:
                raise ValueError(
                    f'Return type of handler "{name}" doesn\'t match the corresponding route. Expected "{route_def.annotations["return"]}", but received "{annotations["return"]}".'
                )
        parameter_annotations = {
            pname: ptype for (pname, ptype) in annotations.items() if pname != "return"
        }
        expected_parameter_annotations = {
            pname: ptype
            for (pname, ptype) in route_def.annotations.items()
            if pname != "return"
        }
        assert tuple(func.__code__.co_varnames) == tuple(
            expected_parameter_annotations.keys()
        ), (
            f'Parameters of handler "{name}" don\'t match corresponding route. Exepected {tuple(expected_parameter_annotations.keys())}, but got {tuple(func.__code__.co_varnames)}.'
        )
        for pname, ptype in expected_parameter_annotations.items():
            if pname in parameter_annotations:
                assert parameter_annotations[pname] == ptype, (
                    f'Annotations for handler "{name}" don\'t match the corresponding route. Expected: {route_def.annotations}. Received: {annotations}.'
                )
        defaults = func.__defaults__ or tuple()
        expected_defaults = route_def.defaults or tuple()
        assert len(defaults) <= len(expected_defaults), (
            f"The handler function has more default parameters than the corresponding route."
        )
        for pname, default, exp_default in reversed(
            list(
                zip(
                    reversed(expected_parameter_annotations.keys()),
                    reversed(defaults),
                    reversed(expected_defaults),
                )
            )
        ):
            assert default == exp_default, (
                f'Found incompatible default values for parameter "{pname}". Expected {exp_default}, but got {default}.'
            )
        func.__annotations__ = route_def.annotations
        func.__defaults__ = route_def.defaults
        self.handlers[name] = func
        return func

    def make_fastapi(self):
        from fastapi import FastAPI

        assert set(self.api_def.routes.keys()) == set(self.handlers.keys()), (
            "ApiImplementation is missing handlers for the following routes: {}".format(
                set(self.api_def.routes.keys()).difference(self.handlers.keys())
            )
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

        path = route.path
        assert "return" in route.annotations
        expected_parameters = {
            pname: ptype
            for (pname, ptype) in route.annotations.items()
            if pname != "return"
        }
        if len(args) + len(kwargs) > len(expected_parameters):
            raise ValueError(
                f"Received too many parameters. Expected {len(expected_parameters)}, but received {len(args) + len(kwargs)}"
            )
        for pname, value in zip(expected_parameters.keys(), args):
            kwargs.setdefault(pname, value)
        for (pname, ptype), value in zip(expected_parameters.items(), kwargs.values()):
            type_adapter = TypeAdapter(ptype)
            try:
                _ = type_adapter.validate_python(value)
            except ValidationError as e:
                raise ValueError(
                    f'Detected illegal type for parameter "{pname}". Expected {ptype}, but received {value.__class__}'
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
        return_type = route.annotations["return"]
        type_adapter = TypeAdapter(return_type)
        return type_adapter.validate_python(json)

    def __init__(self, api_def: ApiDefinition, engine: str, base_url: str):
        assert engine in ApiClientEngine, (
            f'Unsupported engine "{engine}". Supported engines are '
            f"{ {str(e) for e in ApiClientEngine} }."
        )
        self.api_def = api_def
        self.engine = ApiClientEngine(engine)
        self.base_url = base_url
        for name, route_def in self.api_def.routes.items():
            assert not hasattr(self, name), (
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
