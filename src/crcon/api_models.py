import datetime
from enum import StrEnum
from typing import Optional

from attrs import field, frozen, validators

# Represents a redis stream ID, these are by default
# the unix timestamp of when the element was added
# with a 0 indexed sequence number when there are
# multiple entries at the same timestamp
# ex: "1526919030474-0"
StreamID = Optional[str]


class LogMessageType(StrEnum):
    """Both native (from the game server) and synthetic (created by CRCON) log types."""

    admin = "ADMIN"
    admin_anti_cheat = "ADMIN ANTI-CHEAT"
    admin_banned = "ADMIN BANNED"
    admin_idle = "ADMIN IDLE"
    admin_kicked = "ADMIN KICKED"
    admin_misc = "ADMIN MISC"
    admin_perma_banned = "ADMIN PERMA BANNED"
    allies_chat = "CHAT[Allies]"
    allies_team_chat = "CHAT[Allies][Team]"
    allies_unit_chat = "CHAT[Allies][Unit]"
    axis_chat = "CHAT[Axis]"
    axis_team_chat = "CHAT[Axis][Team]"
    axis_unit_chat = "CHAT[Axis][Unit]"
    camera = "CAMERA"
    chat = "CHAT"
    connected = "CONNECTED"
    disconnected = "DISCONNECTED"
    kill = "KILL"
    match = "MATCH"
    match_end = "MATCH ENDED"
    match_start = "MATCH START"
    message = "MESSAGE"
    team_kill = "TEAM KILL"
    team_switch = "TEAMSWITCH"
    # Automatic kicks for team kills
    tk = "TK"
    tk_auto = "TK AUTO"
    tk_auto_banned = "TK AUTO BANNED"
    tk_auto_kicked = "TK AUTO KICKED"
    # Vote kicks
    vote = "VOTE"
    vote_completed = "VOTE COMPLETED"
    vote_expired = "VOTE EXPIRED"
    vote_passed = "VOTE PASSED"
    vote_started = "VOTE STARTED"


@frozen(kw_only=True)
class StructuredLogLineWithMetaData:
    version: int
    timestamp_ms: int
    event_time: datetime.datetime
    relative_time_ms: Optional[float]
    raw: str
    line_without_time: Optional[str]
    action: str
    player_name_1: Optional[str]
    player_id_1: Optional[str]
    player_name_2: Optional[str]
    player_id_2: Optional[str]
    weapon: Optional[str]
    message: str
    sub_content: Optional[str]


@frozen(kw_only=True)
class LogStreamObject:
    id: StreamID
    log: StructuredLogLineWithMetaData


@frozen(kw_only=True)
class LogStreamResponse:
    logs: list[LogStreamObject]
    last_seen_id: StreamID | None
    error: Optional[str]


@frozen(kw_only=True)
class ApiResult[TResult]:
    """The standard wrapper for the result of an API call. The payload, if any, is in the `result` attribute."""

    command: str
    failed: bool
    error: Optional[str]
    version: str
    result: Optional[TResult]


@frozen(kw_only=True)
class ApiResultWithArgs[TResult, TArgs](ApiResult[TResult]):
    arguments: TArgs


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
    def large(cls) -> tuple["GameMode", ...]:
        return (
            cls.WARFARE,
            cls.OFFENSIVE,
        )

    @classmethod
    def small(cls) -> tuple["GameMode", ...]:
        return (
            cls.CONTROL,
            cls.PHASED,
            cls.MAJORITY,
        )

    def is_large(self) -> bool:
        return self in GameMode.large()

    def is_small(self) -> bool:
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
    attackers: Optional[Team] = None
    environment: Environment = Environment.DAY
    pretty_name: str
    image_name: str


class DefaultMethods(StrEnum):
    least_played_suggestions = "least_played_from_suggestions"
    least_played_all_maps = "least_played_from_all_map"
    random_suggestions = "random_from_suggestions"
    random_all_maps = "random_from_all_maps"


INSTRUCTION_TEXT = """Vote for the nextmap:
Type in the chat !votemap <map number>
{map_selection}

To never see this message again type in the chat !votemap never

To renable type: !votemap allow"""
THANK_YOU_TEXT = "Thanks {player_name}, vote registered for:\n{map_name}"
NO_VOTE_TEXT = "No votes recorded yet"
HELP_TEXT = """To vote you must type in the chat (press K to open the chat) !votemap followed by the number of the map\
    you want (from 0 to N), you must write the number without the brackets, e.g.: !votemap 0

The map numbers appear in the reminder message you get once in a while or if you type !votemap without a number.

If you want to opt-out of the votemap reminder FOREVER type !votemap never

To opt back in again type !votemap allow

To see the select type !votemap

To see this message again type !votemap help"""


@frozen(kw_only=True)
class VoteMapUserConfig:
    enabled: bool = field(default=False)
    default_method: DefaultMethods = field(default=DefaultMethods.least_played_suggestions)
    number_last_played_to_exclude: int = field(validator=validators.ge(0), default=3)
    num_warfare_options: int = field(validator=validators.ge(0), default=4)
    num_offensive_options: int = field(validator=validators.ge(0), default=2)
    num_skirmish_control_options: int = field(validator=validators.ge(0), default=1)
    consider_offensive_same_map: bool = field(default=True)
    consider_skirmishes_as_same_map: bool = field(default=True)
    allow_consecutive_offensives: bool = field(default=True)
    allow_consecutive_offensives_opposite_sides: bool = field(default=False)
    allow_default_to_offensive: bool = field(default=False)
    allow_consecutive_skirmishes: bool = field(default=False)
    allow_default_to_skirmish: bool = field(default=False)
    instruction_text: str = field(default=INSTRUCTION_TEXT)
    thank_you_text: str | None = field(default=THANK_YOU_TEXT)
    no_vote_text: str = field(default=NO_VOTE_TEXT)
    reminder_frequency_minutes: int = field(validator=validators.ge(0), default=20)
    allow_opt_out: bool = field(default=True)
    help_text: str | None = field(default="")


@frozen(kw_only=True)
class SetVotemapWhitelistParams:
    map_names: list[str]


@frozen(kw_only=True)
class ServerStatus:
    name: str
    map: Layer
    current_players: int
    max_players: int
    short_name: str
    server_number: int
