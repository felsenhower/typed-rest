import threading
import time
import socket
from contextlib import contextmanager
import pytest
import uvicorn


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def fastapi_server():
    @contextmanager
    def _run(app):
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

    return _run
