# REST-RPC – Upgraded Example

This is a small example for REST-RPC.

The structure of the API draws some inspiration from FastAPI's [upgraded example](https://fastapi.tiangolo.com/#example-upgrade).

## Usage

To start the FastAPI server, simply run
```shell
$ uv run fastapi dev
```

To run the client, open up a second terminal and run `uv run client_sync.py` (synchronous version) or `uv run client_async.py` (async version).

In the synchronous version, you can also use a different `engine` if you want. Simply pass one of the other supported engines (`httpx`, `urllib3`) to the `ApiClient` constructor.

## Structure

- `my_api.py`: Api definition (shared between back-end and front-end)
- `main.py`: FastAPI back-end
- `client_sync.py`: Front-end (sync)
- `client_async.py`: Front-end (async)
