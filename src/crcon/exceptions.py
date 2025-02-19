class ApiClientError(Exception):
    """The exception raised when an ApiClient error occurs."""

    def __init__(self, message: str, command: str, error: str, version: str | None) -> None:
        """Creates a new instance of `ApiClientError`.

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
