import datetime as dt
from collections.abc import Callable, Coroutine
from typing import Any

from .key import KEY as KEY
from .lru import LRU as LRU

class AsyncTTL:
    class _TTL(LRU):
        time_to_live: dt.timedelta
        maxsize: int
        def __init__(self, time_to_live: int | None, maxsize: int | None) -> None: ...
        def __contains__(self, key: object) -> bool: ...
        def __getitem__(self, key: str) -> Any: ...
        def __setitem__(self, key: str, value: Any) -> None: ...
    ttl: int
    skip_args: int
    def __init__(self, time_to_live: int | None = 60, maxsize: int | None = 1024, skip_args: int = 0) -> None:
        """

        :param time_to_live: Use time_to_live as None for non expiring cache
        :param maxsize: Use maxsize as None for unlimited size cache
        :param skip_args: Use `1` to skip first arg of func in determining cache key
        """
    def __call__(self, func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]: ...
