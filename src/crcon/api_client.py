"""A client for the CRCON API."""

import asyncio
from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from types import NoneType, TracebackType
from typing import Self, Unpack

import aiohttp
import aiohttp.typedefs

from .api_models import ApiResult, Layer, ServerStatus, VoteMapUserConfig
from .api_request_context import ApiRequestContext, ApiRequestParams
from .converters import make_rcon_converter
from .exceptions import ApiClientError
from .server_connection_details import ServerConnectionDetails


class ApiClient(AbstractAsyncContextManager):
    """A client for the CRCON API.

    This client is used to interact with the CRCON API, which provides an interface to the Hell Let Loose server's RCON
    interface.
    """

    def __init__(self, crcon_details: ServerConnectionDetails, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the client.

        Args:
            crcon_details (ServerCRCONDetails): The server configuration.
            loop (asyncio.AbstractEventLoop): The event loop to use for the client.
        """
        self._crcon_details = crcon_details
        self._loop = loop
        self._exit_stack = AsyncExitStack()
        self._session: aiohttp.ClientSession | None = None
        self._converter = make_rcon_converter()

    async def __aenter__(self) -> Self:
        """Enter the context manager and set up the client."""
        await self._exit_stack.__aenter__()
        headers = {"Authorization": f"BEARER {self._crcon_details.api_key}"}
        if self._crcon_details.rcon_headers:
            headers.update(self._crcon_details.rcon_headers)
        self._session = await self._exit_stack.enter_async_context(
            aiohttp.ClientSession(loop=self._loop, headers=headers),
        )
        return self

    async def __aexit__(
        self,
        exc_t: type[BaseException] | None,
        exc_v: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context manager and clean up the client."""
        ret = await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)
        self._session = None
        return ret

    async def aclose(self) -> None:
        """Immediately unwind the context stack."""
        await self.__aexit__(None, None, None)

    async def get_status(self) -> ServerStatus:
        """Get the status of the server."""
        result = await self._call_api(result_type=ServerStatus, method=aiohttp.hdrs.METH_GET, endpoint="api/get_status")
        return result

    async def get_maps(self) -> Iterable[Layer]:
        """Get the list of maps on the server."""
        result = await self._call_api(result_type=list[Layer], method=aiohttp.hdrs.METH_GET, endpoint="api/get_maps")
        return result

    async def get_votemap_config(self) -> VoteMapUserConfig:
        """Get the server's vote map configuration."""
        result = await self._call_api(
            result_type=VoteMapUserConfig,
            method=aiohttp.hdrs.METH_GET,
            endpoint="api/get_votemap_config",
        )
        return result

    async def get_votemap_whitelist(self) -> Iterable[str]:
        """Get the list of maps in the vote map whitelist."""
        result = await self._call_api(
            result_type=list[str],
            method=aiohttp.hdrs.METH_GET,
            endpoint="api/get_votemap_whitelist",
        )
        return result

    async def set_votemap_whitelist(self, map_names: Iterable[str]) -> None:
        """Set the vote map whitelist."""
        body = {"map_names": list(map_names)}
        await self._call_api(
            result_type=NoneType,
            method=aiohttp.hdrs.METH_POST,
            endpoint="api/set_votemap_whitelist",
            json=body,
        )

    async def reset_votemap_state(self) -> None:
        """Reset the vote map state."""
        body: dict[str, str] = {}
        await self._call_api(
            result_type=NoneType,
            method=aiohttp.hdrs.METH_POST,
            endpoint="api/reset_votemap_state",
            json=body,
        )

    async def _call_api[T](
        self,
        result_type: type[T],
        method: str,
        endpoint: str,
        **kwargs: Unpack[aiohttp.client._RequestOptions],
    ) -> T:
        async with self._make_request(method=method, endpoint=endpoint, **kwargs) as resp:
            j = await resp.json()
        api_result = self._converter.structure(j, ApiResult[result_type])  # type: ignore[valid-type]
        if api_result.failed:
            raise ApiClientError(
                f"{api_result.command} command failed, error={api_result.error}",
                api_result.command,
                api_result.error or "",
                api_result.version,
            )

        if result_type is NoneType:
            return  # type: ignore[return-value]
        assert api_result.result is not None  # noqa: S101
        return api_result.result

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Unpack[aiohttp.client._RequestOptions],
    ) -> ApiRequestContext:
        if not self._session:
            raise RuntimeError("CRCONApiClient context must be entered")

        params = ApiRequestParams(
            method=method,
            url=self._crcon_details.api_url / endpoint,
            kwargs=kwargs,
        )
        return ApiRequestContext(session=self._session, params=params)
