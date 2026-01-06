import pytest
from rest_rpc import ApiClient, ApiDefinition, NetworkError


@pytest.mark.parametrize("engine", ["requests", "httpx", "urllib3"])
def test_network_error(engine):
    api = ApiDefinition()

    @api.get("/")
    def root() -> dict[str, str]: ...

    client = ApiClient(
        api,
        engine=engine,
        base_url="http://this-domain-does-not-exist.example",
    )

    with pytest.raises(NetworkError):
        client.root()
