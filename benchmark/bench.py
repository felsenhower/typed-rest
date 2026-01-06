import asyncio
import json
import socket
import threading
import time
from contextlib import contextmanager

import aiohttp
import uvicorn
from rest_rpc import ApiClient, ApiDefinition, ApiImplementation


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@contextmanager
def fastapi_server(app):
    port = _get_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def get_api() -> ApiDefinition:
    api_def = ApiDefinition()

    @api_def.get("/")
    def read_root() -> dict[str, str]: ...

    return api_def


def get_impl(api_def) -> ApiImplementation:
    api_impl = ApiImplementation(api_def)

    @api_impl.handler
    def read_root():
        return {"Hello": "World"}

    return api_impl


NUM_REPETITIONS = 1000


async def main() -> None:
    api_def = get_api()
    api_impl = get_impl(api_def)
    app = api_impl.make_fastapi()
    with fastapi_server(app) as base_url:
        api_clients: dict[str, ApiClient] = dict()
        for engine in (
            "httpx",
            "requests",
            "urllib3",
        ):
            api_clients[engine] = ApiClient(api_def, engine=engine, base_url=base_url)
        runtimes: dict[str, float] = dict()
        async with aiohttp.ClientSession() as session:
            api_clients["aiohttp"] = ApiClient(
                api_def, engine="aiohttp", session=session, base_url=base_url
            )
            for engine, api_client in api_clients.items():
                print(f'Testing "{engine}"...', end="", flush=True)
                time_before = time.perf_counter()
                for _ in range(NUM_REPETITIONS):
                    if engine == "aiohttp":
                        result = await api_client.read_root()
                    else:
                        result = api_client.read_root()
                    assert result == {"Hello": "World"}
                time_after = time.perf_counter()
                runtime = time_after - time_before
                runtimes[engine] = runtime
                print(f" {runtime:0.3f} seconds", flush=True)
        print(runtimes)
        with open("runtimes.json", "w") as f:
            json.dump(runtimes, f)


if __name__ == "__main__":
    asyncio.run(main())
