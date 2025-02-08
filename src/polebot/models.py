"""Configuration classes for the application."""

import datetime as dt
import json
import logging
from pathlib import Path

from attrs import define, field, frozen, validators
from bson import ObjectId

from crcon.server_connection_details import ServerConnectionDetails
from polebot.app_config import AppConfig

from .services import converters

_logger = logging.getLogger(__name__)


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
    crcon_details: ServerConnectionDetails
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


UNSAVED_SENTINEL = -1


@define(kw_only=True)
class DbModel:
    _id: ObjectId = field(factory=ObjectId)
    _v: int = field(default=UNSAVED_SENTINEL)
    _created_utc: dt.datetime | None = field(default=None)
    _modified_utc: dt.datetime | None = field(default=None)

    @property
    def id(self) -> ObjectId:
        return self._id

    @property
    def db_version(self) -> int:
        return self._v

    @property
    def created_date_utc(self) -> dt.datetime:
        if not self._created_utc:
            raise ValueError("Created date not set - has the document been saved?")
        return self._created_utc

    @property
    def modified_date_utc(self) -> dt.datetime:
        if not self._modified_utc:
            raise ValueError("Modified date not set - has the document been saved?")
        return self._modified_utc


@define(kw_only=True)
class GuildServer(DbModel):
    guild_id: int
    label: str = field(validator=[validators.min_len(1), validators.max_len(10)])
    name: str = field(validator=[validators.min_len(1), validators.max_len(100)])
    crcon_details: ServerConnectionDetails
    weighting_parameters: WeightingParameters | None = field(default=None)


@define(kw_only=True)
class GuildPlayerGroup(DbModel):
    guild_id: int
    label: str = field(validator=[validators.min_len(1), validators.max_len(10)])
    selector: str = field(validator=[validators.min_len(1), validators.max_len(100)])
