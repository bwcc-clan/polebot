"""A module containing utilities for caching."""

from collections.abc import Callable, Hashable
from typing import Any, ParamSpec, Protocol, TypeVar, runtime_checkable

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
    """A class representing an item in a cache."""
    def __init__(self, ttl: float, value: T) -> None:
        """Initialises a cache item.

        Args:
            ttl (float): The time-to-live for the cache item.
            value (T): The value to cache.
        """
        self.ttl = ttl
        self.value = value


@runtime_checkable
class CacheProvider[T](Protocol):
    """A protocol for classes that provide a cache for caching decorators."""
    def get_cache(self, cache_hint: str | None = None) -> cachetools.TLRUCache[Any, CacheItem[T]]:
        """Returns a cache for the instance.

        Args:
            cache_hint (str | None, optional): The cache hint that was provided in the `ttl_cached` decorator.

        Returns:
            cachetools.TLRUCache[Any, CacheItem[T]]: The cache for the instance.
        """
        ...


def ttl_cached(
    time_to_live: float, cache_hint: str | None = None,
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    """A decorator that caches the result of a method for a specified time-to-live."""
    def try_get_cache(
        wrapped, instance, args: tuple[Hashable, ...], kwargs: dict[str, Any],  # noqa: ANN001
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
        async def _async_run(wrapped, instance, args, kwargs):  # noqa: ARG001, ANN001, ANN202
            cache, cache_key, cached_value = try_get_cache(wrapped, instance, args, kwargs)
            if cached_value:
                return cached_value.value
            value = await wrapped(*args, **kwargs)
            cache[cache_key] = CacheItem(time_to_live, value)
            return value

        @wrapt.decorator
        def _sync_run(wrapped, instance, args, kwargs):  # noqa: ARG001, ANN001, ANN202
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


def cache_item_ttu(key: Any, value: CacheItem[Any], now: float) -> float:  # noqa: ANN401
    """Returns the time-to-use for a cache item.

    Args:
        key (Any): The cache key for the item.
        value (CacheItem[Any]): The item being added into the cache.
        now (float): A value representing the current time.

    Returns:
        float: A value representing the time-to-use for the cache item.
    """
    return now + value.ttl
