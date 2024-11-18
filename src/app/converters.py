

from types import NoneType
from typing import Any

from cattrs.preconf.json import make_converter

rcon_converter = make_converter()

@rcon_converter.register_structure_hook
def json_null_hook(val: Any, _: Any) -> NoneType: # type: ignore[valid-type]
    """
    This hook will be registered for JSON nulls. These are needed so that an ApiResult can have no 'result', which is
    represented by a JSON null in the received response.
    """
    return None
