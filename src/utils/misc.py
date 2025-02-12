from email.headerregistry import ContentTypeHeader
from email.policy import EmailPolicy
from typing import Any


def parse_content_type(content_type: str) -> tuple[str, dict[str, Any]]:
    """Parses a content type string into a tuple of the mime type and a dictionary of the parameters.

    Args:
        content_type (str): The content type string.

    Returns:
        _type_: The stuff.
    """
    header: ContentTypeHeader = EmailPolicy.header_factory("content-type", content_type)
    return (header.content_type, dict(header.params))
