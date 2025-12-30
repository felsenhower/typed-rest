#!/usr/bin/env python3

from my_api import api_def

from typed_rest import ApiClient

from requests.exceptions import HTTPError


def main() -> None:
    api_client = ApiClient(api_def, engine="requests", base_url="http://127.0.0.1:8000")
    print(api_client.read_root())

    print(api_client.read_item(42, "Foo"))
    print(api_client.read_item(item_id=42, q="Foo"))

    print(api_client.read_item(42))
    print(api_client.read_item(item_id=42))

    try:
        print(api_client.read_item())
        raise RuntimeError("Too few parameters! This should throw, but it didn't!")
    except (HTTPError, ValueError):
        pass

    try:
        print(api_client.read_item(item_id=42, q="Foo", foo="bar"))
        raise RuntimeError("Too many parameters! This should throw, but it didn't!")
    except (HTTPError, ValueError):
        pass

    try:
        print(api_client.read_item(item_id=42.5, q="Foo"))
        raise RuntimeError("Wrong type! This should throw, but it didn't!")
    except (HTTPError, ValueError):
        pass

if __name__ == "__main__":
    main()
