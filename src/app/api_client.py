import asyncio
from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from types import TracebackType
from typing import Self, Type, Unpack

import aiohttp
import aiohttp.typedefs

from app.api_request_context import ApiRequestContext, ApiRequestParams

from . import converters
from .api_models import ApiResult, Layer, ServerStatus, VoteMapUserConfig
from .crcon_server_details import CRCONServerDetails


class CRCONApiClient(AbstractAsyncContextManager):
    def __init__(
        self, server_details: CRCONServerDetails, loop: asyncio.AbstractEventLoop
    ) -> None:
        self._server_details = server_details
        self._loop = loop
        self._exit_stack = AsyncExitStack()
        self._session: aiohttp.ClientSession | None = None
        self._converter = converters.rcon_converter

    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()
        headers = {"Authorization": f"BEARER {self._server_details.api_key}"}
        if self._server_details.rcon_headers:
            headers.update(self._server_details.rcon_headers)
        self._session = await self._exit_stack.enter_async_context(
            aiohttp.ClientSession(loop=self._loop, headers=headers)
        )
        return self

    async def __aexit__(
        self,
        exc_t: type[BaseException] | None,
        exc_v: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        ret = await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)
        self._session = None
        return ret

    async def aclose(self) -> None:
        """Immediately unwind the context stack."""
        await self.__aexit__(None, None, None)

    async def get_status(self) -> ServerStatus:
        result = await self._call_api(
            type=ServerStatus, method=aiohttp.hdrs.METH_GET, endpoint="api/get_status"
        )
        return result

    async def get_maps(self) -> Iterable[Layer]:
        result = await self._call_api(
            type=list[Layer], method=aiohttp.hdrs.METH_GET, endpoint="api/get_maps"
        )
        return result

    async def get_votemap_config(self) -> VoteMapUserConfig:
        result = await self._call_api(
            type=VoteMapUserConfig,
            method=aiohttp.hdrs.METH_GET,
            endpoint="api/get_votemap_config",
        )
        return result

    async def _call_api[T](
        self,
        type: Type[T],
        method: str,
        endpoint: str,
        **kwargs: Unpack[aiohttp.client._RequestOptions],
    ) -> T:
        async with self._make_request(
            method=method, endpoint=endpoint, **kwargs
        ) as resp:
            j = await resp.json()
        api_result = self._converter.structure(j, ApiResult[type])  # type: ignore[valid-type]
        if api_result.failed:
            raise RuntimeError(f"{endpoint} call failed")
        assert api_result.result is not None
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
            url=self._server_details.api_url / endpoint,
            kwargs=kwargs,
        )
        return ApiRequestContext(session=self._session, params=params)
