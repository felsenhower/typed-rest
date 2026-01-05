import aiohttp
import fastapi
import pytest
from typed_rest import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    DecodeError,
    HttpError,
    NetworkError,
)

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_client_simple(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return {"Hello": "World"}

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        async with aiohttp.ClientSession() as session:
            api_client = ApiClient(
                api_def,
                engine="aiohttp",
                base_url=base_url,
                session=session,
            )
            result = await api_client.simple_route()
    assert result == {"Hello": "World"}


@pytest.mark.asyncio
async def test_network_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    async with aiohttp.ClientSession() as session:
        api_client = ApiClient(
            api_def,
            engine="aiohttp",
            base_url="http://i-made-up-this-url-4e40ac92-3df4-4aa9-9a6a-d6da534a67cf.org/api",
            session=session,
        )
        with pytest.raises(NetworkError):
            _ = await api_client.simple_route()


@pytest.mark.asyncio
async def test_http_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return fastapi.responses.JSONResponse(
                content={"Hello": "World"}, status_code=400
            )

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        async with aiohttp.ClientSession() as session:
            api_client = ApiClient(
                api_def,
                engine="aiohttp",
                base_url=base_url,
                session=session,
            )
            with pytest.raises(HttpError):
                _ = await api_client.simple_route()


@pytest.mark.asyncio
async def test_decode_error(fastapi_server):
    def make_def():
        api_def = ApiDefinition()

        @api_def.get("/")
        def simple_route() -> dict[str, str]: ...

        return api_def

    api_def = make_def()

    def make_impl(api_def):
        api_impl = ApiImplementation(api_def)

        @api_impl.handler
        def simple_route():
            return fastapi.Response(content="this is not json", media_type="text/plain")

        return api_impl

    api_impl = make_impl(api_def)

    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        async with aiohttp.ClientSession() as session:
            api_client = ApiClient(
                api_def,
                engine="aiohttp",
                base_url=base_url,
                session=session,
            )
            with pytest.raises(DecodeError):
                _ = await api_client.simple_route()
