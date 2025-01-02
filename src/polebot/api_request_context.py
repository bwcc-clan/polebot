"""Performs retrying on requests to the CRCON API.

Based on https://github.com/inyutin/aiohttp_retry but with customizations.
"""

import abc
import asyncio
import logging
import random
from collections.abc import Generator, Iterable
from types import TracebackType
from typing import Any

import aiohttp
import aiohttp.typedefs
from attrs import frozen
from yarl import URL

_MIN_SERVER_ERROR_STATUS = 500


class RetryOptionsBase(abc.ABC):
    """Base class for request retry options."""

    def __init__(
        self,
        attempts: int = 3,
        statuses: Iterable[int] | None = None,
        exceptions: Iterable[type[Exception]] | None = None,
        methods: Iterable[str] | None = None,
        retry_all_server_errors: bool = True,
    ) -> None:
        """Initializes the retry options.

        Args:
            attempts (int, optional): How many times should we retry. Defaults to 3.
            statuses (set[int], optional): On which statuses we should retry
            exceptions (set[type[Exception]], optional): On which exception types we should retry
            methods (set[str], optional):  On which HTTP methods we should retry
            retry_all_server_errors (bool, optional): If should retry all 500 errors or not
        """
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
        """Gets the timeout (in seconds) for the retry attempt iteration."""
        raise NotImplementedError


class ExponentialRetry(RetryOptionsBase):
    """A retry option with exponential backoff."""

    def __init__(
        self,
        attempts: int = 3,
        start_timeout: float = 0.1,
        max_timeout: float = 30.0,
        factor: float = 2.0,
        statuses: set[int] | None = None,
        exceptions: set[type[Exception]] | None = None,
        methods: set[str] | None = None,
        retry_all_server_errors: bool = True,
    ) -> None:
        """Initializes the retry options.

        Args:
            attempts (int, optional): How many times should we retry. Defaults to 3.
            start_timeout (float, optional): Base timeout in seconds, then it exponentially grow. Defaults to 0.1.
            max_timeout (float, optional): Max possible timeout between tries. Defaults to 30.0.
            factor (float, optional): How much we increase timeout each time
            statuses (set[int], optional): On which statuses we should retry
            exceptions (set[type[Exception]], optional): On which exception types we should retry
            methods (set[str], optional):  On which HTTP methods we should retry
            random_interval_size (float, optional): Size of interval for random component
            retry_all_server_errors (bool, optional): If should retry all 500 errors or not
        """
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
        """Gets the timeout (in seconds) for the retry attempt iteration."""
        timeout = self._start_timeout * (self._factor**attempt)
        return min(timeout, self._max_timeout)


class JitterRetry(ExponentialRetry):
    """A retry option with exponential backoff and jitter."""

    def __init__(
        self,
        attempts: int = 3,
        start_timeout: float = 0.1,
        max_timeout: float = 30.0,
        factor: float = 2.0,
        statuses: set[int] | None = None,
        exceptions: set[type[Exception]] | None = None,
        methods: set[str] | None = None,
        random_interval_size: float = 2.0,
        retry_all_server_errors: bool = True,
    ) -> None:
        """Initializes the retry options.

        Args:
            attempts (int, optional): How many times should we retry. Defaults to 3.
            start_timeout (float, optional): Base timeout in seconds, then it exponentially grow. Defaults to 0.1.
            max_timeout (float, optional): Max possible timeout between tries. Defaults to 30.0.
            factor (float, optional): How much we increase timeout each time
            statuses (set[int], optional): On which statuses we should retry
            exceptions (set[type[Exception]], optional): On which exception types we should retry
            methods (set[str], optional):  On which HTTP methods we should retry
            random_interval_size (float, optional): Size of interval for random component
            retry_all_server_errors (bool, optional): If should retry all 500 errors or not
        """
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
        """Gets the timeout (in seconds) for the retry attempt iteration."""
        timeout: float = super().get_timeout(attempt) + random.uniform(0, self._random_interval_size) ** self._factor  # noqa: S311
        return timeout


@frozen(kw_only=True)
class ApiRequestParams:
    """Contains parameters for an API request with retries."""
    method: str
    url: URL
    headers: dict[str, Any] | None = None
    kwargs: aiohttp.client._RequestOptions | None = None


class ApiRequestContext:
    """Context manager for making API requests with retries."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        params: ApiRequestParams,
        retry_options: RetryOptionsBase | None = None,
        logger: logging.Logger | None = None,
        raise_for_status: bool = False,
    ) -> None:
        """Initializes the context manager.

        Args:
            session (aiohttp.ClientSession): The session to use for the request.
            params (ApiRequestParams): The parameters for the request.
            retry_options (RetryOptionsBase | None, optional): The retry options. Defaults to None.
            logger (logging.Logger | None, optional): The logger to use. Defaults to None.
            raise_for_status (bool, optional): Whether to raise an exception for a failure HTTP status response code.
            Defaults to False.
        """
        self._session = session
        self._params = params
        self._retry_options = retry_options or JitterRetry()
        self._logger = logger or logging.getLogger(__name__)
        self._raise_for_status = raise_for_status
        self._response: aiohttp.ClientResponse | None = None

    async def _is_skip_retry(self, current_attempt: int, response: aiohttp.ClientResponse) -> bool:
        if current_attempt == self._retry_options.attempts:
            return True

        if response.method.upper() not in self._retry_options.methods:
            return True

        if response.status >= _MIN_SERVER_ERROR_STATUS and self._retry_options.retry_all_server_errors:
            return False

        return response.status not in self._retry_options.statuses

    async def _do_request(self) -> aiohttp.ClientResponse:
        current_attempt = 0

        while True:
            self._logger.debug("Attempt %d out of %d", current_attempt+1, self._retry_options.attempts)

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
        """Part of the awaitable protocol."""
        return self.__aenter__().__await__()

    async def __aenter__(self) -> aiohttp.ClientResponse:
        """Part of the context manager protocol."""
        return await self._do_request()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Part of the context manager protocol."""
        if self._response is not None and not self._response.closed:
            self._response.close()
