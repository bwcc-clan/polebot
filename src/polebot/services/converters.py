"""This module configures the converters for JSON serialization and deserialization."""


from cattrs.preconf.bson import BsonConverter
from cattrs.preconf.bson import make_converter as make_bson_converter
from cattrs.preconf.json import JsonConverter
from cattrs.preconf.json import make_converter as make_json_converter
from yarl import URL


def make_params_converter() -> JsonConverter:
    """Creates a converter for server parameters.

    Returns:
        JsonConverter: The JSON converter.
    """
    config_converter = make_json_converter()
    return config_converter


def make_db_converter() -> BsonConverter:
    """Creates a BSON converter for MongoDb database.

    Returns:
        BsonConverter: The BSON converter.
    """
    converter = make_bson_converter()
    converter.register_unstructure_hook(URL, lambda u: str(u))
    return converter
