"""This module contains custom exceptions that are used throughout the application."""


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


class TerminateTaskGroup(Exception):  # noqa: N818 - taken from docs https://docs.python.org/3/library/asyncio-task.html#terminating-a-task-group
    """Exception raised to terminate a task group."""
