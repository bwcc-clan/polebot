"""Configuration classes for the application."""

import json
import logging
from pathlib import Path
from typing import Any

import environ
from attrs import field, frozen, validators
from yarl import URL

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
class EnvironmentGroupConfig:
    """Configuration for a group of environments."""
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)


@frozen(kw_only=True)
class MapGroupConfig:
    """Configuration for a group of maps."""
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class WeightingConfig:
    """Configuration for map and environment weighting."""
    groups: dict[str, MapGroupConfig]
    environments: dict[str, EnvironmentGroupConfig]


@frozen(kw_only=True)
class ServerConfig:
    """Configuration for a CRCON server instance."""
    server_name: str
    crcon_details: ServerCRCONDetails
    weighting_config: WeightingConfig


@environ.config(prefix="APP")
class AppConfig:
    """Configuration for the application."""
    config_dir: str = environ.var(".config")


def get_server_config(app_cfg: AppConfig) -> ServerConfig:
    """Get the server configuration from the configuration directory."""
    config_converter = converters.make_config_converter()
    config_dir = Path(app_cfg.config_dir)
    if not config_dir.is_absolute():
        config_dir = Path(__file__).parent / config_dir

    _logger.debug("Looking for server config files in %s", str(config_dir))
    for file in config_dir.glob("*.json"):
        _logger.debug("Loading server config file %s", str(file))
        server_config: ServerConfig | None = None
        try:
            contents = file.read_text()
            json_contents = json.loads(contents)
            server_config = config_converter.structure(json_contents, ServerConfig)
        except Exception as ex:  # noqa: BLE001
            _logger.warning("Unable to load file %s as a server config file", str(file), exc_info=ex)
        if server_config:
            return server_config

    raise RuntimeError(f"No valid configuration files found in {config_dir}")
