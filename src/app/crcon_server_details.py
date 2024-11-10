import urllib.parse
from typing import Optional


class CRCONServerDetails:
    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        rcon_headers: Optional[dict[str, str]] = None,
    ):
        scheme, netloc, path, *_ = urllib.parse.urlparse(api_base_url)
        if scheme not in ["http", "https"]:
            raise ValueError(f"Invalid scheme {scheme}")

        path = path.removesuffix("/")
        self.api_url = urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))
        ws_scheme = "wss" if scheme == "https" else "ws"
        self.websocket_url = urllib.parse.urlunparse(
            (ws_scheme, netloc, path, None, None, None)
        )
        self.api_key = api_key
        self.rcon_headers = rcon_headers
