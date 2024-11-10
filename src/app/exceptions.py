
class LogStreamMessageError(Exception):
    """
    The exception that is raised when the log stream returns a message indicating an error.
    """
    def __init__(self, message: str) -> None:
        """
        Creates a new instance of `LogStreamMessageError`.

        Args:
            message (str): The error message that was returned from the CRCON server in the response.
        """
        self.message = message
        super().__init__(self.message)
