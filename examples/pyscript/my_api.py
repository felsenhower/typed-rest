from typing import Annotated

from typed_rest import ApiDefinition, Query

api_def = ApiDefinition()


@api_def.get("/")
def read_root() -> dict[str, str]: ...


@api_def.get("/items/{item_id}")
def read_item(
    item_id: int, q: Annotated[str | None, Query()] = None
) -> dict[str, int | str | None]: ...
