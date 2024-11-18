

import os
import random
from collections.abc import Generator

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

