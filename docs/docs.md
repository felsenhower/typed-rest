<a id="rest_rpc"></a>

# rest\_rpc

Public API for REST-RPC.

Public classes have been re-exported for convenience:
- [`api_definition`](#rest_rpc.api_definition)
    - [ApiDefinition](#rest_rpc.api_definition.ApiDefinition)
- [`api_implementation`](#rest_rpc.api_implementation)
    - [ApiImplementation](#rest_rpc.api_implementation.ApiImplementation)
- [`api_client`](#rest_rpc.api_client)
    - [ApiClient](#rest_rpc.api_client.ApiClient)
    - [NetworkError](#rest_rpc.api_client.NetworkError)
    - [HttpError](#rest_rpc.api_client.HttpError)
    - [DecodeError](#rest_rpc.api_client.DecodeError)
    - [ValidationError](#rest_rpc.api_client.ValidationError)
    - [Request](#rest_rpc.api_client.Request)
- [`request_params`](#rest_rpc.request_params)
    - [Body](#rest_rpc.request_params.Body)
    - [Header](#rest_rpc.request_params.Header)
    - [Path](#rest_rpc.request_params.Path)
    - [Query](#rest_rpc.request_params.Query)

<a id="rest_rpc.api_definition"></a>

# rest\_rpc.api\_definition

API definition.

<a id="rest_rpc.api_definition.ApiDefinition"></a>

## ApiDefinition Objects

```python
class ApiDefinition()
```

Class for API definition. Put an instance of this class into a module that you import from both the back-end and
the front-end.

**Example**:

  
```python
api_def = ApiDefinition()


@api_def.get("/")
def read_root() -> dict[str, str]: ...
```

<a id="rest_rpc.api_definition.ApiDefinition.route"></a>

### route

```python
def route(method: str, path: str)
```

Decorator for route definitions.

**Example**:

  
```python
@api_def.route("GET", "/")
def read_root() -> dict[str, str]: ...

@api_def.route("GET", "/items/{item_id}")
def read_item(item_id: int) -> dict[str, Any]: ...
```
  

**Arguments**:

- `method` _str_ - The HTTP method of the route. Supports `DELETE`, `GET`, `PATCH`, `POST`, and `PUT`. Only one
  method is supported per route.
  
- `path` _str_ - The path of the route. May contain path parameters like `{param}`. Must start with a `/`.
  

**Raises**:

- `ValueError` - When trying to add a duplicated route, a route with an unsopported HTTP method, with an invalid
  path, with missing or invalid annotations, or using more than one parameter annotated with
  [`Body()`](#rest_rpc.request_params.Body).

<a id="rest_rpc.api_definition.ApiDefinition.delete"></a>

### delete

```python
def delete(path: str)
```

Shorthand for `@api_def.route(method="DELETE", path)`. See [`route`](#rest_rpc.api_definition.ApiDefinition.route).

**Example**:

  
```python
@api_def.delete("/foo")
def route() -> dict[str,Any]: ...
```

<a id="rest_rpc.api_definition.ApiDefinition.get"></a>

### get

```python
def get(path: str)
```

Shorthand for `@api_def.route(method="GET", path)`. See [`route`](#rest_rpc.api_definition.ApiDefinition.route).

**Example**:

  
```python
@api_def.get("/foo")
def route() -> dict[str,Any]: ...
```

<a id="rest_rpc.api_definition.ApiDefinition.patch"></a>

### patch

```python
def patch(path: str)
```

Shorthand for `@api_def.route(method="PATCH", path)`. See [`route`](#rest_rpc.api_definition.ApiDefinition.route).

**Example**:

  
```python
@api_def.patch("/foo")
def route() -> dict[str,Any]: ...
```

<a id="rest_rpc.api_definition.ApiDefinition.post"></a>

### post

```python
def post(path: str)
```

Shorthand for `@api_def.route(method="POST", path)`. See [`route`](#rest_rpc.api_definition.ApiDefinition.route).

**Example**:

  
```python
@api_def.post("/foo")
def route() -> dict[str,Any]: ...
```

<a id="rest_rpc.api_definition.ApiDefinition.put"></a>

### put

```python
def put(path: str)
```

Shorthand for `@api_def.route(method="PUT", path)`. See [`route`](#rest_rpc.api_definition.ApiDefinition.route).

**Example**:

  
```python
@api_def.put("/foo")
def route() -> dict[str,Any]: ...
```

<a id="rest_rpc.request_params"></a>

# rest\_rpc.request\_params

Helper classes for `Annotated` and API definition.

<a id="rest_rpc.request_params.RequestParam"></a>

## RequestParam Objects

```python
class RequestParam()
```

Base class for the [`Path`](#rest_rpc.request_params.Path), [`Query`](#rest_rpc.request_params.Query), [`Body`](#rest_rpc.request_params.Body) and [`Header`](#rest_rpc.request_params.Header) classes which mirror the corresponding Request Parameter
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

<a id="rest_rpc.request_params.Path"></a>

## Path Objects

```python
class Path(RequestParam)
```

REST-RPC analogue to FastAPI's `Path()`. Refer to [`RequestParam`](#rest_rpc.request_params.RequestParam) for more information.

Note: It's optional to annotate path parameters in REST-RPC.

**Example**:

  
```python
@api_def.get("/foo")
def foo(bar: Annotated[int, Path()]) -> dict[str, Any]: ...
```

<a id="rest_rpc.request_params.Query"></a>

## Query Objects

```python
class Query(RequestParam)
```

REST-RPC analogue to FastAPI's `Query()`. Refer to [`RequestParam`](#rest_rpc.request_params.RequestParam) for more information.

Note: Query parameters must be annotated in REST-RPC.

**Example**:

  
```python
@api_def.get("/foo")
def foo(bar: Annotated[int, Query()]) -> dict[str, Any]: ...
```

<a id="rest_rpc.request_params.Body"></a>

## Body Objects

```python
class Body(RequestParam)
```

REST-RPC analogue to FastAPI's `Body()`. Refer to [`RequestParam`](#rest_rpc.request_params.RequestParam) for more information.

Note: Body parameters must be annotated in REST-RPC. Body parameters are only allowed on `PATCH`, `POST`, and `PUT`.
Only one Body parameter is allowed per route. FastAPI's `Body(embed=True)` is not supported.

**Example**:

  
```python
@api_def.get("/foo")
def foo(bar: Annotated[SomeModel, Body()]) -> dict[str, Any]: ...
```

<a id="rest_rpc.request_params.Header"></a>

## Header Objects

```python
class Header(RequestParam)
```

REST-RPC analogue to FastAPI's `Header()`. Refer to [`RequestParam`](#rest_rpc.request_params.RequestParam) for more information.

Note: Header parameters must be annotated in REST-RPC.

**Example**:

  
```python
@api_def.get("/foo")
def foo(bar: Annotated[str, Header()]) -> dict[str, Any]: ...
```

<a id="rest_rpc.api_implementation"></a>

# rest\_rpc.api\_implementation

API implementation via FastAPI.

<a id="rest_rpc.api_implementation.ApiImplementation"></a>

## ApiImplementation Objects

```python
class ApiImplementation()
```

Class for API implementation via FastAPI.

**Arguments**:

- `api_def` _ApiDefinition_ - The [`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance to base the
  implementation on. The constructed `ApiImplementation` instance must add a handler to all routes that have
  been defined in `api_def`. Otherwise, it won't be possible to generate a FastAPI app.
  

**Example**:

  
```python
api_impl = ApiImplementation(api_def)

@api_impl.handler
def read_root():
    return {"Hello": "World"}
```

<a id="rest_rpc.api_implementation.ApiImplementation.handler"></a>

### handler

```python
def handler(func)
```

Decorator for route handlers. All routes defined in the
[`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance that was passed to the constructor must
be implemented through this decorator.

**Example**:

  
```python
@api_impl.handler
def read_root():
    return {"Hello": "World"}
```
  

**Raises**:

- `ValueError` - When trying to add a duplicate handler, a handler that doesn't exist in the api defintion,
  when adding a non-matching annotation or default value.

<a id="rest_rpc.api_implementation.ApiImplementation.make_fastapi"></a>

### make\_fastapi

```python
def make_fastapi()
```

Generate a FastAPI app.

**Raises**:

- `ValueError` - When not all route definitions have a corresponding handler.
  

**Returns**:

- `FastAPI` - a FastAPI instance.

<a id="rest_rpc.api_client"></a>

# rest\_rpc.api\_client

Api Client.

<a id="rest_rpc.api_client.CommunicationError"></a>

## CommunicationError Objects

```python
class CommunicationError(IOError)
```

Base class for errors that can happen in route accessors.

<a id="rest_rpc.api_client.NetworkError"></a>

## NetworkError Objects

```python
class NetworkError(CommunicationError)
```

An error that signifies that something network-related went wrong during a request.

<a id="rest_rpc.api_client.HttpError"></a>

## HttpError Objects

```python
class HttpError(CommunicationError)
```

An error that signifies that the server replied with a status code that indicates an error (>= 400).

<a id="rest_rpc.api_client.DecodeError"></a>

## DecodeError Objects

```python
class DecodeError(CommunicationError)
```

An error that signifies that the server did not send valid JSON data back.

<a id="rest_rpc.api_client.ValidationError"></a>

## ValidationError Objects

```python
class ValidationError(CommunicationError)
```

An error that signifies that the server did not send data back that can be deserialized into the desired type.

<a id="rest_rpc.api_client.Request"></a>

## Request Objects

```python
@dataclass
class Request()
```

A description of an HTTP request.

<a id="rest_rpc.api_client.ApiClient"></a>

## ApiClient Objects

```python
class ApiClient()
```

Class for API clients.

**Arguments**:

- `api_def` _ApiDefinition_ - The [`ApiDefinition`](#rest_rpc.api_definition.ApiDefinition) instance to generate the
  client for. For each route in the `ApiDefinition` instance, an accessor function with the same name will be
  generated.
- `engine` _str_ - The engine to use. Valid values are `"aiohttp"`, `"httpx"`, `"pyodide"`, `"pyscript"`,
  `"requests"`, `"urllib3"`, `"testclient"`, and `"custom"`. This determines which HTTP library is used
  internally.
- `app` _fastapi.FastAPI, optional_ - Required iff engine is `"testclient"`. FastAPI app to make requests on.
- `base_url` _str, optional_ - Required iff engine is one of `("aiohttp", "httpx", "pyodide", "pyscript",
  "requests", "urllib3")`. This is the base URL that is prepended to the route paths.
- `is_async` _bool | None, optional_ - When engine is `"custom"`, explicitly state if `transport` is as `async`
  function (`True`, `False`) or let the library decide (`None`). Defaults to `None`.
- `session` _aiohttp.ClientSession, optional_ - Required iff engine is `"aiohttp"`.
- `transport` _Callable[[Request], object], optional_ - Required iff engine is `"custom"`. Transport function to
  use for requests.

