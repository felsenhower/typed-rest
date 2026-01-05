import aiohttp
import pytest
from typed_rest import (
    ApiClient,
    ApiDefinition,
    ApiImplementation,
    Request,
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

            async def transport(
                request: Request,
            ):
                url = f"{base_url}{request.path}"
                async with session.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    json=request.body,
                    headers=request.headers,
                    raise_for_status=True,
                ) as response:
                    return await response.json()

            api_client = ApiClient(api_def, engine="custom", transport=transport)
            result = await api_client.simple_route()
            assert result == {"Hello": "World"}
