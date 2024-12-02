from collections.abc import Callable, Coroutine
from typing import Any

from .key import KEY as KEY
from .lru import LRU as LRU

class AsyncLRU:
    lru: LRU
    def __init__(self, maxsize: int | None = 128) -> None:
        """
        :param maxsize: Use maxsize as None for unlimited size cache
        """
    def __call__(self, func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]: ...
