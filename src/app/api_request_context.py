# Performs retrying on requests to the CRCON API.
# Based on https://github.com/inyutin/aiohttp_retry
import abc
import asyncio
import logging
import random
from collections.abc import Generator, Iterable
from types import TracebackType
from typing import Any, Optional

import aiohttp
import aiohttp.typedefs
from attrs import frozen
from yarl import URL

_MIN_SERVER_ERROR_STATUS = 500


class RetryOptionsBase(abc.ABC):
    """
    Base class for request retry options.
    """
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        statuses: Iterable[int] | None = None,  # On which statuses we should retry
        exceptions: Iterable[type[Exception]] | None = None,  # On which exceptions we should retry, by default on all
        methods: Iterable[str] | None = None,  # On which HTTP methods we should retry
        retry_all_server_errors: bool = True,  # If should retry all 500 errors or not
    ) -> None:
        self.attempts: int = attempts
        if statuses is None:
            statuses = set()
        self.statuses: Iterable[int] = statuses

        if exceptions is None:
            exceptions = set()
        self.exceptions: Iterable[type[Exception]] = exceptions

        if methods is None:
            methods = {"HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST", "CONNECT", "PATCH"}
        self.methods: Iterable[str] = {method.upper() for method in methods}

        self.retry_all_server_errors = retry_all_server_errors

    @abc.abstractmethod
    def get_timeout(self, attempt: int, response: aiohttp.ClientResponse | None = None) -> float:
        """
        Gets the timeout (in seconds) for the retry attempt iteration.
        """
        raise NotImplementedError


class ExponentialRetry(RetryOptionsBase):
    """
    A retry option with exponential backoff.
    """
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: set[int] | None = None,  # On which statuses we should retry
        exceptions: set[type[Exception]] | None = None,  # On which exceptions we should retry
        methods: set[str] | None = None,  # On which HTTP methods we should retry
        retry_all_server_errors: bool = True,
    ) -> None:
        super().__init__(
            attempts=attempts,
            statuses=statuses,
            exceptions=exceptions,
            methods=methods,
            retry_all_server_errors=retry_all_server_errors,
        )

        self._start_timeout: float = start_timeout
        self._max_timeout: float = max_timeout
        self._factor: float = factor

    def get_timeout(
        self,
        attempt: int,
        response: aiohttp.ClientResponse | None = None,  # noqa: ARG002
    ) -> float:
        timeout = self._start_timeout * (self._factor**attempt)
        return min(timeout, self._max_timeout)


class JitterRetry(ExponentialRetry):
    """
    A retry option with exponential backoff and jitter.
    """
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: set[int] | None = None,  # On which statuses we should retry
        exceptions: set[type[Exception]] | None = None,  # On which exceptions we should retry
        methods: set[str] | None = None,  # On which HTTP methods we should retry
        random_interval_size: float = 2.0,  # size of interval for random component
        retry_all_server_errors: bool = True,
    ) -> None:
        super().__init__(
            attempts=attempts,
            start_timeout=start_timeout,
            max_timeout=max_timeout,
            factor=factor,
            statuses=statuses,
            exceptions=exceptions,
            methods=methods,
            retry_all_server_errors=retry_all_server_errors,
        )

        self._start_timeout: float = start_timeout
        self._max_timeout: float = max_timeout
        self._factor: float = factor
        self._random_interval_size = random_interval_size

    def get_timeout(
        self,
        attempt: int,
        response: aiohttp.ClientResponse | None = None,  # noqa: ARG002
    ) -> float:
        timeout: float = super().get_timeout(attempt) + random.uniform(0, self._random_interval_size) ** self._factor
        return timeout


@frozen(kw_only=True)
class ApiRequestParams:
    """
    Contains parameters for an API request with retries.
    """
    method: str
    url: URL
    headers: dict[str, Any] | None = None
    kwargs: aiohttp.client._RequestOptions | None = None


class ApiRequestContext:
    """
    A context manager that handles making an API request.
    """
    def __init__(
        self,
        session: aiohttp.ClientSession,
        params: ApiRequestParams,
        retry_options: Optional[RetryOptionsBase] = None,
        logger: Optional[logging.Logger] = None,
        raise_for_status: bool = False,
    ) -> None:
        self._session = session
        self._params = params
        self._retry_options = retry_options or JitterRetry()
        self._logger = logger or logging.getLogger(type(ApiRequestContext).__name__)
        self._raise_for_status = raise_for_status
        self._response: aiohttp.ClientResponse | None = None

    async def _is_skip_retry(self, current_attempt: int, response: aiohttp.ClientResponse) -> bool:
        if current_attempt == self._retry_options.attempts:
            return True

        if response.method.upper() not in self._retry_options.methods:
            return True

        if response.status >= _MIN_SERVER_ERROR_STATUS and self._retry_options.retry_all_server_errors:
            return False

        if response.status in self._retry_options.statuses:
            return False

        return True

    async def _do_request(self) -> aiohttp.ClientResponse:
        current_attempt = 0

        while True:
            self._logger.debug(f"Attempt {current_attempt+1} out of {self._retry_options.attempts}")

            current_attempt += 1
            try:
                response: aiohttp.ClientResponse = await self._session.request(
                    self._params.method,
                    self._params.url,
                    **(self._params.kwargs or {}),
                )

                debug_message = f"Retrying after response code: {response.status}"
                skip_retry = await self._is_skip_retry(current_attempt, response)

                if skip_retry:
                    if self._raise_for_status:
                        response.raise_for_status()
                    self._response = response
                    return self._response
                retry_wait = self._retry_options.get_timeout(attempt=current_attempt, response=response)

            except Exception as e:
                if current_attempt >= self._retry_options.attempts:
                    raise

                is_exc_valid = any(isinstance(e, exc) for exc in self._retry_options.exceptions)
                if not is_exc_valid:
                    raise

                debug_message = f"Retrying after exception: {e!r}"
                retry_wait = self._retry_options.get_timeout(attempt=current_attempt, response=None)

            self._logger.debug(debug_message)
            await asyncio.sleep(retry_wait)

    def __await__(self) -> Generator[Any, None, aiohttp.ClientResponse]:
        return self.__aenter__().__await__()

    async def __aenter__(self) -> aiohttp.ClientResponse:
        return await self._do_request()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._response is not None and not self._response.closed:
            self._response.close()
