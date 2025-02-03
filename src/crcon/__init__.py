from typing import Any

from yarl import URL

from .api_client import ApiClient
from .exceptions import ApiClientError, LogStreamMessageError, WebsocketConnectionError
from .log_stream_client import LogStreamClient, LogStreamClientConfig
from .server_connection_details import ServerConnectionDetails


def _validate_api_key(_instance: Any, _attribute: Any, value: str) -> None:  # noqa: ANN401
    if value.strip() == "":
        raise ValueError("API key must not be blank")


def _validate_api_url(_instance: Any, _attribute: Any, value: URL) -> None:  # noqa: ANN401
    if value.scheme not in ["http", "https"]:
        raise ValueError(f"Invalid scheme {value.scheme}")


def _str_to_url(val: str) -> URL:
    return URL(val).with_query(None).with_fragment(None).with_user(None).with_password(None)


__all__ = [
    "ApiClient",
    "LogStreamClient",
    "LogStreamClientConfig",
    "ApiClientError",
    "LogStreamMessageError",
    "WebsocketConnectionError",
    "ServerConnectionDetails",
]
