import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Optional, Union, assert_never, get_args, get_origin

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
    request_params: dict[str, RequestParam]


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
        return self.route(method="DELETE", path=path)

    def get(self, path: str):
        return self.route(method="GET", path=path)

    def patch(self, path: str):
        return self.route(method="PATCH", path=path)

    def post(self, path: str):
        return self.route(method="POST", path=path)

    def put(self, path: str):
        return self.route(method="PUT", path=path)


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
    AIOHTTP = "aiohttp"
    HTTPX = "httpx"
    PYODIDE = "pyodide"
    PYSCRIPT = "pyscript"
    REQUESTS = "requests"
    URLLIB3 = "urllib3"
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


@dataclass
class Request:
    method: str
    path: str
    query_params: dict | None
    body: dict | None
    headers: dict | None


TransportFunction = Callable[[Request], object]


class ApiClient:
    @staticmethod
    def _get_init_signature(engine: ApiClientEngine):
        dummy = None
        match engine:
            case ApiClientEngine.AIOHTTP:
                import aiohttp

                def dummy(*, base_url: str, session: aiohttp.ClientSession) -> None: ...

            case ApiClientEngine.HTTPX:

                def dummy(*, base_url: str) -> None: ...

            case ApiClientEngine.PYSCRIPT:

                def dummy(
                    *,
                    base_url: str,
                ) -> None: ...

            case ApiClientEngine.PYODIDE:

                def dummy(*, base_url: str) -> None: ...

            case ApiClientEngine.REQUESTS:

                def dummy(*, base_url: str) -> None: ...

            case ApiClientEngine.URLLIB3:

                def dummy(*, base_url: str) -> None: ...

            case ApiClientEngine.TESTCLIENT:
                from fastapi import FastAPI

                def dummy(*, app: FastAPI) -> None: ...

            case ApiClientEngine.CUSTOM:

                def dummy(
                    *, transport: TransportFunction, is_async: bool | None = None
                ) -> None: ...

            case _:
                assert_never(engine)
        assert dummy is not None and callable(dummy)
        return inspect.signature(dummy)

    def _add_accessor(
        self, route: Route, transport: TransportFunction, is_async: bool | None = None
    ):
        def get_request(signature: inspect.Signature, *args, **kwargs) -> Request:
            def header_name(pname: str, header: Header) -> str:
                args = header.bound_args.arguments
                if args.get("serialization_alias") is not None:
                    return args["serialization_alias"]
                if args.get("alias") is not None:
                    return args["alias"]
                return pname.replace("_", "-")

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
            query_params: dict | None = None
            body: dict | None = None
            headers: dict | None = None
            for pname, req_param in route.request_params.items():
                value = bound.arguments[pname]
                if isinstance(req_param, Path):
                    path = path.replace(f"{{{pname}}}", str(value))
                elif isinstance(req_param, Query):
                    if query_params is None:
                        query_params = {}
                    query_params[pname] = value
                elif isinstance(req_param, Body):
                    type_adapter = TypeAdapter(value.__class__)
                    body = type_adapter.dump_python(value)
                elif isinstance(req_param, Header):
                    if headers is None:
                        headers = {}
                    header_key = header_name(pname, req_param)
                    headers[header_key] = value
            return Request(
                route.method,
                path,
                query_params,
                body,
                headers,
            )

        def validate_result(
            signature: inspect.Signature, request: Request, json_data: Any
        ) -> Any:
            try:
                return TypeAdapter(signature.return_annotation).validate_python(
                    json_data
                )
            except pydantic.ValidationError as e:
                raise ValidationError(
                    route,
                    path=request.path,
                    query_params=request.query_params,
                    body=request.body,
                    headers=request.headers,
                ) from e

        signature = route.signature

        if is_async is None:
            is_async = inspect.iscoroutinefunction(transport)

        if is_async:

            async def accessor(*args, **kwargs):
                request = get_request(signature, *args, **kwargs)
                json_data = await transport(request)
                return validate_result(signature, request, json_data)

        else:

            def accessor(*args, **kwargs):
                request = get_request(signature, *args, **kwargs)
                json_data = transport(request)
                return validate_result(signature, request, json_data)

        setattr(self, route.name, accessor)

    def _add_accessor_with_aiohttp(self, route: Route):
        import aiohttp

        async def transport(
            request: Request,
        ):
            try:
                url = self.base_url.rstrip("/") + request.path
                async with self.session.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    json=request.body,
                    headers=request.headers,
                    raise_for_status=True,
                ) as response:
                    try:
                        return await response.json()
                    except Exception as e:
                        raise DecodeError(
                            route,
                            url=url,
                            query_params=request.query_params,
                            body=request.body,
                            headers=request.headers,
                            response=response,
                        ) from e
            except aiohttp.ClientConnectionError as e:
                raise NetworkError(
                    route,
                    url=url,
                    query_params=request.query_params,
                    body=request.body,
                    headers=request.headers,
                ) from e
            except aiohttp.ClientResponseError as e:
                raise HttpError(
                    route,
                    url=url,
                    query_params=request.query_params,
                    body=request.body,
                    headers=request.headers,
                ) from e

        self._add_accessor(route, transport, is_async=True)

    def _add_accessor_with_httpx(self, route: Route):
        import json

        import httpx

        def transport(
            request: Request,
        ):
            method = request.method
            path = request.path
            query_params = request.query_params
            body = request.body
            headers = request.headers
            url = self.base_url.rstrip("/") + path
            try:
                response = httpx.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=body,
                    headers=headers,
                )
            except httpx.HTTPError as e:
                raise NetworkError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                ) from e

            try:
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise HttpError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=False)

    def _add_accessor_with_pyodide(self, route: Route):
        import json
        from urllib.parse import urlencode

        from pyodide.http import AbortError, HttpStatusError, pyfetch

        async def transport(
            request: Request,
        ):
            url = self.base_url.rstrip("/") + request.path
            if request.query_params is not None:
                url += "?" + urlencode(request.query_params)
            fetch_args = {"method": request.method}
            if request.body is not None:
                fetch_args["body"] = request.body
            if request.headers is not None:
                fetch_args["headers"] = request.headers
            try:
                response = await pyfetch(
                    url,
                    **fetch_args,
                )
            except AbortError as e:
                raise NetworkError(
                    route,
                    url=url,
                    fetch_args=fetch_args,
                ) from e
            try:
                response.raise_for_status()
            except HttpStatusError as e:
                raise HttpError(
                    route,
                    url=url,
                    fetch_args=fetch_args,
                    response=response,
                ) from e
            try:
                return await response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route,
                    fetch_args=fetch_args,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=True)

    def _add_accessor_with_pyscript(self, route: Route):
        import json
        from urllib.parse import urlencode

        import pyscript

        async def transport(
            request: Request,
        ):
            url = self.base_url.rstrip("/") + request.path
            if request.query_params is not None:
                url += "?" + urlencode(request.query_params)
            fetch_args = {"url": url, "method": request.method}
            if request.body is not None:
                fetch_args["body"] = request.body
            if request.headers is not None:
                fetch_args["headers"] = request.headers
            try:
                response = await pyscript.fetch(**fetch_args)
            except Exception as e:
                raise NetworkError(
                    route,
                    fetch_args=fetch_args,
                ) from e
            if not response.ok:
                raise HttpError(
                    route,
                    fetch_args=fetch_args,
                    response=response,
                )
            try:
                return await response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route,
                    fetch_args=fetch_args,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=True)

    def _add_accessor_with_requests(self, route: Route):
        import requests

        def transport(
            request: Request,
        ):
            method = request.method
            path = request.path
            query_params = request.query_params
            body = request.body
            headers = request.headers
            url = self.base_url.rstrip("/") + path
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=body,
                    headers=headers,
                )
            except requests.RequestException as e:
                raise NetworkError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                ) from e

            try:
                response.raise_for_status()
            except requests.RequestException as e:
                raise HttpError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

            try:
                return response.json()
            except requests.RequestException as e:
                raise DecodeError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=False)

    def _add_accessor_with_urllib3(self, route: Route):
        import json
        from urllib.parse import urlencode

        import urllib3

        def transport(
            request: Request,
        ):
            method = request.method
            path = request.path
            body = request.body
            headers = request.headers
            url = self.base_url.rstrip("/") + path
            if request.query_params is not None:
                url += "?" + urlencode(request.query_params)
            try:
                response = urllib3.request(
                    method=method,
                    url=url,
                    json=body,
                    headers=headers,
                )
            except urllib3.exceptions.HTTPError as e:
                raise NetworkError(
                    route,
                    url=url,
                    body=body,
                    headers=headers,
                ) from e

            if response.status >= 400:
                raise HttpError(
                    route,
                    url=url,
                    body=body,
                    headers=headers,
                    response=response,
                )

            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route,
                    url=url,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=False)

    def _add_accessor_with_testclient(self, route: Route):
        import json

        import httpx

        def transport(
            request: Request,
        ):
            method = request.method
            path = request.path
            query_params = request.query_params
            body = request.body
            headers = request.headers
            url = path
            try:
                response = self.testclient.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=body,
                    headers=headers,
                )
            except httpx.HTTPError as e:
                raise NetworkError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                ) from e

            try:
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise HttpError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                    response_text=response.text,
                ) from e

            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise DecodeError(
                    route,
                    url=url,
                    query_params=query_params,
                    body=body,
                    headers=headers,
                    response=response,
                ) from e

        self._add_accessor(route, transport, is_async=False)

    def _add_accessor_with_custom(self, route: Route):
        self._add_accessor(route, self.transport, self.is_async)

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
            case ApiClientEngine.AIOHTTP:
                self.base_url = bound.arguments["base_url"]
                self.session = bound.arguments["session"]

            case ApiClientEngine.HTTPX:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.PYODIDE:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.PYSCRIPT:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.REQUESTS:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.URLLIB3:
                self.base_url = bound.arguments["base_url"]

            case ApiClientEngine.TESTCLIENT:
                from fastapi.testclient import TestClient

                self.app = bound.arguments["app"]
                self.testclient = TestClient(self.app)

            case ApiClientEngine.CUSTOM:
                self.transport = bound.arguments["transport"]
                self.is_async = bound.arguments["is_async"]

            case _:
                assert_never(self.engine)
        for route in self.api_def.routes.values():
            if hasattr(self, route.name):
                raise ValueError(
                    f'Unable to add accessor for route "{route.name}". '
                    "Name conflicts with ApiClient internals."
                )
            match self.engine:
                case ApiClientEngine.AIOHTTP:
                    self._add_accessor_with_aiohttp(route)
                case ApiClientEngine.HTTPX:
                    self._add_accessor_with_httpx(route)
                case ApiClientEngine.PYODIDE:
                    self._add_accessor_with_pyodide(route)
                case ApiClientEngine.PYSCRIPT:
                    self._add_accessor_with_pyscript(route)
                case ApiClientEngine.REQUESTS:
                    self._add_accessor_with_requests(route)
                case ApiClientEngine.URLLIB3:
                    self._add_accessor_with_urllib3(route)
                case ApiClientEngine.TESTCLIENT:
                    self._add_accessor_with_testclient(route)
                case ApiClientEngine.CUSTOM:
                    self._add_accessor_with_custom(route)
                case _:
                    assert_never(self.engine)
