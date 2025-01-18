"""Configuration classes for the application."""

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

from attrs import define, field, frozen, validators
from bson import ObjectId
from yarl import URL

from polebot.app_config import AppConfig

from . import converters
from .utils import expand_environment

_logger = logging.getLogger(__name__)


def _validate_api_key(_instance: Any, _attribute: Any, value: str) -> None:  # noqa: ANN401
    if value.strip() == "":
        raise ValueError("API key must not be blank")


def _validate_api_url(_instance: Any, _attribute: Any, value: URL) -> None:  # noqa: ANN401
    if value.scheme not in ["http", "https"]:
        raise ValueError(f"Invalid scheme {value.scheme}")


def _str_to_url(val: str) -> URL:
    return URL(val).with_query(None).with_fragment(None).with_user(None).with_password(None)


@frozen(auto_detect=True)
class ServerCRCONDetails:
    """Details for connecting to a server via CRCON."""
    api_url: URL = field(converter=_str_to_url, validator=_validate_api_url)
    api_key: str = field(converter=expand_environment, validator=_validate_api_key)
    websocket_url: URL = field(init=False)
    rcon_headers: dict[str, str] | None = None

    @websocket_url.default  # type: ignore[reportFunctionMemberAccess,unused-ignore]
    def _set_derived_attributes(self) -> URL:
        # The attrs docs on derived attributes https://www.attrs.org/en/stable/init.html#derived-attributes
        # suggest to implement them as a decorator-based default
        ws_scheme = "wss" if self.api_url.scheme == "https" else "ws"
        return self.api_url.with_scheme(ws_scheme)


@frozen(kw_only=True)
class EnvironmentGroup:
    """Represents a group of environments and their parameters."""
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)


@frozen(kw_only=True)
class MapGroup:
    """Represents a group of maps and their parameters."""
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class WeightingParameters:
    """Parameters for map and environment weighting."""
    groups: dict[str, MapGroup]
    environments: dict[str, EnvironmentGroup]


@frozen(kw_only=True)
class ServerParameters:
    """Parameters for a CRCON server instance."""
    server_name: str
    crcon_details: ServerCRCONDetails
    weighting_params: WeightingParameters


def get_server_params(app_cfg: AppConfig) -> ServerParameters:
    """Get the server configuration from the configuration directory."""
    params_converter = converters.make_params_converter()
    config_dir = Path(app_cfg.config_dir)
    if not config_dir.is_absolute():
        config_dir = Path(__file__).parent / config_dir

    _logger.debug("Looking for server config files in %s", str(config_dir))
    for file in config_dir.glob("*.json"):
        _logger.debug("Loading server config file %s", str(file))
        server_params: ServerParameters | None = None
        try:
            contents = file.read_text()
            json_contents = json.loads(contents)
            server_params = params_converter.structure(json_contents, ServerParameters)
        except Exception as ex:  # noqa: BLE001
            _logger.warning("Unable to load file %s as a server config file", str(file), exc_info=ex)
        if server_params:
            return server_params

    raise RuntimeError(f"No valid configuration files found in '{config_dir}'")


@define(kw_only=True)
class GuildServer:
    _id: ObjectId = field(factory=ObjectId)
    guild_id: int
    server_name: str
    crcon_details: ServerCRCONDetails
    created_date_utc: dt.datetime

    @property
    def id(self) -> ObjectId:
        return self._id
