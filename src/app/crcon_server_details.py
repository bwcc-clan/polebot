from typing import Optional

from yarl import URL


class CRCONServerDetails:
    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        rcon_headers: Optional[dict[str, str]] = None,
    ):
        url = URL(api_base_url)
        if url.scheme not in ["http", "https"]:
            raise ValueError(f"Invalid scheme {url.scheme}")

        self.api_url = url.with_query(None).with_fragment(None).with_user(None).with_password(None)
        ws_scheme = "wss" if url.scheme == "https" else "ws"
        self.websocket_url = self.api_url.with_scheme(ws_scheme)
        self.api_key = api_key
        self.rcon_headers = rcon_headers
