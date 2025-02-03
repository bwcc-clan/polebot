"""This module contains custom exceptions that are used throughout the application."""


class CRCONApiClientError(Exception):
    """The exception raised when the CRCONApiClient error occurs."""

    def __init__(self, message: str, command: str, error: str, version: str) -> None:
        """Creates a new instance of `CRCONApiClientError`.

        Args:
            message (str): Indicates the error that occurred.
            command (str): Indicates the command that failed.
            error (str): Indicates the error response from the API.
            version (str): The API version number.
        """
        self.message = message
        self.command = command
        self.error = error
        self.version = version
        super().__init__(self.message)


class WebsocketConnectionError(Exception):
    """The exception raised when a websocket connection error occurs."""

    def __init__(self, message: str) -> None:
        """Creates a new instance of `WebsocketConnectionError`.

        Args:
            message (str): Indicates the error that occurred.
        """
        self.message = message
        super().__init__(self.message)


class LogStreamMessageError(Exception):
    """The exception raised when the log stream returns a message indicating an error."""

    def __init__(self, message: str) -> None:
        """Creates a new instance of `LogStreamMessageError`.

        Args:
            message (str): The error message that was returned from the CRCON server in the response.
        """
        self.message = message
        super().__init__(self.message)


class DatastoreError(Exception):
    """The exception raised when an error occurs when accessing the data store."""

    def __init__(self, message: str) -> None:
        """Creates a new instance of `DatastoreError`.

        Args:
            message (str): Indicates the error that occurred.
        """
        self.message = message
        super().__init__(self.message)


class DuplicateKeyError(DatastoreError):
    """The exception raised when a data store operation would result in a unique key index violation."""

    def __init__(self) -> None:
        """Creates a new instance of `DuplicateKeyError`.

        Args:
            message (str): Indicates the error that occurred.
        """
        self.message = "Key already exists"
        super().__init__(self.message)


class TerminateTaskGroup(Exception):  # noqa: N818 - taken from docs https://docs.python.org/3/library/asyncio-task.html#terminating-a-task-group
    """Exception raised to terminate a task group."""
