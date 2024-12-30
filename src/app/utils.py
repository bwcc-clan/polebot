
import asyncio
import functools
import os
import random
from collections.abc import Awaitable, Callable, Generator
from typing import Any, TypeGuard, TypeVar, overload

from yarl import URL

BACKOFF_INITIAL_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_INITIAL_DELAY", "5"))
BACKOFF_MIN_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_MIN_DELAY", "3.1"))
BACKOFF_MAX_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_MAX_DELAY", "90.0"))
BACKOFF_FACTOR = float(os.environ.get("LOGSTREAM_BACKOFF_FACTOR", "1.618"))


def backoff(
    initial_delay: float = BACKOFF_INITIAL_DELAY,
    min_delay: float = BACKOFF_MIN_DELAY,
    max_delay: float = BACKOFF_MAX_DELAY,
    factor: float = BACKOFF_FACTOR,
) -> Generator[float]:
    """
    Generate a series of backoff delays between reconnection attempts.

    Yields:
        How many seconds to wait before retrying to connect.

    """
    # Add a random initial delay between 0 and 5 seconds.
    # See 7.2.3. Recovering from Abnormal Closure in RFC 6455.
    yield random.random() * initial_delay
    delay = min_delay
    while delay < max_delay:
        yield delay
        delay *= factor
    while True:
        yield max_delay


def expand_environment(value: str) -> str:
    """
    If `value` starts with the `!!env:§` magic prefix, and the remainder of `value` refers to an environment
    variable, returns an overridden `value`. Otherwise, returns the input value.

    Args:
        value (str): The value to expand.

    Returns:
        str: The expanded value, replaced with the value of an environment variable if so configured.
    """
    ENV_PREFIX = "!!env:"
    if value.startswith(ENV_PREFIX):
        env_var = value.removeprefix(ENV_PREFIX)
        env_value = os.environ.get(env_var, None)
        if env_value:
            value = env_value
    return value


def str_to_url(val: str) -> URL:
    return URL(val).with_query(None).with_fragment(None).with_user(None).with_password(None)

T = TypeVar("T")
AwaitableCallable = Callable[..., Awaitable[T]]


@overload
def is_async_callable(obj: AwaitableCallable[T]) -> TypeGuard[AwaitableCallable[T]]: ...


@overload
def is_async_callable(obj: Any) -> TypeGuard[AwaitableCallable[Any]]: ...


def is_async_callable(obj: Any) -> Any:
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or (callable(obj) and asyncio.iscoroutinefunction(obj.__call__))    # type: ignore[reportFunctionMemberAccess,unused-ignore]

