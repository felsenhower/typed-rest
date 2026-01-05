import pyodide
from pyscript import document, window

from my_api import api_def
from typed_rest import ApiClient, CommunicationError

api_client = ApiClient(api_def, engine="pyscript", base_url="/api/")


async def make_api_request(event):
    try:
        data = await api_client.read_item(item_id=42, q="Foobar")
    except CommunicationError as e:
        window.alert("Something went wrong. See the browser console for more details!")
        raise e
    window.alert(f"Received {data=}")


def main():
    print("Hello from Python!")
    btn = document.querySelector("#make_request_button")
    btn.addEventListener("click", pyodide.ffi.create_proxy(make_api_request))


if __name__ == "__main__":
    main()
