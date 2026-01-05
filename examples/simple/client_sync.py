#!/usr/bin/env python3

from typed_rest import ApiClient

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
