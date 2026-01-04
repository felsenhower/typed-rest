import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional, Union, assert_never

import pydantic
from pydantic import AliasChoices, AliasPath, AnyUrl, TypeAdapter
from pydantic_core import PydanticUndefined
from typing_extensions import TypedDict, deprecated


class ParamExample(TypedDict, total=False):
    summary: Optional[str]
    description: Optional[str]
    value: Optional[Any]
    externalValue: Optional[AnyUrl]
    __pydantic_config__ = {"extra": "allow"}  # type: ignore[misc]


class RequestParam:
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


class Path(RequestParam): ...


class Query(RequestParam): ...


class Body(RequestParam): ...


class Header(RequestParam): ...


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
            parameters = signature.parameters.values()
            path_param_names = set(re.findall(r"\{(.+?)\}", path))
            if not path_param_names.issubset(p.name for p in parameters):
                raise ValueError(
                    f'Unable to add route "{name}". Parameters {path_param_names.difference(p.name for p in parameters)} are in path, but not in parameters.'
                )
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

    def delete(self, path: str):
        return self.route(method="DELETE", path=path)

    def get(self, path: str):
        return self.route(method="GET", path=path)

    def patch(self, path: str):
        return self.route(method="PATCH", path=path)

    def post(self, path: str):
        return self.route(method="POST", path=path)

    def put(self, path: str):
        return self.route(method="PUT", path=path)


class ApiImplementation:
    def __init__(self, api_def: ApiDefinition):
        from fastapi import FastAPI  # noqa # pylint: disable=unused-import

        self.api_def = api_def
        self.handlers: dict[str, Callable] = dict()

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
            app.add_api_route(
                path,
                endpoint=handler,
                methods=[
                    method,
                ],
            )
        return app


class ApiClientEngine(StrEnum):
    REQUESTS = "requests"
    TESTCLIENT = "testclient"
    CUSTOM = "custom"


class CommunicationError(IOError):
    def __init__(self, route: Route, **kwargs):
        super().__init__(
            f'{self.__class__.__name__} while accessing route "{route.name}" ({kwargs}).'
        )


class NetworkError(CommunicationError): ...


class HttpError(CommunicationError): ...


class DecodeError(CommunicationError): ...


class ValidationError(CommunicationError): ...


TransportFunction = Callable[[str, str, dict | None], object]


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

            case ApiClientEngine.CUSTOM:

                def dummy(*, transport: TransportFunction) -> None: ...

            case _:
                assert_never(engine)
        assert dummy is not None and callable(dummy)
        return inspect.signature(dummy)

    def _add_accessor(self, route: Route, transport: TransportFunction):
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
                raise ValidationError(route, path=path, params=params) from e

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
        import json

        import httpx

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

    def _add_accessor_with_custom(self, route: Route):
        self._add_accessor(route, self.transport)

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

                self.app = bound.arguments["app"]
                self.testclient = TestClient(self.app)

            case ApiClientEngine.CUSTOM:
                self.transport = bound.arguments["transport"]

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
                case ApiClientEngine.CUSTOM:
                    self._add_accessor_with_custom(route)
                case _:
                    assert_never(self.engine)
