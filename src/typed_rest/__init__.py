from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never
import pydantic
from pydantic import TypeAdapter
import inspect


@dataclass
class Route:
    method: str
    path: str
    name: str
    signature: inspect.Signature
    raw_annotations: dict[str, type]
    raw_defaults: tuple | None


def is_valid_pydantic_type(tp) -> bool:
    try:
        TypeAdapter(tp)
    except pydantic.PydanticSchemaGenerationError:
        return False
    return True


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
    TESTCLIENT = "testclient"


class CommunicationError(IOError):
    def __init__(self, route: Route, **kwargs):
        super().__init__(
            f'{self.__class__.__name__} while accessing route "{route.name}" ({kwargs}).'
        )


class NetworkError(CommunicationError):
    pass


class HttpError(CommunicationError):
    pass


class DecodeError(CommunicationError):
    pass


class ValidationError(CommunicationError):
    pass


class ApiClient:
    @staticmethod
    def _get_init_signature(engine: ApiClientEngine):
        dummy = None
        match engine:
            case ApiClientEngine.REQUESTS:

                def dummy(*, base_url: str) -> None: ...

            case ApiClientEngine.TESTCLIENT:
                from fastapi import FastAPI

                def dummy(*, app: FastAPI) -> None: ...

            case _:
                assert_never(engine)
        assert dummy is not None and callable(dummy)
        return inspect.signature(dummy)

    def _add_accessor(self, route: Route, transport):
        signature = route.signature

        def accessor(*args, **kwargs):
            try:
                bound = signature.bind(*args, **kwargs)
            except TypeError as e:
                raise ValueError(
                    f'Unable to use accessor for route "{route.name}": {e}'
                ) from e

            bound.apply_defaults()
            for pname, value in bound.arguments.items():
                param = signature.parameters[pname]
                try:
                    TypeAdapter(param.annotation).validate_python(value)
                except pydantic.ValidationError as e:
                    raise ValueError(
                        f'Illegal type for parameter "{pname}". '
                        f'Expected "{param.annotation}", got "{type(value)}".'
                    ) from e
            path = route.path
            params = dict(bound.arguments)
            for pname in list(params.keys()):
                placeholder = f"{{{pname}}}"
                if placeholder in path:
                    path = path.replace(placeholder, str(params.pop(pname)))
            json_data = transport(route.method, path, params or None)
            try:
                return TypeAdapter(signature.return_annotation).validate_python(
                    json_data
                )
            except pydantic.ValidationError as e:
                raise ValidationError(route, path, params) from e

        accessor.__signature__ = signature
        setattr(self, route.name, accessor)

    def _add_accessor_with_requests(self, route: Route):
        import requests

        def transport(method: str, path: str, params: dict | None):
            url = self.base_url.rstrip("/") + path
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                )
            except requests.RequestException as e:
                raise NetworkError(route, url=url, params=params) from e
            try:
                response.raise_for_status()
            except requests.RequestException as e:
                raise HttpError(route, url=url, params=params, response=response) from e
            try:
                return response.json()
            except requests.RequestException as e:
                raise DecodeError(
                    route, url=url, params=params, response=response
                ) from e

        self._add_accessor(route, transport)

    def _add_accessor_with_testclient(self, route: Route):
        import httpx
        import json

        def transport(method: str, path: str, params: dict | None):
            url = path
            try:
                response = self.testclient.request(
                    method=method,
                    url=url,
                    params=params,
                )
            except httpx.HTTPError as e:
                raise NetworkError(route, url=url, params=params) from e

            try:
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise HttpError(route, url=url, params=params, response=response) from e

            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route, url=url, params=params, response=response
                ) from e

        self._add_accessor(route, transport)

    def __init__(self, api_def: ApiDefinition, engine: str, **kwargs):
        if engine not in ApiClientEngine:
            raise ValueError(
                f'Unsupported engine "{engine}". Supported engines are '
                f"{ {str(e) for e in ApiClientEngine} }."
            )
        self.api_def = api_def
        self.engine = ApiClientEngine(engine)
        sig = self._get_init_signature(self.engine)
        try:
            bound = sig.bind(**kwargs)
        except TypeError as e:
            raise ValueError(
                f'Invalid parameters for ApiClient(engine="{engine}"): {e}'
            ) from e
        bound.apply_defaults()
        match self.engine:
            case ApiClientEngine.REQUESTS:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.TESTCLIENT:
                from fastapi.testclient import TestClient

                self.testclient = TestClient(bound.arguments["app"])
            case _:
                assert_never(self.engine)
        for route in self.api_def.routes.values():
            if hasattr(self, route.name):
                raise ValueError(
                    f'Unable to add accessor for route "{route.name}". '
                    "Name conflicts with ApiClient internals."
                )
            match self.engine:
                case ApiClientEngine.REQUESTS:
                    self._add_accessor_with_requests(route)
                case ApiClientEngine.TESTCLIENT:
                    self._add_accessor_with_testclient(route)
                case _:
                    assert_never(self.engine)
