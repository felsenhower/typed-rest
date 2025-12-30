#!/usr/bin/env python3

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never


@dataclass
class Route:
    method: str
    path: str
    name: str
    annotations: dict[str, type]


class ApiDefinition:
    def __init__(self):
        self.routes: dict[str, Route] = dict()

    def route(self, method: str, path: str):
        def route_decorator(func):
            name = func.__name__
            annotations = func.__annotations__
            assert name not in self.routes, f'Duplicate route "{name}"'
            self.routes[name] = Route(method, path, name, annotations)
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
        assert annotations == route_def.annotations, (
            f'Annotations for handler "{name}" don\'t match the corresponding route. Expected: {route_def.annotations}. Received: {annotations}.'
        )
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
        param_names = [name for name in route.annotations.keys() if name != "return"]
        for name, value in zip(param_names, args):
            kwargs.setdefault(name, value)
        for name, value in list(kwargs.items()):
            placeholder = "{" + name + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))
                kwargs.pop(name)
        url = self.base_url.rstrip("/") + path
        method = route.method
        response = requests.request(
            method=method,
            url=url,
            params=kwargs if kwargs else None,
        )
        response.raise_for_status()
        json = response.json()
        return json

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
