import asyncio
import time
from typing import Any, Optional

import cachetools
import pytest

from app.cache_utils import CacheItem, cache_item_ttu, ttl_cached


class HasCache:
    def __init__(self):
        self._cache = cachetools.TLRUCache[Any, CacheItem[Any]](maxsize=100, ttu=cache_item_ttu)

    def get_cache(self, cache_hint: Optional[str] = None) -> cachetools.TLRUCache[Any, CacheItem[Any]]:
        return self._cache

    @ttl_cached(time_to_live=0.05)
    def short_ttl(self) -> str:
        return f"Time: {time.monotonic()}"

    @ttl_cached(time_to_live=100)
    def long_ttl(self) -> str:
        return f"Time: {time.monotonic()}"

    @ttl_cached(time_to_live=0.05)
    async def short_ttl_async(self) -> str:
        await asyncio.sleep(0.01)
        return f"Time: {time.monotonic()}"

    @ttl_cached(time_to_live=100)
    async def long_ttl_async(self) -> str:
        await asyncio.sleep(0.01)
        return f"Time: {time.monotonic()}"

def describe_sync_methods():
    def with_short_ttl_results_change():
        # *** ARRANGE ***
        sut = HasCache()

        # *** ACT ***
        result1 = sut.short_ttl()
        time.sleep(0.25)
        result2 = sut.short_ttl()

        # *** ASSERT ***
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert result1 != result2

    def with_long_ttl_results_same():
        # *** ARRANGE ***
        sut = HasCache()

        # *** ACT ***
        result1 = sut.long_ttl()
        time.sleep(0.25)
        result2 = sut.long_ttl()

        # *** ASSERT ***
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert result1 == result2


def describe_async_methods():
    @pytest.mark.asyncio()
    async def with_short_ttl_results_change():
        # *** ARRANGE ***
        sut = HasCache()

        # *** ACT ***
        result1 = await sut.short_ttl_async()
        time.sleep(0.25)
        result2 = await sut.short_ttl_async()

        # *** ASSERT ***
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert result1 != result2

    @pytest.mark.asyncio()
    async def with_long_ttl_results_same():
        # *** ARRANGE ***
        sut = HasCache()

        # *** ACT ***
        result1 = await sut.long_ttl_async()
        time.sleep(0.25)
        result2 = await sut.long_ttl_async()

        # *** ASSERT ***
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert result1 == result2
