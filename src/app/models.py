from enum import StrEnum
from typing import Optional, Union

from attrs import frozen


class Orientation(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class GameMode(StrEnum):
    WARFARE = "warfare"
    OFFENSIVE = "offensive"
    CONTROL = "control"
    PHASED = "phased"
    MAJORITY = "majority"

    @classmethod
    def large(cls):
        return (
            cls.WARFARE,
            cls.OFFENSIVE,
        )

    @classmethod
    def small(cls):
        return (
            cls.CONTROL,
            cls.PHASED,
            cls.MAJORITY,
        )

    def is_large(self):
        return self in GameMode.large()

    def is_small(self):
        return self in GameMode.small()


class Team(StrEnum):
    ALLIES = "allies"
    AXIS = "axis"


class Environment(StrEnum):
    DAWN = "dawn"
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"
    OVERCAST = "overcast"
    RAIN = "rain"


class FactionName(StrEnum):
    CW = "cw"
    GB = "gb"
    GER = "ger"
    RUS = "rus"
    US = "us"


@frozen(kw_only=True)
class Faction:
    name: str
    team: Team


@frozen(kw_only=True)
class Map:
    id: str
    name: str
    tag: str
    pretty_name: str
    shortname: str
    allies: Faction
    axis: Faction
    orientation: Orientation


@frozen(kw_only=True)
class Layer:
    id: str
    map: Map
    game_mode: GameMode
    attackers: Union[Team, None] = None
    environment: Environment = Environment.DAY
    pretty_name: str
    image_name: str


@frozen(kw_only=True)
class ApiResult[T]:
    command: str
    arguments: dict
    failed: bool
    error: Optional[str]
    version: str
    result: Optional[T]
