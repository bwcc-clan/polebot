import json
import logging
from pathlib import Path
from typing import Any, Optional

import environ
from attrs import field, frozen, validators
from yarl import URL

from . import converters
from .utils import expand_environment, str_to_url

_logger = logging.getLogger(__name__)


def _validate_api_url(_instance: Any, _attribute: Any, value: URL) -> None:
    if value.scheme not in ["http", "https"]:
        raise ValueError(f"Invalid scheme {value.scheme}")


@frozen(auto_detect=True)
class ServerCRCONDetails:
    api_url: URL = field(converter=str_to_url, validator=_validate_api_url)
    api_key: str = field(converter=expand_environment)
    websocket_url: URL = field(init=False)
    rcon_headers: Optional[dict[str, str]] = None

    @websocket_url.default  # type: ignore[reportFunctionMemberAccess,unused-ignore]
    def ann__attrs_post_init__(self) -> URL:
        # The attrs docs on derived attributes https://www.attrs.org/en/stable/init.html#derived-attributes
        # suggest to implement them as a decorator-based default
        ws_scheme = "wss" if self.api_url.scheme == "https" else "ws"
        return self.api_url.with_scheme(ws_scheme)


@frozen(kw_only=True)
class EnvironmentGroupConfig:
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)


@frozen(kw_only=True)
class MapGroupConfig:
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class WeightingConfig:
    groups: dict[str, MapGroupConfig]
    environments: dict[str, EnvironmentGroupConfig]


@frozen(kw_only=True)
class ServerConfig:
    server_name: str
    crcon_details: ServerCRCONDetails
    weighting_config: WeightingConfig


@environ.config(prefix="APP")
class AppConfig:
    config_dir: str = environ.var(".config")


def get_server_config(app_cfg: AppConfig) -> ServerConfig:
    config_converter = converters.make_config_converter()
    config_dir = Path(app_cfg.config_dir)
    if not config_dir.is_absolute():
        config_dir = Path(__file__).parent / config_dir
    for file in config_dir.glob("*.json"):
        server_config: ServerConfig | None = None
        try:
            contents = file.read_text()
            json_contents = json.loads(contents)
            server_config = config_converter.structure(json_contents, ServerConfig)
        except Exception as ex:
            _logger.warning("Unable to load file %s as a server config file", str(file), exc_info=ex)
        if server_config:
            return server_config

    raise RuntimeError(f"No valid configuration files found in {config_dir}")
