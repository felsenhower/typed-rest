# REST-RPC

REST-RPC is a Python library that makes writing type-checked REST APIs easy (by allowing you to define your API once and use it on both the server and the client).

It automatically creates convenient front-end bindings to your API for you, so from the front-end developer's perspective it's indistinguishable from an RPC library, hence the name.

REST-RPC's type-checking is based on Pydantic. For the back-end, it used FastAPI. For the front-end, it supports `requests`, `urllib3`, `httpx`, and `aiohttp` (or provide your own transport layer). If you want to use REST-RPC in the webbrowser, you can: It supports `pyodide`'s `pyfetch` and `pyscript`'s `fetch`![^1]

[^1]: This means that the only "hard" dependency is `pydantic`. Of course, you'll need FastAPI in the back-end and one of the mentioned HTTP libraries for the front-end.

REST-RPC is for you, if you:
- …like FastAPI and Pydantic.
- …just want to write simple type-checked REST APIs without frills.
- …don't want to repeat yourself when writing the front-end code.

## Usage

> [!TIP]
> Go right to the [documentation](docs/docs.md)

### Installation

To install `rest-rpc` for back-end use, run:

```shell
$ uv add 'git+https://github.com/felsenhower/rest-rpc' --extra fastapi
```

To install `rest-rpc` for front-end use, run:

```shell
$ uv add 'git+https://github.com/felsenhower/rest-rpc' --extra requests
```

If you want to use `urllib3`, `httpx`, or `aiohttp` instead of `requests`, just replace the corresponding extra.

### Simple Example

We assume that you're familiar with REST APIs and FastAPI.

See [`examples/simple/`](examples/simple/) for a simple example of an API definition, back-end, and front-end.

The core idea behind REST-RPC is that an API definition is shared between back-end and front-end, so we begin by defining an API without any implementation details:

```python
# my_api.py

from typing import Annotated, Any

from rest_rpc import ApiDefinition, Query

api_def = ApiDefinition()


@api_def.get("/")
def read_root() -> dict[str, str]: ...


@api_def.get("/items/{item_id}")
def read_item(
    item_id: int, q: Annotated[str | None, Query()] = None
) -> dict[str, Any]: ...
```

You've probably seen something similar on the [FastAPI homepage](https://fastapi.tiangolo.com/#create-it).

Let's continue with the actual back-end definition:

```python
# main.py

from rest_rpc import ApiImplementation

from my_api import api_def

api_impl = ApiImplementation(api_def)


@api_impl.handler
def read_root():
    return {"Hello": "World"}


@api_impl.handler
def read_item(item_id, q):
    return {"item_id": item_id, "q": q}


app = api_impl.make_fastapi()
```

And finally, the front-end:

```python
# client_sync.py

from rest_rpc import ApiClient

from my_api import api_def


def main() -> None:
    api_client = ApiClient(api_def, engine="requests", base_url="http://127.0.0.1:8000")
    
    result = api_client.read_root()
    print(result)
    assert result == {"Hello": "World"}
    
    result2 = api_client.read_item(item_id=42, q="Foo")
    print(result2)
    assert result2 == {"item_id": 42, "q": "Foo"}


if __name__ == "__main__":
    main()
```

You can try it out by running `uv run fastapi dev` in one terminal and running `uv run client_sync.py` in another.

For the sake of the comparison, here is what a functionally identical back-end and front-end would look like without REST-RPC:

```python
# main.py

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

```python
# client.py

import requests


def main() -> None:
    response = requests.get("http://127.0.0.1:8000/")
    response.raise_for_status()
    result = response.json()
    print(result)
    assert result == {"Hello": "World"}
    
    response2 = requests.get("http://127.0.0.1:8000/items/42", params={"q": "Foo"})
    response2.raise_for_status()
    result2 = response2.json()
    print(result2)
    assert result2 == {"item_id": 42, "q": "Foo"}


if __name__ == "__main__":
    main()
```

Let's go through it from top to bottom:

The API definition in `my_api.py` looks very similar to the way we write FastAPI apps. Some notable differences are:
- All the route definitions are just stubs (they're missing their bodies). This is intentional: Since `my_api.py` is imported by both the back-end and the front-end, we want to hide the implementation details of the server from the client. The client only needs to know which routes exist, and not how they are implemented. The implementation can be found inside `main.py` instead.
- Instead of the `@app.get()` decorator we use the `api_def.get()` decorator which works mostly the same.
- There are a few annotations more: The return values of the routes are annotated, and we use `Annotated[]` together with `Query()` to annotate that `q` is a query parameter. These annotations are required in REST-RPC. In FastAPI, you _can_ use them, but don't have to.

The API implementation is contained in `main.py`. Again, this looks similar to the pure FastAPI version. Here, the annotations and default values are _not_ required. We left them out to keep the code brief and to show that it's supported. Once your API design is stable, you'll probably want to add them.

Finally, `client_sync.py` contains a simple front-end. The actual API calls are very neatly abstracted away, i.e. since we stated in `my_api.py` that a function `read_item(item_id: int, q: str | None = None) -> dict[str, Any]` exists, we can just call `api_client.read_item(item_id=42, q="Foo")` in the front-end. On the other hand, the front-end written with pure `requests` looks way less pleasing to the eye. One could of course argue that the example is intentionally ugly and that it would be obvious to write an abstraction layer that builds the URL from a constant `base_url`, that checks return codes and that actually validates the API's reponses. But REST-RPC _is_ that abstraction layer!

As a final note about this example: Here, the API client uses `requests` internally. If you want to use `httpx` or `urllib3` instead, just pass a different `engine` to the `ApiClient` constructor. From the user perspective it doesn't matter. The function calls always behave the same way. So use the engine you like working with. If you need help deciding, maybe the [performance comparison](#performance-comparison) will help.

### Async example

In the simple example above, the requests are performed synchronously. If you're working with an `async` environment, you'll want to take a look at `client_async.py` inside [`examples/simple/`](examples/simple/):

```python
# client_async.py

import asyncio

import aiohttp
from rest_rpc import ApiClient

from my_api import api_def


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        api_client = ApiClient(
            api_def, engine="aiohttp", session=session, base_url="http://127.0.0.1:8000"
        )
        
        result = await api_client.read_root()
        print(result)
        assert result == {"Hello": "World"}
        
        result2 = await api_client.read_item(item_id=42, q="Foo")
        print(result2)
        assert result2 == {"item_id": 42, "q": "Foo"}


if __name__ == "__main__":
    asyncio.run(main())
```

When using the `aiohttp` engine, you'll need to construct the `aiohttp.ClientSession` yourself and pass it to the `ApiClient` constructor. If you're wondering why this is necessary, take a look in the [`aiohttp` FAQ](https://docs.aiohttp.org/en/stable/faq.html#why-is-creating-a-clientsession-outside-of-an-event-loop-dangerous).

The accessor functions are now `async` as well, so you'll need to `await` them.

### Example Upgrade

Akin to FastAPI's [Example Upgrade](https://fastapi.tiangolo.com/#example-upgrade), we also provide an upgrade of our own simple example above which can be found in [`examples/upgraded`](examples/upgraded):

```python
# my_api.py

from typing import Annotated, Any

from rest_rpc import ApiDefinition, Query, Body

from pydantic import BaseModel

api_def = ApiDefinition()


class ReadItemResponse(BaseModel):
    item_id: int
    q: str | None


class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None


class UpdateItemResponse(BaseModel):
    item_name: str
    item_id: int


@api_def.get("/")
def read_root() -> dict[str, str]: ...


@api_def.get("/items/{item_id}")
def read_item(
    item_id: int, q: Annotated[str | None, Query()] = None
) -> ReadItemResponse: ...


@api_def.put("/items/{item_id}")
def update_item(item_id: int, item: Annotated[Item, Body()]) -> UpdateItemResponse: ...
```

```python
# main.py

from rest_rpc import ApiImplementation

from my_api import api_def, ReadItemResponse, UpdateItemResponse

api_impl = ApiImplementation(api_def)


@api_impl.handler
def read_root():
    return {"Hello": "World"}


@api_impl.handler
def read_item(item_id, q):
    return ReadItemResponse(item_id=item_id, q=q)


@api_impl.handler
def update_item(item_id, item):
    return UpdateItemResponse(item_name=item.name, item_id=item_id)


app = api_impl.make_fastapi()
```

```python
# client_sync.py

from rest_rpc import ApiClient

from my_api import api_def, ReadItemResponse, UpdateItemResponse, Item


def main() -> None:
    api_client = ApiClient(api_def, engine="requests", base_url="http://127.0.0.1:8000")

    result = api_client.read_root()
    print(result)
    assert result == {"Hello": "World"}

    result2 = api_client.read_item(item_id=42, q="Foo")
    print(result2)
    assert result2 == ReadItemResponse(item_id=42, q="Foo")

    result3 = api_client.update_item(item_id=42, item=Item(name="pie", price=3.14))
    print(result3)
    assert result3 == UpdateItemResponse(item_name="pie", item_id=42)


if __name__ == "__main__":
    main()
```

Here, we make generous use of pydantic's `BaseModel`. This is the recommended way, so instead of returning `dict` instances, you should always aim for `BaseModel` instead. This makes the intent of the API much clearer and makes type-checking more robust.

### In the Webbrowser (Pyodide / PyScript)

[Pyodide](https://pyodide.org/en/stable/) and [PyScript](https://pyscript.net/) are two methods to use Python in the webbrowser. They both have wrappers around the browser's [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API) and REST-RPC supports both of them. Just use `engine="pyodide"` or `engine="pyscript"`. See the [`examples/webapp`](examples/webapp) directory for a complete minimal example webapp in which the front-end is served via FastAPI.

### Custom Transport

If you're not happy of the selection for the `engine` parameter, you can also provide your own. Just pass `engine="custom"` and your hand-crafted transport function.

This is useful if you already have an HTTP abstraction, want to integrate with a test harness, or need special authentication logic.
    
## Restrictions and Limitations

Here are some notable differences between building your REST API with pure FastAPI and using REST-RPC:

- With REST-RPC, you need to add an annotation to _every_ parameter and the return value of routes. With FastAPI, this is not strictly required and only needed when you want the type-checking.
- FastAPI has some rules to automatically infer if a parameter is supposed to be a path, query, or body parameter which can be found in the [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters). You can also annotate parameters with `Path()`, `Query()`, or `Body()` to make it explicit. REST-RPC does _not_ do such automatic inference. You _have_ to annotate query parameters with `Query()` and body parameters with `Body()`. Only path parameters are allowed to not have such an annotation. REST-RPC provides its own versions of `Query()`, `Body()` etc. which are mapped to FastAPI's versions when creating a FastAPI app, but they do support less features than the FastAPI versions to simplify things.
- REST-RPC only supports Body parameters for `PATCH`, `PUT`, and `POST`, not for `GET` and `DELETE`. Furthermore, only one Body parameter is supported, and FastAPI's `Body(embed=True)` is not supported.
- Out of FastAPI's [Request Parameters](https://fastapi.tiangolo.com/reference/parameters/), REST-RPC only supports `Path`, `Query`, `Body`, and `Header`, not `Cookie`, `Form`, or `File`.

Another important note: In the API implementation, you don't need to add any annotations or default values to the route handlers. So usually, the only things that strictly have to match are the names of the route handler functions and their parameters. So this is okay:

```python
@api_def.get("/foo")
def foo(bar: int = 42, baz: Annotated[str | None, Query()] = None) -> dict[str, Any]: ...

# [...]

@api_impl.handler
def foo(bar, baz):
    return {"bar": bar, "baz": baz}
```

However, if you _decide_ to add annotations or default values, they _do_ have to match exactly (except for `Annotated[]`, where you must use the first argument instead), so these are all okay:

```python
@api_impl.handler
def foo(bar: int, baz: str | None):
    return {"bar": bar, "baz": baz}
    
@api_impl.handler
def foo(bar: int = 42, baz: str | None = None):
    return {"bar": bar, "baz": baz}
```

But these are not:

```python
@api_impl.handler
def foo(bar: float, baz: int):
    return {"bar": bar, "baz": baz}
    
@api_impl.handler
def foo(bar = 0, baz = "Baz"):
    return {"bar": bar, "baz": baz}
```


> [!TIP]
> Personal recommendation: Keep it simple in the prototyping phase since things are likely to be changed around and you'll be annoyed by changing the signatures in two places instead of one. Once the API definition becomes stable, you can still add the annotations to the API implementation to improve expressivity.

## Performance Comparison

The [`benchmark`](benchmark) directory contains a very simple benchmarking script, where we compare the performance of the different engines on a simple `get("/")` without parameters. Your mileage may vary in other situations.

As you can see below, `httpx` performs noticeably worse in this specific benchmark.

So it's probably a good idea to use `requests` or `urllib3` if you want synchronous requests, and of course `aiohttp` when you prefer `async`.

![Bar graph comparing the performance of the supported engines](benchmark/benchmark.png)

## Planned Features

- Support for authentication. At the moment, you can only do this via middlewares in the backend implementation.
- Support parameters in `ApiImplementation.make_fastapi()` that are forwarded to the `FastAPI()` constructor.
- Missing something? Create an issue.
