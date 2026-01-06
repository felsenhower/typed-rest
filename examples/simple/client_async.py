#!/usr/bin/env python3

from rest_rpc import ApiClient

from my_api import api_def

import asyncio

import aiohttp

async def main() -> None:
    async with aiohttp.ClientSession() as session:
        api_client = ApiClient(api_def, engine="aiohttp", session=session, base_url="http://127.0.0.1:8000")
        result = await api_client.read_root()
        print(result)
        assert result == {"Hello": "World"}
        result2 = await api_client.read_item(item_id=42, q="Foo")
        print(result2)
        assert result2 == {"item_id": 42, "q": "Foo"}


if __name__ == "__main__":
    asyncio.run(main())
