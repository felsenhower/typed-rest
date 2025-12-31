#!/usr/bin/env python3

from my_api import api_def

from typed_rest import ApiClient


def main() -> None:
    api_client = ApiClient(api_def, engine="requests", base_url="http://127.0.0.1:8000")
    print(api_client.read_root())
    print(api_client.read_item(item_id=42, q="Foo"))


if __name__ == "__main__":
    main()
