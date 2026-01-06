import aiohttp
import pytest
from rest_rpc import ApiClient, ApiDefinition, ApiImplementation, Request

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_custom_async_transport(fastapi_server):
    api = ApiDefinition()

    @api.get("/")
    def root() -> dict[str, str]: ...

    impl = ApiImplementation(api)

    @impl.handler
    def root():
        return {"ok": "yes"}

    app = impl.make_fastapi()

    async with aiohttp.ClientSession() as session:
        with fastapi_server(app) as base_url:

            async def transport(request: Request):
                async with session.request(
                    request.method,
                    f"{base_url}{request.path}",
                    params=request.query_params,
                    json=request.body,
                    headers=request.headers,
                ) as r:
                    r.raise_for_status()
                    return await r.json()

            client = ApiClient(api, engine="custom", transport=transport)
            result = await client.root()

    assert result == {"ok": "yes"}
