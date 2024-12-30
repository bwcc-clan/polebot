from collections.abc import Callable
from typing import Any, Hashable, Optional, ParamSpec, Protocol, TypeVar, runtime_checkable

import cachetools
import cachetools.keys
import wrapt

from .utils import is_async_callable

# Wrapt is untyped, plus it's highly verbose to type decorators etc so we ignore for now
# mypy: ignore-errors

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


T = TypeVar("T")


class CacheItem[T]:
    def __init__(self, ttl: float, value: T) -> None:
        self.ttl = ttl
        self.value = value


@runtime_checkable
class CacheProvider[T](Protocol):
    def get_cache(self, cache_hint: Optional[str] = None) -> cachetools.TLRUCache[Any, CacheItem[T]]: ...


def ttl_cached(
    time_to_live: float, cache_hint: Optional[str] = None
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    def try_get_cache(
        wrapped, instance, args: tuple[Hashable, ...], kwargs: dict[str, Any]
    ) -> tuple[cachetools.Cache[Any, CacheItem[Any]], tuple[Hashable, ...], CacheItem[Any] | None]:
        if not isinstance(instance, CacheProvider):
            raise RuntimeError("The wrapped method's parent class must implement the CacheProvider protocol")
        cache = instance.get_cache(cache_hint)
        func_name = wrapped.__name__
        cache_key = cachetools.keys.hashkey(*args, __func_name__=func_name, **kwargs)
        cache_result = cache.get(cache_key, None)
        return (cache, cache_key, cache_result)

    def wrapper(wrapped: Callable[Param, RetType]) -> Callable[Param, RetType]:
        @wrapt.decorator
        async def _async_run(wrapped, instance, args, kwargs):  # noqa: ARG001
            cache, cache_key, cached_value = try_get_cache(wrapped, instance, args, kwargs)
            if cached_value:
                return cached_value.value
            value = await wrapped(*args, **kwargs)
            cache[cache_key] = CacheItem(time_to_live, value)
            return value

        @wrapt.decorator
        def _sync_run(wrapped, instance, args, kwargs):  # noqa: ARG001
            cache, cache_key, cached_value = try_get_cache(wrapped, instance, args, kwargs)
            if cached_value:
                return cached_value.value
            value = wrapped(*args, **kwargs)
            cache[cache_key] = CacheItem(time_to_live, value)
            return value

        if is_async_callable(wrapped):
            return _async_run(wrapped)  # type: ignore[reportCallIssue]

        return _sync_run(wrapped)  # type: ignore[reportCallIssue,call-arg]

    return wrapper


def cache_item_ttu(key: Any, value: CacheItem[Any], now: float) -> float:
    return now + value.ttl
