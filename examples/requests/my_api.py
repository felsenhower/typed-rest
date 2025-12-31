from typed_rest import ApiDefinition

api_def = ApiDefinition()


@api_def.get("/")
def read_root() -> dict[str, str]:
    pass


@api_def.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None) -> dict[str, int | str | None]:
    pass
