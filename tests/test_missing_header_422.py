from typing import Annotated

import pytest
from rest_rpc import ApiClient, ApiClientEngine, ApiDefinition, Header


def test_missing_required_header_results_in_http_error():
    api = ApiDefinition()

    @api.get("/need-header")
    def need_header(h: Annotated[str, Header()]) -> str:
        return h

    from rest_rpc import ApiImplementation

    impl = ApiImplementation(api)

    @impl.handler
    def need_header(h: str) -> str:
        return h

    app = impl.make_fastapi()
    client = ApiClient(api, ApiClientEngine.TESTCLIENT, app=app)

    with pytest.raises(ValueError):
        client.need_header(h=None)
