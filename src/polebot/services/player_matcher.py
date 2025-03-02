import re

from attrs import frozen


@frozen(kw_only=True)
class PlayerProperties:
    name: str
    id: str


class PlayerMatcher:
    def __init__(self, selector: str, exact: bool = False) -> None:
        ok, err = self.validate_selector(selector)
        if not ok:
            raise ValueError(err)

        assert not isinstance(err, str)  # noqa: S101
        self.selector = selector
        self._pattern = err
        self.exact = exact
        if self.exact and self._pattern is not None:
            raise ValueError("Exact match requires a simple string selector")

    def is_match(self, player: PlayerProperties) -> bool:
        if self.exact:
            return player.name == self.selector
        if self._pattern is None:
            return player.name.startswith(self.selector)
        return re.match(self._pattern, player.name) is not None

    @classmethod
    def validate_selector(cls, selector: str) -> tuple[bool, str | re.Pattern[str] | None]:
        if selector.startswith("/") and selector.endswith("/"):
            try:
                pattern = re.compile(selector.strip("/"))
                return (True, pattern)
            except re.error:
                return (False, "Selector is not a valid regular expression")
        return (True, None)
