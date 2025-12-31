import pytest

from typed_rest import ApiDefinition


def test_add_route():
    api_def = ApiDefinition()

    @api_def.get("/")
    def dummy_route() -> dict[str, str]:
        pass


def test_detect_missing_return_annotation():
    api_def = ApiDefinition()
    with pytest.raises(ValueError):

        @api_def.get("/")
        def dummy_route():
            pass
