import datetime as dt

import pytest
import pytz
from attrs import define, field

from utils import validators as utils_validators


def describe_timezone_validator():

    def describe_utc_validation():
        @define
        class HasTimezoneValidator:
            t: dt.datetime = field(validator=[utils_validators.is_utc()])

        def succeeds_when_timezone_is_utc():
            # *** ARRANGE ***

            # *** ACT ***
            x = HasTimezoneValidator(t=dt.datetime.now(tz=dt.UTC))  # noqa: DTZ005

            # *** ASSERT ***
            assert x.t is not None

        def raises_when_no_timezone():
            # *** ARRANGE ***

            # *** ACT ***
            with pytest.raises(ValueError) as excinfo:
                HasTimezoneValidator(t=dt.datetime.now())  # noqa: DTZ005

            # *** ASSERT ***
            assert str(excinfo.value) == "'t' must be timezone-aware"

        def raises_when_different_timezone():
            # *** ARRANGE ***
            timezone= 'Europe/Amsterdam'

            # *** ACT ***
            with pytest.raises(ValueError) as excinfo:
                HasTimezoneValidator(t=dt.datetime.now(tz=pytz.timezone(timezone)))  # noqa: DTZ005

            # *** ASSERT ***
            assert str(excinfo.value).startswith("Timezone UTC offset of 't' must be 0:00:00: ")
