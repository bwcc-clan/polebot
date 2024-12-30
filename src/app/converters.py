
from typing import Any

from cattrs.preconf.json import JsonConverter, make_converter
from yarl import URL


def str_to_url(val: Any, _: Any) -> URL:
    return URL(val)


def make_rcon_converter() -> JsonConverter:
    from types import NoneType
    rcon_converter = make_converter()

    @rcon_converter.register_structure_hook
    def json_null_hook(val: Any, _: Any) -> NoneType:  # type: ignore[valid-type]
        """
        This hook will be registered for JSON nulls. These are needed so that an ApiResult can have no 'result', which
        is represented by a JSON null in the received response.
        """
        return None

    return rcon_converter


def make_config_converter() -> JsonConverter:
    config_converter = make_converter()
    return config_converter
