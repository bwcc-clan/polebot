"""This module configures the converters for JSON serialization and deserialization."""

from typing import Any

from cattrs.preconf.bson import BsonConverter
from cattrs.preconf.bson import make_converter as make_bson_converter
from cattrs.preconf.json import JsonConverter, make_converter
from yarl import URL


def make_rcon_converter() -> JsonConverter:
    """Creates a JSON converter for RCON messages.

    Returns:
        JsonConverter: The JSON converter.
    """
    from types import NoneType
    rcon_converter = make_converter()

    @rcon_converter.register_structure_hook
    def _json_null_hook(val: Any, _: Any) -> NoneType:  # type: ignore[valid-type]  # noqa: ANN401
        """This hook will be registered for JSON nulls.

        These are needed so that an ApiResult can have no 'result', which is represented by a JSON null in the received
        response.
        """
        return None

    return rcon_converter


def make_params_converter() -> JsonConverter:
    """Creates a JSON converter for server parameters.

    Returns:
        JsonConverter: The JSON converter.
    """
    config_converter = make_converter()
    return config_converter


def make_db_converter() -> BsonConverter:
    """Creates a BSON converter for MongoDb database.

    Returns:
        BsonConverter: The BSON converter.
    """
    converter = make_bson_converter()
    converter.register_unstructure_hook(URL, lambda u: str(u))
    return converter
