import datetime as dt
from typing import Any

import attrs
from attrs import define


@define(repr=False, frozen=True, slots=True)
class _TimezoneValidator:
    tz: dt.tzinfo

    def __call__(self, inst: Any, attr: attrs.Attribute, value: Any) -> None:  # noqa: ANN401
        """We use a callable class to be able to change the ``__repr__``."""
        if not isinstance(value, dt.datetime):
            msg = f"Value of '{attr.name}' must be a datetime"
            raise ValueError(msg)
        if not value.tzinfo:
            msg = f"'{attr.name}' must be timezone-aware"
            raise ValueError(msg)
        if value.tzinfo.utcoffset(value) != self.tz.utcoffset(value):
            offset1 = self.tz.utcoffset(value)
            offset2 = value.tzinfo.utcoffset(value)
            msg = f"Timezone UTC offset of '{attr.name}' must be {offset1}: {offset2}"
            raise ValueError(msg)

    def __repr__(self) -> str:
        return f"timezone validator for {self.tz.tzname}>"


def has_timezone(tz: dt.tzinfo) -> _TimezoneValidator:
    """A validator that raises `ValueError` if the initializer value's timezone does not match `tz`.

    Args:
        tz (tzinfo): The required timezone.
    """
    return _TimezoneValidator(tz)


def is_utc() -> _TimezoneValidator:
    """A validator that raises `ValueError` if the initializer value's timezone is not UTC.

    Args:
        tz (tzinfo): The required timezone.
    """
    return _TimezoneValidator(dt.UTC)
