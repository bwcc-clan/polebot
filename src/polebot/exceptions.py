"""This module contains custom exceptions that are used throughout the application."""


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
