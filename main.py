from typed_rest import ApiImplementation

from my_api import api_def

api_impl = ApiImplementation(api_def)


@api_impl.handler
def read_root():
    return {"Hello": "World"}


@api_impl.handler
def read_item(item_id, q):
    return {"item_id": item_id, "q": q}


app = api_impl.make_fastapi()
