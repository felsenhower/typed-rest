"""Api Client."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, assert_never

import pydantic
from pydantic import TypeAdapter

from .api_definition import ApiDefinition
from .request_params import Body, Header, Path, Query
from .route import Route


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
    """Base class for errors that can happen in route accessors."""

    def __init__(self, route: Route, **kwargs):
        super().__init__(
            f'{self.__class__.__name__} while accessing route "{route.name}" ({kwargs}).'
        )


class NetworkError(CommunicationError):
    """An error that signifies that something network-related went wrong during a request."""

    pass


class HttpError(CommunicationError):
    """An error that signifies that the server replied with a status code that indicates an error (>= 400)."""

    pass


class DecodeError(CommunicationError):
    """An error that signifies that the server did not send valid JSON data back."""

    pass


class ValidationError(CommunicationError):
    """An error that signifies that the server did not send data back that can be deserialized into the desired type."""

    pass


@dataclass
class Request:
    """A description of an HTTP request."""

    method: str
    path: str
    query_params: dict | None
    body: dict | None
    headers: dict | None


class ApiClient:
    """Class for API clients.

    Args:
        api_def (ApiDefinition): The [`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance to generate the
            client for. For each route in the `ApiDefinition` instance, an accessor function with the same name will be
            generated.
        engine (str): The engine to use. Valid values are `"aiohttp"`, `"httpx"`, `"pyodide"`, `"pyscript"`,
            `"requests"`, `"urllib3"`, `"testclient"`, and `"custom"`. This determines which HTTP library is used
            internally.
        app (fastapi.FastAPI, optional): Required iff engine is `"testclient"`. FastAPI app to make requests on.
        base_url (str, optional): Required iff engine is one of `("aiohttp", "httpx", "pyodide", "pyscript",
            "requests", "urllib3")`. This is the base URL that is prepended to the route paths.
        is_async (bool | None, optional): When engine is `"custom"`, explicitly state if `transport` is as `async`
            function (`True`, `False`) or let the library decide (`None`). Defaults to `None`.
        session (aiohttp.ClientSession, optional): Required iff engine is `"aiohttp"`.
        transport (Callable[[Request], object], optional): Required iff engine is `"custom"`. Transport function to
            use for requests.
    """

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
                    *,
                    transport: Callable[[Request], object],
                    is_async: bool | None = None,
                ) -> None: ...

            case _:
                assert_never(engine)
        assert dummy is not None and callable(dummy)
        return inspect.signature(dummy)

    def _add_accessor(
        self,
        route: Route,
        transport: Callable[[Request], object],
        is_async: bool | None = None,
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
