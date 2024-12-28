import json
import logging
import os
from pathlib import Path
from typing import Optional

import environ
from attrs import field, frozen, validators
from yarl import URL

from app import converters

_logger = logging.getLogger(__name__)

@frozen(kw_only=True)
class EnvironmentGroupConfig:
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_factor: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)


@frozen(kw_only=True)
class MapGroupConfig:
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_factor: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class WeightingConfig:
    groups: dict[str, MapGroupConfig]
    environments: dict[str, EnvironmentGroupConfig]
@frozen(auto_detect=True)
class ServerCRCONDetails:
    api_url: URL
    api_key: str
    websocket_url: URL
    rcon_headers: Optional[dict[str, str]] = None

    def __init__(
        self, api_url: URL, api_key: str, rcon_headers: Optional[dict[str, str]] = None
    ) -> None:
        if api_url.scheme not in ["http", "https"]:
            raise ValueError(f"Invalid scheme {api_url.scheme}")

        api_url = (
            api_url.with_query(None)
            .with_fragment(None)
            .with_user(None)
            .with_password(None)
        )
        ws_scheme = "wss" if api_url.scheme == "https" else "ws"
        websocket_url = api_url.with_scheme(ws_scheme)

        api_key = self._expand_environment(api_key)

        self.__attrs_init__(api_url=api_url, api_key=api_key, websocket_url=websocket_url, rcon_headers=rcon_headers)  # type: ignore[attr-defined]

    def _expand_environment(self, value: str) -> str:
        """
        If `value` starts with the `!!env:§` magic prefix, and the remainder of `value` refers to an environment
        variable, returns an overridden `value`. Otherwise, returns the input value.

        Args:
            value (str): The value to expand.

        Returns:
            str: The expanded value, replaced with the value of an environment variable if so configured.
        """
        ENV_PREFIX = "!!env:"
        if value.startswith(ENV_PREFIX):
            env_var = value.removeprefix(ENV_PREFIX)
            env_value = os.environ.get(env_var, None)
            if env_value:
                value = env_value
        return value


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
