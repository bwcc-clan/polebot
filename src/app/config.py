import os

import environ

from .crcon_server_details import CRCONServerDetails


def get_required_environ(name: str) -> str:
    value = os.environ.get(name, None)
    if not value:
        raise RuntimeError(f"Environment variable {name} not set")
    return value


def get_server_details() -> CRCONServerDetails:
    return CRCONServerDetails(
        get_required_environ("RCON_API_BASE_URL"), get_required_environ("RCON_API_KEY")
    )

@environ.config(prefix="APP")
class AppConfig:
    @environ.config
    class Paths:
        weighting_config = environ.var("weighting_config.json")
