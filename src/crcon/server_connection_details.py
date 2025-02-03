from typing import Any

from attrs import field, frozen
from yarl import URL

from utils import expand_environment


def _validate_api_key(_instance: Any, _attribute: Any, value: str) -> None:  # noqa: ANN401
    if value.strip() == "":
        raise ValueError("API key must not be blank")


def _validate_api_url(_instance: Any, _attribute: Any, value: URL) -> None:  # noqa: ANN401
    if value.scheme not in ["http", "https"]:
        raise ValueError(f"Invalid scheme {value.scheme}")


def _str_to_url(val: str) -> URL:
    return URL(val).with_query(None).with_fragment(None).with_user(None).with_password(None)


@frozen(auto_detect=True)
class ServerConnectionDetails:
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
