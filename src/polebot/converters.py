"""This module configures the converters for JSON serialization and deserialization."""

from typing import Any

from cattrs.preconf.json import JsonConverter, make_converter


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


def make_config_converter() -> JsonConverter:
    """Creates a JSON converter for server configuration.

    Returns:
        JsonConverter: The JSON converter.
    """
    config_converter = make_converter()
    return config_converter
